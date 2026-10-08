import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services.storage import Store, read_json, write_json
from app.services.shared_index import SharedIndex
from app.indexing.index_manager import NativeIndex
from app.services.research_workspace import ResearchWorkspace
from app.services.project_storage import IndexCancelled


class SharedProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'Alice' / 'OneDrive' / 'GDL research - General'
        self.root.mkdir(parents=True)
        (self.root / 'report.txt').write_text('Existing research', encoding='utf-8')
        self.owner = Store(local_dir=self.base / 'Alice' / 'AppData')
        SharedIndex.enroll(self.owner, self.root, confirmed=True)
        self.owner.attach_shared(self.root)
        self.index = NativeIndex(self.owner)
        self.index.refresh()
        self.bob_root = self.base / 'Bob' / 'OneDrive' / 'GDL research - General'
        shutil.copytree(self.root, self.bob_root)
        self.bob = Store(local_dir=self.base / 'Bob' / 'AppData')
        self.bob.attach_shared(self.bob_root)
        self.reader = NativeIndex(self.bob)

    def sync(self):
        shutil.copytree(self.root, self.bob_root, dirs_exist_ok=True)

    def test_two_profiles_same_identity_no_rebuild_and_portable_paths(self):
        self.assertEqual(self.index.locations.value['active']['id'], self.reader.locations.value['active']['id'])
        self.assertFalse(self.bob.shared_index.authority)
        self.assertEqual(self.reader.summary()['current'], 1)
        row = list(self.reader.rows())[0]
        self.assertEqual(self.reader.safe_path(row), self.bob_root / 'report.txt')
        self.assertNotIn(str(self.root), json.dumps(row))
        with self.reader.connect() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM files')
        self.assertFalse((self.bob.local_dir / 'catalog').exists())

    def test_authority_incremental_revision_received_by_reader(self):
        previous = self.bob.shared_index.revision
        (self.root / 'new.txt').write_text('New work', encoding='utf-8')
        self.index.refresh(quick=True)
        self.sync()
        self.assertEqual(self.reader.summary()['current'], 2)
        self.assertNotEqual(previous, self.bob.shared_index.revision)
        self.assertGreaterEqual(len(list((self.root / '.project_hub/index/revisions').glob('*.sqlite3'))), 3)
        self.assertEqual((self.root / 'report.txt').read_text(), 'Existing research')

    def test_partial_sync_corruption_conflict_and_offline_keep_verified(self):
        previous = self.bob.shared_index.revision
        manifest = self.bob_root / '.project_hub/index/project_manifest.json'
        value = read_json(manifest, {})
        value['revision'] = 'b3f4c4fb-712b-4b9a-bf68-97a6a4811e1b'
        write_json(manifest, value)
        self.assertIsNotNone(self.bob.shared_index.load())
        self.assertEqual(previous, self.bob.shared_index.revision)
        write_json(manifest.with_name('project_manifest-conflicted.json'), value)
        self.assertEqual(self.reader.summary()['current'], 1)
        restarted = SharedIndex(self.bob, self.bob_root, self.bob.local['shared_project_id'])
        self.assertIsNotNone(restarted.load())

    def test_cancel_never_publishes_partial_database(self):
        revision = self.owner.shared_index.revision
        with self.assertRaises(IndexCancelled):
            self.index.refresh(cancel=lambda: True)
        self.assertEqual(revision, self.owner.shared_index.manifest()['revision'])
        self.assertFalse(list(self.owner.shared_index.cache.glob('working-*')))

    def test_pending_jobs_idempotent_and_offline_authority(self):
        identity = self.bob.shared_index.submit('refresh', {})
        self.bob.shared_index.submit('refresh', {}, identity)
        self.assertEqual(len(list((self.bob_root / '.project_hub/index/pending').glob('*.json'))), 1)
        with self.assertRaises(ValueError):
            self.bob.shared_index.submit('refresh', {'different': True}, identity)
        shutil.copytree(self.bob_root / '.project_hub/index/pending', self.root / '.project_hub/index/pending')
        self.index.refresh(quick=True)
        self.index.refresh(quick=True)
        with self.index.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM shared_jobs').fetchone()[0], 1)

    def test_normal_user_sample_edit_queued_then_published_once(self):
        with self.assertRaisesRegex(ValueError, 'queued'):
            ResearchWorkspace(self.reader).save('sample', {'name':'Test sample'})
        shutil.copytree(self.bob_root / '.project_hub/index/pending', self.root / '.project_hub/index/pending')
        self.index.refresh(quick=True)
        self.index.refresh(quick=True)
        self.sync()
        self.assertEqual(len(ResearchWorkspace(self.reader).objects('sample')), 1)

    def test_wrong_identity_and_unmarked_folder_never_initialized(self):
        other = self.base / 'Another' / 'GDL research - General'
        other.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.bob.attach_shared(other)
        self.assertFalse((other / '.project_hub').exists())
        third = Store(local_dir=self.base / 'Third')
        SharedIndex.enroll(third, other, confirmed=True)
        with self.assertRaisesRegex(ValueError, 'different project'):
            self.bob.attach_shared(other)

    def test_no_automatic_authority_or_duplicate_enrollment(self):
        with self.assertRaises(ValueError):
            SharedIndex.enroll(self.bob, self.bob_root)
        with self.assertRaises(FileExistsError):
            SharedIndex.enroll(self.bob, self.bob_root, confirmed=True)
        with self.assertRaises(ValueError):
            self.reader.refresh()

    def test_manifest_last_failure_keeps_committed_revision(self):
        revision = self.owner.shared_index.revision
        with patch('app.services.shared_index.write_json', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError):
                self.index.refresh(quick=True)
        self.assertEqual(revision, self.owner.shared_index.manifest()['revision'])
        self.assertEqual(self.reader.summary()['current'], 1)

    def test_project_settings_activity_shared_and_tokens_untouched(self):
        tokens = self.owner.local_dir / 'tokens.bin'
        tokens.write_bytes(b'opaque-session-fixture')
        self.owner.record('Research', 'Contribution')
        self.owner.save_project(self.owner.project)
        self.assertTrue(list((self.root / '.project_hub/logs').glob('*.json')))
        self.assertTrue((self.root / '.project_hub/settings/project_settings.json').exists())
        self.assertFalse((self.owner.local_dir / 'project_settings.json').exists())
        self.assertEqual(tokens.read_bytes(), b'opaque-session-fixture')

    def test_existing_catalog_import_preserves_objects_and_is_once_only(self):
        from tools.configure_shared_project import import_catalog
        ResearchWorkspace(self.index).save('sample', {'name': 'Preserved sample'})
        root = self.base / 'Migration' / 'GDL research - General'
        root.mkdir(parents=True)
        store = Store(local_dir=self.base / 'MigratingUser')
        SharedIndex.enroll(store, root, confirmed=True, project_id=self.owner.shared_index.identity['project_id'])
        store.attach_shared(root)
        before = self.owner.shared_index.digest(self.index.path)
        counts = import_catalog(store.shared_index, self.index.path)
        self.assertEqual(counts['files'], 1)
        self.assertEqual(counts['research_objects'], 1)
        migrated = NativeIndex(store)
        self.assertEqual(ResearchWorkspace(migrated).objects('sample')[0]['name'], 'Preserved sample')
        self.assertEqual(before, self.owner.shared_index.digest(self.index.path))
        with self.assertRaises(ValueError):
            import_catalog(store.shared_index, self.index.path)

    def test_shared_window_startup_reader_does_not_index(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from app.ui.window import HubWindow
        app = QApplication.instance() or QApplication([])
        with patch.object(NativeIndex, 'refresh', side_effect=AssertionError('Reader must not rebuild')), patch('app.ui.window.QTimer.singleShot'):
            window = HubWindow(self.bob)
            window.show()
            app.processEvents()
            window.research_panel.automatic_refresh()
            self.assertFalse(window.research_panel.indexing)
            window.research_panel.start_index(apply_settings=False)
            self.assertIn('queued', window.research_panel.status.text())
            import time
            from PySide6.QtCore import QThread
            deadline = time.monotonic() + 15
            while any(t.isRunning() for t in window.findChildren(QThread)) or window.research_workspace.busy():
                app.processEvents(); time.sleep(.01)
                self.assertLess(time.monotonic(), deadline, 'Workspace workers did not finish')
            window.research_panel.shared_poll.stop()
            window.close()
            window.deleteLater()
            from PySide6.QtCore import QCoreApplication, QEvent
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_missing_or_corrupted_disposable_cache_does_not_become_an_index(self):
        cached = self.bob.shared_index.path
        cached.write_bytes(b'corrupt cache')
        (self.bob_root / '.project_hub/index/project_manifest.json').unlink()
        # No valid committed revision plus no verified cache requires reconnection.
        self.assertIsNone(self.bob.shared_index.load())

    def test_shared_profile_must_not_start_a_second_publisher(self):
        other = SharedIndex(self.owner, self.root, self.owner.local['shared_project_id'])
        with self.owner.shared_index.working():
            with self.assertRaises(ValueError):
                with other.working():
                    self.fail('Concurrent publisher allowed')

    def test_fresh_user_checks_the_pinned_project_identity(self):
        user = Store(local_dir=self.base / 'FreshProfile')
        user.shared_required = True
        user.config_dir = self.base / 'BootstrapConfig'
        write_json(user.config_dir / 'shared_project_public.json', {'project_id':self.owner.shared_index.identity['project_id']})
        user.attach_shared(self.bob_root)
        unrelated = self.base / 'Unrelated' / 'GDL research - General'
        unrelated.mkdir(parents=True)
        SharedIndex.enroll(Store(local_dir=self.base/'UnrelatedProfile'), unrelated, confirmed=True)
        with self.assertRaisesRegex(ValueError, 'different project'):
            user.attach_shared(unrelated)

    def test_personal_views_do_not_publish_or_affect_other_users(self):
        row = list(self.reader.rows())[0]
        revision = self.bob.shared_index.revision
        workspace = ResearchWorkspace(self.reader)
        workspace.viewed(row)
        self.assertEqual(self.reader.query(recent=True)[1], 1)
        workspace.hide(row)
        self.assertEqual(self.reader.query()[1], 0)
        self.assertEqual(self.index.query()[1], 1)
        workspace.restore_hidden()
        self.assertEqual(self.reader.query()[1], 1)
        self.assertEqual(revision, self.bob.shared_index.manifest()['revision'])
