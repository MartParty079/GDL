"""Local identity, offline transport, role boundaries and real startup regressions."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services.storage import Store, write_json, read_json
from app.services.local_accounts import LocalAccounts, NAMES, matches
from app.services.contributions import Participation, WeeklyReports, combined_report
from app.services import updates
from app import edition

ROOT = Path(__file__).resolve().parents[1]


class LocalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(local_dir=self.root / 'profile')
        self.accounts = LocalAccounts(self.store)
        self.users = self.accounts.users()

    def tearDown(self):
        self.accounts.close()
        self.temp.cleanup()

    def admin(self):
        recovery = self.accounts.setup_admin('135790')
        self.accounts.sign_in(self.users[0]['id'], '135790')
        return recovery

    def test_four_permanent_profiles_optional_pin_and_remembered_switch(self):
        self.assertEqual([p['display_name'] for p in self.users], list(NAMES))
        self.assertEqual(len({p['id'] for p in self.users}), 4)
        for person in self.users[1:]:
            self.accounts.sign_in(person['id'])
            self.assertFalse(self.accounts.admin_unlocked)
            self.assertEqual(self.store.local['selected_user'], person['id'])
            self.accounts.sign_out()
        self.accounts.sign_in(self.users[1]['id'], automatic=True)
        other = LocalAccounts(Store(local_dir=self.store.local_dir))
        try:
            self.assertEqual(other.restore()['id'], self.users[1]['id'])
            self.assertEqual(other.install_id, self.accounts.install_id)
        finally:
            other.close()

    def test_admin_requires_pin_and_no_automatic_admin_restore(self):
        with self.assertRaisesRegex(ValueError, 'Set an Admin PIN'):
            self.accounts.sign_in(self.users[0]['id'])
        self.accounts.sign_in(self.users[1]['id'])
        with self.assertRaises(ValueError):
            self.accounts.manage_user(name='Unauthorized')
        recovery = self.admin()
        self.assertTrue(self.accounts.admin_unlocked)
        self.accounts.sign_in(self.users[0]['id'], '135790', automatic=True)
        self.assertEqual(self.store.local['automatic_user'], '')
        self.assertNotIn('135790', self.accounts.profile_path.read_text(encoding='utf-8'))
        self.assertNotIn(recovery, self.accounts.profile_path.read_text(encoding='utf-8'))
        self.assertTrue(matches('135790', self.accounts.find(self.users[0]['id'])['pin']))

    def test_pin_change_reset_recovery_and_persistent_rate_limit(self):
        code = self.admin()
        self.accounts.sign_out()
        member = self.users[1]['id']
        self.accounts.sign_in(member)
        self.accounts.change_pin('', '2468')
        self.accounts.sign_out()
        for i in range(5):
            with self.assertRaisesRegex(ValueError, 'not accepted'):
                self.accounts.sign_in(member, '1111')
        again = LocalAccounts(Store(local_dir=self.store.local_dir))
        try:
            with self.assertRaisesRegex(ValueError, 'Wait one minute'):
                again.sign_in(member, '2468')
        finally:
            again.close()
        self.accounts.sign_in(self.users[0]['id'], '135790')
        self.accounts.manage_user(member, reset_pin=True)
        self.assertIsNone(self.accounts.find(member)['pin'])
        new_code = self.accounts.recover_admin(code, '987654')
        self.assertNotEqual(code, new_code)
        with self.assertRaises(ValueError):
            self.accounts.recover_admin(code, '112233')
        self.accounts.sign_in(self.users[0]['id'], '987654')
        with self.assertRaises(ValueError):
            self.accounts.change_pin('987654', '')

    def test_profile_revision_backup_writer_and_conflict_rejection(self):
        self.admin()
        identity = self.users[1]['id']
        self.accounts.manage_user(identity, name='Andrew renamed')
        self.assertEqual(self.accounts.find(identity)['id'], identity)
        self.assertTrue(list((self.accounts.shared / 'Configuration' / 'Backups').glob('*.json')))
        cached = copy.deepcopy(self.accounts.registry)
        self.accounts.manage_user(identity, active=False)
        self.accounts.registry = cached
        with self.assertRaisesRegex(ValueError, 'changed on another device'):
            self.accounts.manage_user(identity, name='Stale')
        self.accounts.registry = self.accounts.load_registry()
        write_json(self.accounts.profile_path.with_name('profiles-conflicted-PC.json'), cached)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.accounts.manage_user(name='Conflict')
        self.accounts.profile_path.with_name('profiles-conflicted-PC.json').unlink()
        self.accounts.registry['writer_device'] = 'another-device'
        with self.assertRaisesRegex(ValueError, 'designated profile writer'):
            self.accounts.manage_user(name='Wrong writer')

    def test_offline_queue_restart_sync_dedup_and_owner_attribution(self):
        self.admin()
        shared = self.accounts.shared
        self.accounts.shared = self.root / 'offline' / 'AppData' / edition.CHANNEL
        self.accounts.event('EXPERIMENT_UPDATED', 'experiment', 'EXP-1')
        self.assertFalse(self.accounts.flush())
        queued = list((self.accounts.base / 'outbox' / 'Events').glob('*.json'))
        self.assertTrue(queued)
        snapshot = [read_json(p, {}) for p in queued]
        self.accounts.shared = shared
        self.accounts.flush()
        for row in snapshot:
            write_json(self.accounts.base / 'outbox' / 'Events' / (row['id'] + '.json'), row)
        self.accounts.flush(); self.accounts.flush()
        events = self.accounts.rows('Events')
        self.assertEqual(len(events), len({e['id'] for e in events}))
        self.assertEqual(len([e for e in events if e['event_type'] == 'EXPERIMENT_UPDATED']), 1)
        self.assertTrue(all(e['user_id'] == self.users[0]['id'] for e in events))
        self.accounts.sign_out()
        self.accounts.sign_in(self.users[1]['id'])
        self.assertFalse(any(e['event_type'] == 'EXPERIMENT_UPDATED' for e in self.accounts.rows('Events')))

    def test_weekly_and_combined_reports_use_measured_events(self):
        self.admin()
        self.accounts.participation = Participation(self.accounts)
        self.accounts.event('FILE_ADDED', 'file', 'f', 'fixture.csv', {'attribution':'app_user_action'})
        self.accounts.event('PROCEDURE_UPDATED', 'procedure', 'P-1')
        self.accounts.flush()
        begin = datetime.now(timezone.utc) - timedelta(days=1)
        end = begin + timedelta(days=7)
        reports = [WeeklyReports(self.accounts).load(p, begin, end) for p in self.accounts.roster()]
        combined = combined_report(reports)
        self.assertEqual(combined['metrics']['Files added (known attribution)'], 1)
        self.assertEqual(combined['metrics']['Procedure revisions'], 1)
        self.assertEqual(combined['metrics']['Sessions'], 1)
        self.assertNotIn('score', json.dumps(combined['metrics']).lower())
        contaminated = dict(self.accounts.rows('Events')[0], id='foreign', channel='stable' if edition.CHANNEL != 'stable' else 'beta')
        write_json(self.accounts.shared / 'Activity' / 'Events' / 'foreign.json', contaminated)
        self.assertFalse(any(e['id'] == 'foreign' for e in self.accounts.rows('Events')))

    def test_absent_shared_root_uses_cache_and_never_recreates_root(self):
        self.accounts.sign_in(self.users[1]['id'])
        shared_root = self.accounts.shared.parents[1]
        moved = shared_root.with_name('temporarily-disconnected')
        self.accounts.flush()
        shared_root.rename(moved)
        try:
            again = LocalAccounts(Store(local_dir=self.store.local_dir))
            try:
                again.sign_in(self.users[1]['id'])
                self.assertFalse(again.flush())
                self.assertFalse(shared_root.exists())
                self.assertIn('unavailable', again.warning)
            finally:
                again.close()
        finally:
            moved.rename(shared_root)

    def test_update_is_recorded_only_after_verified_new_version(self):
        self.accounts.sign_in(self.users[1]['id'])
        self.accounts.flush()
        self.assertFalse(any(e['event_type'] == 'APP_UPDATED' for e in self.accounts.rows('Events')))
        write_json(self.store.local_dir / 'update-result.local.json', {'status':'version_verified','verified_version':edition.DISPLAY_VERSION})
        self.accounts.sign_in(self.users[1]['id'])
        self.accounts.sign_in(self.users[1]['id'])
        self.accounts.flush()
        self.assertEqual(len([e for e in self.accounts.rows('Events') if e['event_type'] == 'APP_UPDATED']), 1)

    def test_storage_remapping_preserves_activity_and_rejects_conflicting_profiles(self):
        self.admin()
        self.store.accounts = self.accounts
        self.accounts.event('SAMPLE_UPDATED', 'sample', 'S-1')
        self.accounts.flush()
        from app.services.project_locations import ProjectLocations
        locations = ProjectLocations(self.store)
        value = copy.deepcopy(locations.value)
        current = self.root / 'research'; current.mkdir()
        shared = self.root / 'team'; shared.mkdir()
        value['active']['root_path'] = str(current)
        value['legacy'] = []
        value['shared_storage'] = str(shared)
        original = self.accounts.shared
        locations.save(value)
        self.assertNotEqual(self.accounts.shared, original)
        self.assertTrue((original / 'Users' / 'profiles.json').is_file())
        self.assertEqual(len([e for e in self.accounts.rows('Events') if e['event_type'] == 'SAMPLE_UPDATED']), 1)
        target = self.root / 'conflicting-team'; target.mkdir()
        write_json(target / 'AppData' / edition.CHANNEL / 'Users' / 'profiles.json', {'revision':999})
        value['shared_storage'] = str(target)
        saved = copy.deepcopy(self.store.local['project_locations'])
        with self.assertRaisesRegex(ValueError, 'different team profiles'):
            locations.save(value)
        self.assertEqual(self.store.local['project_locations'], saved)
        self.accounts.sign_out(); self.accounts.sign_in(self.users[1]['id'])
        with self.assertRaises(ValueError):locations.save(saved)

    def test_processing_completion_retains_initiating_user_after_switch(self):
        self.admin()
        owner = self.accounts.profile['id']
        self.accounts.sign_out(); self.accounts.sign_in(self.users[1]['id'])
        self.accounts.event('IMAGE_PROCESSED', 'processing', 'run-1', owner=owner)
        self.accounts.flush()
        self.assertFalse(any(e['event_type'] == 'IMAGE_PROCESSED' for e in self.accounts.rows('Events')))
        self.accounts.sign_out(); self.accounts.sign_in(owner, '135790')
        event = next(e for e in self.accounts.rows('Events') if e['event_type'] == 'IMAGE_PROCESSED')
        self.assertEqual(event['user_id'], owner)


class ChannelIsolationTests(unittest.TestCase):
    def test_main_login_switch_and_member_window_lifecycle(self):
        # A separate process catches real startup/teardown problems without
        # sharing QApplication lifetime with unrelated widget tests.
        code = '''
import tempfile,time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtCore import QTimer
from app.services.storage import Store
from app.services.local_accounts import LocalAccounts
from app.ui.local_accounts import LoginDialog
from app.ui.window import HubWindow
from app.main import main
app=QApplication([])
temporary=tempfile.TemporaryDirectory()
store=Store(local_dir=Path(temporary.name)/'profile')
seed=LocalAccounts(store);users=seed.users();seed.close()
store.local['automatic_user']=users[1]['id'];store.save_local()
observed=[];started=time.monotonic();timer=QTimer()
def inspect():
    windows=[w for w in app.topLevelWidgets() if isinstance(w,HubWindow) and w.isVisible()]
    if windows:
        window=windows[0]
        if window.account_service.profile is None:return
        assert not hasattr(window,'admin_workspace')
        assert not window.tabs.isTabVisible(list(window.pages).index('Settings'))
        assert window.findChild(QPushButton,'current-user').text().startswith(window.account_service.profile['display_name'])
        if not observed and not window.research_workspace.busy():
            observed.append(window.account_service.profile['id'])
            window.findChild(QPushButton,'current-user').menu().actions()[-1].trigger()
        elif observed and window.account_service.profile['id']==users[3]['id']:
            if not window.research_workspace.busy() and not window.meetings_panel.busy() and not window.weekly_panel.tasks.busy():
                observed.append(users[3]['id']);timer.stop();window.close()
    elif observed:
        dialogs=[w for w in app.topLevelWidgets() if isinstance(w,LoginDialog) and w.isVisible()]
        if dialogs:
            dialog=dialogs[0];dialog.person.setCurrentIndex(dialog.person.findData(users[3]['id']));dialog.sign_in()
    if time.monotonic()-started>20:
        timer.stop();app.exit(9)
timer.timeout.connect(inspect);timer.start(40)
with patch('app.main.Store',return_value=store),patch('app.services.diagnostics.configure'),patch.object(HubWindow,'scan',lambda _:None),patch.object(HubWindow,'check_updates_on_startup',lambda _:None):
    result=main()
assert result==0,result
assert observed==[users[1]['id'],users[3]['id']],observed
print('login-switch-workspace-close passed')
temporary.cleanup()
import gc;gc.collect()
app.shutdown()
'''
        environment=dict(os.environ, QT_QPA_PLATFORM='offscreen', GDL_HUB_CHANNEL='beta')
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=environment,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('login-switch-workspace-close passed',result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_source_development_has_separate_identity_and_no_remote_updates(self):
        code = 'from app.edition import *;from app.services.updates import latest_release;print(CHANNEL,PROFILE_NAME,DISPLAY_VERSION);latest_release()'
        environment = dict(os.environ); environment.pop('GDL_HUB_CHANNEL', None)
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=environment, capture_output=True, text=True)
        self.assertIn('development FuelCellProjectHubDevelopment', result.stdout)
        self.assertIn('-dev.', result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No remote installer channel', result.stderr)
        self.assertFalse(updates.newer('v9.0.0-beta.1', '0.5.0-dev.1'))
        self.assertFalse(updates.newer('v9.0.0', '0.5.0-dev.1'))

    def test_old_beta_mapping_migrates_without_touching_production(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = root / 'FuelCellProjectHubBeta'
            production = root / 'production'; production.mkdir()
            original = production / 'research.txt'; original.write_text('keep')
            write_json(profile / 'local.json', {'paths':{},'shared_root':str(production),'local_project_root':str(production)})
            with patch.dict(os.environ, {'LOCALAPPDATA':temporary,'GDL_HUB_BETA_DATA_DIR':temporary}), patch.object(edition, 'PROFILE_NAME', 'FuelCellProjectHubBeta'), patch.object(edition, 'BETA', True):
                store = Store()
                self.assertTrue(store.sandbox_required)
                self.assertNotIn('shared_root', store.local)
                self.assertTrue(list((profile / 'migration-backups').glob('*.json')))
                self.assertEqual(original.read_text(), 'keep')
                self.assertEqual(list(production.iterdir()), [original])
                with self.assertRaises(ValueError):store.attach_shared(production)
                with self.assertRaises(ValueError):store.validate_project_output(production / 'out.txt')

    def test_packaging_contains_no_external_login_configuration(self):
        source=(ROOT / 'tools/FuelCellProjectHub.spec').read_text(encoding='utf-8')
        self.assertNotIn('accounts_public.json', source)
        self.assertNotIn('accounts_beta_public.json', source)
        self.assertFalse((ROOT / 'app/services/accounts.py').exists())
        self.assertFalse((ROOT / 'app/services/desktop_oauth.py').exists())


if __name__ == '__main__':
    unittest.main()
