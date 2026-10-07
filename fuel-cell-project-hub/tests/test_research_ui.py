import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from app.services.storage import Store, ROOT
from app.ui.window import HubWindow


class ResearchUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.current, self.legacy = self.base / 'current', self.base / 'legacy'
        self.current.mkdir()
        self.legacy.mkdir()
        self.store = Store(ROOT, self.base / 'profile')
        with patch('app.ui.window.QTimer.singleShot'):
            self.window = HubWindow(self.store)
        panel = self.window.research_panel
        panel.active.setText(str(self.current))
        panel.legacy.setPlainText(str(self.legacy))
        panel.paths['shared_storage'].setText(str(self.current))
        self.assertTrue(panel.save())

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        self.temp.cleanup()

    def test_background_index_filters_pagination_and_laptop_startup(self):
        for n in range(240):
            (self.current / f'file-{n}.txt').write_text(str(n))
        (self.legacy / 'pressure.csv').write_text('historical')
        panel = self.window.research_panel
        panel.start_index()
        deadline = time.monotonic() + 20
        while panel.indexing:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail('Research indexing did not finish')
            time.sleep(.01)
        files = self.window.files_panel
        self.assertEqual(files.total_matches, 240)
        self.assertEqual(files.table.rowCount(), 200)
        files.change_page(1)
        self.assertEqual(files.table.rowCount(), 40)
        files.origin.setCurrentIndex(files.origin.findData('legacy'))
        self.assertEqual(len(files.rows), 1)
        files.origin.setCurrentIndex(files.origin.findData(''))
        self.assertEqual(files.total_matches, 241)
        self.window.show_research_files('legacy')
        self.window.resize(1024, 700)
        self.window.show()
        self.app.processEvents()
        self.assertEqual(self.window.tabs.count(), 6)
        self.assertFalse((self.current / '.projecthub').exists())
        self.assertFalse((self.legacy / '.projecthub').exists())
        self.window.show_page('Dashboard')
        self.window.open_settings(1)
        self.app.processEvents()

    def test_gui_path_change_keeps_previous_catalog_and_identity(self):
        (self.current / 'data.txt').write_text('current')
        settings = self.window.storage_settings
        settings.catalog.refresh()
        previous_id = settings.locations.value['active']['id']
        new_root = self.base / 'next-project'
        new_root.mkdir()
        self.window.research_panel.active.setText(str(new_root))
        self.assertTrue(self.window.research_panel.save())
        self.assertNotEqual(settings.locations.value['active']['id'], previous_id)
        self.assertEqual(settings.catalog.rows(), [])
        self.assertEqual(len(settings.catalog.rows(all_sources=True)), 1)
        self.assertTrue((self.current / 'data.txt').exists())

    def test_corrupt_catalog_does_not_block_application_start(self):
        path = self.window.storage_settings.catalog.path
        path.write_bytes(b'broken database')
        self.window.storage_settings.connect_catalog()
        self.assertIsNone(self.window.storage_settings.catalog)
        self.assertIn('preserved', self.window.storage_settings.catalog_error)
        self.assertEqual(path.read_bytes(), b'broken database')
        self.window.research_panel.refresh_status()
        self.window.render_dashboard()

    def test_corrupt_record_preserves_database_and_keeps_tools_available(self):
        catalog = self.window.storage_settings.catalog
        with catalog.connect() as db:
            db.execute('INSERT INTO files VALUES (?,?,?)', ('bad', 'bad', '{invalid'))
        self.window.storage_settings.connect_catalog()
        self.assertIsNone(self.window.storage_settings.catalog)
        self.assertIn('preserved', self.window.storage_settings.catalog_error)
        with catalog.connect() as db:
            self.assertEqual(db.execute('SELECT payload FROM files').fetchone()[0], '{invalid')

    def test_advanced_shared_initialization_cannot_write_research_roots(self):
        for root in (self.current, self.legacy, self.base):
            with self.assertRaisesRegex(ValueError, 'research storage'):
                self.window.storage_settings.change_root(str(root), initialize=True)
        self.assertEqual(list(self.current.iterdir()), [])
        self.assertEqual(list(self.legacy.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
