import hashlib
import json
import os
import runpy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import QThread, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit
from app.services import updates
from app.services.storage import Store, write_json
from app.services.project_locations import ProjectLocations
from app.services.local_accounts import LocalAccounts
from app.ui.update_installation import SafeUpdate, StartupUpdate, pending_update_at_startup
from app.ui.update_recovery import UpdateRecovery
from app import edition

APP = QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parents[1]


def future_release():
    tag=f'v{updates.version(updates.__version__)[0]+1}.0.0'
    if '-beta.' in updates.__version__:tag+='-beta.1'
    return {'tag':tag,'assets':{name:{'browser_download_url':f'https://github.com/MartParty079/GDL/releases/download/{tag}/{name}'} for name in (updates.ASSET,updates.ASSET+'.sha256')}}


class Response:
    def __init__(self,data):self.data=data;self.offset=0
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n=-1):
        end=len(self.data) if n<0 else self.offset+n
        result=self.data[self.offset:end];self.offset=end;return result
    def geturl(self):return 'https://release-assets.githubusercontent.com/asset'


class CooperativeTask(QThread):
    def __init__(self,parent):super().__init__(parent);self.stop=threading.Event()
    def run(self):self.stop.wait(10)


class UpdateFixture(QWidget):
    def __init__(self,directory):
        super().__init__();self.store=Store(local_dir=directory)
        self.fields={'project_name':QLineEdit('Unsaved title',self)};self.lifecycle_fields={}
        self.research_panel=QWidget(self)
        self.research_panel.watcher=SimpleNamespace(stop=Mock())
        self.research_panel.cancel_index=Mock();self.research_panel.configure_watcher=Mock()
        self.storage_panel=SimpleNamespace(cancel_index=Mock())
        self.research_workspace=SimpleNamespace(save_layout=Mock())
        self.latest_release_info=future_release();self.messages=[];self.closed=False
        self.update_recovery=UpdateRecovery(self);self.safe_update=SafeUpdate(self)
    def offer_deferred_update(self,message):self.messages.append(message)
    def close(self):self.closed=True;return True


class SafeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.window=UpdateFixture(self.root)
    def tearDown(self):
        self.window.safe_update.timer.stop()
        for thread in self.window.findChildren(CooperativeTask):thread.stop.set();thread.wait(1000)
        self.window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.temp.cleanup()
    def pump(self,condition):
        end=time.monotonic()+4
        while not condition() and time.monotonic()<end:APP.processEvents();time.sleep(.01)
        self.assertTrue(condition())
    def test_update_now_idle_preserves_profile_and_starts_installer(self):
        for name in ('tokens.bin','research.sqlite3','research-file.txt'):(self.root/name).write_bytes(b'preserved')
        installer=self.root/'verified.exe';installer.write_bytes(b'MZfixture')
        with patch.object(self.window.safe_update.pending,'prepare',return_value=installer),patch('app.ui.update_installation.launch_installer') as launch:
            self.window.safe_update.start();self.pump(lambda:self.window.closed)
            launch.assert_called_once_with(installer)
        for name in ('tokens.bin','research.sqlite3','research-file.txt'):self.assertEqual((self.root/name).read_bytes(),b'preserved')
        self.assertEqual(self.window.safe_update.pending.read()['status'],'installer_started')
        drafts=json.loads((self.root/'update-drafts.local.json').read_text())
        self.assertEqual(drafts['settings']['project_name'],'Unsaved title')
    def test_active_index_is_cooperatively_cancelled_and_drained(self):
        task=CooperativeTask(self.window);task.start()
        self.window.research_panel.cancel_index.side_effect=task.stop.set
        with patch.object(self.window.safe_update.pending,'prepare',return_value=self.root/'verified.exe'),patch('app.ui.update_installation.launch_installer'):
            self.window.safe_update.start();self.pump(lambda:self.window.closed)
        self.window.research_panel.cancel_index.assert_called_once()
        self.assertFalse(task.isRunning())
    def test_refusing_task_never_terminated_and_offers_next_open(self):
        task=CooperativeTask(self.window);task.start()
        controller=self.window.safe_update;controller.start();controller.deadline=0;controller.tick()
        self.assertTrue(task.isRunning());self.assertFalse(self.window.closed)
        self.assertIn('not be terminated',self.window.messages[-1]);self.assertTrue(self.window.isEnabled())
    def test_cancellation_failure_preserves_work(self):
        self.window.storage_panel.cancel_index.side_effect=RuntimeError('unsafe')
        self.window.safe_update.start()
        self.assertFalse(self.window.closed);self.assertIn('safely cancel',self.window.messages[-1])
    def test_scheduling_does_not_interrupt_background_work(self):
        task=CooperativeTask(self.window);task.start();self.window.safe_update.schedule()
        self.assertTrue(task.isRunning());self.window.research_panel.cancel_index.assert_not_called()
        self.assertEqual(self.window.safe_update.pending.read()['status'],'scheduled')
    def test_download_failure_resumes_app_and_keeps_retry(self):
        with patch.object(self.window.safe_update.pending,'prepare',side_effect=OSError('raw-error-secret')):
            self.window.safe_update.start();self.pump(lambda:bool(self.window.messages))
        self.assertTrue(self.window.isEnabled());self.assertFalse(self.window.closed)
        self.assertNotIn('raw-error',self.window.messages[-1]);self.assertTrue(self.window.safe_update.pending.read())
    def test_installer_launch_failure_resumes_and_keeps_session(self):
        (self.root/'tokens.bin').write_bytes(b'encrypted-session')
        with patch.object(self.window.safe_update.pending,'prepare',return_value=self.root/'verified.exe'),patch('app.ui.update_installation.launch_installer',side_effect=OSError('failure')):
            self.window.safe_update.start();self.pump(lambda:bool(self.window.messages))
        self.assertFalse(self.window.closed);self.assertEqual((self.root/'tokens.bin').read_bytes(),b'encrypted-session')
        self.assertIn('Installer could not start',self.window.messages[-1])
    def test_activity_flush_has_bounded_wait(self):
        future=Mock();future.done.return_value=False
        self.window.account_service=SimpleNamespace(lock=threading.RLock(),executor=SimpleNamespace(submit=Mock(return_value=future)),flush=Mock())
        controller=self.window.safe_update;controller.start();controller.flush_deadline=0;controller.tick()
        self.assertIn('Activity synchronization',self.window.messages[-1]);future.cancel.assert_called_once()
        self.assertFalse(self.window.closed)
    def test_unsafe_scientific_processing_is_not_stopped(self):
        self.window.gdl_service=SimpleNamespace(active=lambda:True,stop_analysis=Mock())
        self.window.safe_update.start();self.assertIn('Scientific analysis',self.window.messages[-1])
        self.window.gdl_service.stop_analysis.assert_not_called()
    def test_saved_settings_recover_without_overwriting_shared_data(self):
        self.window.update_recovery.save();self.window.fields['project_name'].setText('Changed')
        self.window.update_recovery.restore_settings()
        self.assertEqual(self.window.fields['project_name'].text(),'Unsaved title')


class PendingUpdateTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.pending=updates.PendingUpdate(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_restart_pending_update_runs_before_workspace_and_retries_failure(self):
        release=future_release();self.pending.schedule(release)
        restored=updates.PendingUpdate(self.root)
        with patch.object(updates,'latest_release',return_value=release),patch.object(updates,'verified_download',return_value=self.root/'installer.exe') as download:
            self.assertEqual(restored.prepare(),self.root/'installer.exe');download.assert_called_once()
        store=Store(local_dir=self.root)
        with patch.object(updates.PendingUpdate,'prepare',side_effect=OSError('offline')):
            self.assertFalse(pending_update_at_startup(store))
        self.assertTrue(self.pending.read())
    def test_startup_installer_failure_allows_normal_start(self):
        self.pending.schedule(future_release())
        with patch.object(updates.PendingUpdate,'prepare',return_value=self.root/'installer.exe'),patch('app.ui.update_installation.launch_installer',side_effect=OSError('denied')):
            self.assertFalse(pending_update_at_startup(Store(local_dir=self.root)))
        self.assertEqual(self.pending.read()['status'],'scheduled')
    def test_startup_install_success_exits_before_normal_background_work(self):
        self.pending.schedule(future_release())
        with patch.object(updates.PendingUpdate,'prepare',return_value=self.root/'installer.exe'),patch('app.ui.update_installation.launch_installer') as launch:
            self.assertTrue(pending_update_at_startup(Store(local_dir=self.root)));launch.assert_called_once()
    def test_current_or_newer_installed_version_clears_pending(self):
        write_json(self.pending.path,{'tag':'v'+updates.__version__,'status':'installer_started'})
        with patch.object(updates,'latest_release') as network:self.assertIsNone(self.pending.prepare());network.assert_not_called()
        self.assertFalse(self.pending.path.exists())
        result=json.loads((self.root/'update-result.local.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'],'version_verified')
        self.assertEqual(result['verified_version'],updates.__version__)
    def test_interrupted_download_removes_partial_and_preserves_retry(self):
        release=future_release();self.pending.schedule(release)
        checksum=hashlib.sha256(b'MZfixture').hexdigest()
        class Broken(Response):
            def read(self,n=-1):raise OSError('interrupted')
        with patch.object(updates,'latest_release',return_value=release),patch.object(updates,'urlopen',side_effect=[Response((checksum+'  '+updates.ASSET).encode()),Broken(b'')]):
            with self.assertRaises(updates.UpdateError):self.pending.prepare()
        self.assertEqual(list((self.root/'updates').glob('*.part')),[]);self.assertTrue(self.pending.read())
    def test_cached_installer_rehashed_before_reuse(self):
        release=future_release();payload=b'MZfixture';checksum=hashlib.sha256(payload).hexdigest()
        cache=self.root/'updates';cache.mkdir();target=cache/(release['tag']+'-'+updates.ASSET);target.write_bytes(payload)
        with patch.object(updates,'latest_release',return_value=release),patch.object(updates,'urlopen',return_value=Response((checksum+'  '+updates.ASSET).encode())) as network:
            self.assertEqual(updates.verified_download(release,cache),target);self.assertEqual(network.call_count,1)


class EditionTests(unittest.TestCase):
    def test_channels_cannot_update_each_other(self):
        self.assertFalse(updates.newer('v9.0.0-beta.1','0.4.0'))
        self.assertFalse(updates.newer('v9.0.0','0.4.1-beta.1'))
        self.assertTrue(updates.newer('v0.4.1-beta.2','0.4.1-beta.1'))
        self.assertFalse(updates.newer('v0.4.1-beta.1','0.4.1-beta.2'))
    def test_beta_selects_prereleases_only(self):
        records=[{'tag_name':'v99.0.0','prerelease':False,'draft':False}, {'tag_name':'v0.4.1-beta.2','prerelease':True,'draft':False,'html_url':'https://github.com/MartParty079/GDL/releases/tag/v0.4.1-beta.2','assets':[]}]
        with patch.object(updates,'BETA',True),patch.object(updates,'urlopen',return_value=Response(json.dumps(records).encode())):
            self.assertEqual(updates.latest_release()['tag'],'v0.4.1-beta.2')
    def test_beta_profile_and_research_storage_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LOCALAPPDATA':directory,'FUEL_HUB_DATA_DIR':str(Path(directory)/'production'),'GDL_HUB_BETA_DATA_DIR':directory}),patch.object(edition,'BETA',True),patch.object(edition,'PROFILE_NAME','FuelCellProjectHubBeta'):
            store=Store();self.assertEqual(store.local_dir,Path(directory)/'FuelCellProjectHubBeta')
            locations=ProjectLocations(store);self.assertEqual(locations.value['legacy'],[])
            self.assertTrue(Path(locations.value['active']['root_path']).is_relative_to(store.local_dir))
            locations.value['active']['root_path']=str(Path(directory)/'production')
            with self.assertRaises(ValueError):locations.save(locations.value)
            with self.assertRaises(ValueError):store.connect_storage(Path(directory)/'production')
    def test_identity_ignores_external_backend_configuration(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GDL_BETA_SUPABASE_URL':'https://production.invalid','GDL_BETA_SUPABASE_PUBLISHABLE_KEY':'unused'}):
            accounts=LocalAccounts(Store(local_dir=Path(directory)))
            try:
                accounts.sign_in(accounts.users()[1]['id'])
                self.assertFalse(hasattr(accounts, 'url'))
                self.assertEqual(accounts.profile['role'], 'member')
            finally:accounts.close()
    def test_release_policy_requires_exact_approval_and_correct_branch(self):
        validate=runpy.run_path(str(ROOT/'tools/release_policy.py'))['validate'];sha='a'*40
        validate('beta','develop',sha)
        for branch,approval in [('develop',{'approved_commit':sha,'production_release_order':'APPROVED'}),('main',None),('main',{'approved_commit':'b'*40,'production_release_order':'APPROVED'})]:
            with self.assertRaises(ValueError):validate('stable',branch,sha,approval)
        validate('stable','main',sha,{'approved_commit':sha,'production_release_order':'APPROVED'})
    def test_workflows_cannot_publish_stable_from_development(self):
        beta=(ROOT.parent/'.github/workflows/windows-release.yml').read_text()
        production=(ROOT.parent/'.github/workflows/production-promotion.yml').read_text()
        self.assertIn('branches: [develop]',beta);self.assertIn('--prerelease',beta);self.assertNotIn("tags:",beta)
        self.assertIn('environment: production',production);self.assertIn('APPROVE PRODUCTION RELEASE',production)
        self.assertNotIn('  push:',production)
    def test_installer_preserves_stable_identity_and_refuses_other_folder(self):
        script=(ROOT/'tools/GDLResearchHub.iss').read_text()
        self.assertIn('ACAC162E-8C9A-4F0B-998F-710038B7C32D',script)
        self.assertIn('9DC7B6A1-418F-4CD4-BAB0-A7D96E5189B6',script)
        self.assertIn('Choose a separate installation folder',script)
        self.assertIn('will not downgrade',script)


if __name__=='__main__':unittest.main()
