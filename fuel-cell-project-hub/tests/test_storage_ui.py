import copy
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from app.services.storage import ROOT, Store
from app.services.project_storage import LocalOneDriveProvider, IndexCancelled
from app.ui.storage_panels import RootWizard, IndexWorker
from app.ui.window import HubWindow


class StorageUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "Synced Project"
        self.root.mkdir()
        (self.root / "03_Experiments").mkdir()
        self.store = Store(ROOT, self.base / "profile")
        with patch("app.ui.window.QTimer.singleShot"):
            self.window = HubWindow(self.store)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.wait_for_index()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def wait_for_index(self):
        deadline = time.monotonic() + 15
        while self.window.storage_panel.indexing:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Index worker did not complete")
            time.sleep(0.01)
        self.app.processEvents()

    def connect(self):
        provider = LocalOneDriveProvider(self.root, self.store.local_dir / "index")
        provider.accept_root("Fuel Cell Capstone", self.store.project)
        self.store.connect_storage(self.root)
        self.window.storage_changed()
        self.window.storage_panel.reload_fields()

    def test_settings_and_project_subnavigation(self):
        self.assertEqual(self.window.settings_tabs.tabText(1), "Storage")
        self.assertEqual(self.window.project_tabs.tabText(1), "Files & Data")
        self.assertEqual(self.window.storage_panel.status_label.text(), "Needs Setup")

    def test_wizard_cancel_does_not_write_marker_or_local_root(self):
        wizard = RootWizard(self.store, self.window)
        wizard.root_field.setText(str(self.root))
        wizard.restart()
        self.assertTrue(wizard.validateCurrentPage())
        wizard.reject()
        self.assertFalse((self.root / ".projecthub/project.json").exists())
        self.assertEqual(self.store.local["local_project_root"], "")

    def test_setup_wizard_and_acceptance_search_workflow(self):
        directory = self.root / "03_Experiments/E-20261010-A/R03"
        directory.mkdir(parents=True)
        (directory.parent / "experiment.json").write_text('{"sample_id":"S-001","procedure_id":"P-001"}')
        (directory / "video.mp4").write_bytes(b"sample video")
        (directory / "image.tif").write_bytes(b"sample image")
        archive = self.root / "99_Archive"
        archive.mkdir()
        (archive / "old.csv").write_text("old")
        wizard = RootWizard(self.store, self.window)
        wizard.root_field.setText(str(self.root))
        wizard.restart()
        self.assertTrue(wizard.validateCurrentPage())
        wizard.create_folders.setChecked(True)
        wizard.accept()
        self.assertEqual(self.store.provider.missing_folders(), [])
        self.window.storage_changed()
        self.window.storage_panel.reload_fields()
        self.window.storage_panel.start_index()
        self.wait_for_index()
        self.assertEqual(self.window.storage_panel.status_label.text(), "Connected")
        panel = self.window.files_panel
        panel.search.setText("s-001")
        panel.filters["category"].setCurrentIndex(panel.filters["category"].findData("Video"))
        self.assertEqual(panel.table.rowCount(), 1)
        self.assertEqual(panel.rows[0]["relative_path"], "03_Experiments/E-20261010-A/R03/video.mp4")
        panel.table.selectRow(0)
        with patch("app.services.project_storage.os.startfile") as start:
            panel.open_selected()
            panel.open_parent()
        self.assertEqual(start.call_args_list[0].args[0], str((directory / "video.mp4").resolve()))
        self.assertEqual(start.call_args_list[1].args[0], str(directory.resolve()))
        panel.copy_path()
        self.assertEqual(QApplication.clipboard().text(), panel.rows[0]["relative_path"])

    def test_index_worker_executes_off_ui_thread(self):
        self.connect()
        original = self.store.provider.refresh
        thread_ids = []
        def observe(*args, **kwargs):
            thread_ids.append(threading.get_ident())
            return original(*args, **kwargs)
        with patch.object(self.store.provider, "refresh", observe):
            self.window.storage_panel.start_index()
            self.wait_for_index()
        self.assertTrue(thread_ids)
        self.assertNotEqual(thread_ids[0], threading.get_ident())

    def test_missing_folder_creation_requires_confirmation(self):
        self.connect()
        before = self.store.provider.missing_folders()
        with patch("app.ui.storage_panels.QMessageBox.question", return_value=QMessageBox.No):
            self.window.storage_panel.create_folders()
        self.assertEqual(self.store.provider.missing_folders(), before)
        with patch("app.ui.storage_panels.QMessageBox.question", return_value=QMessageBox.Yes):
            self.window.storage_panel.create_folders()
        self.assertEqual(self.store.provider.missing_folders(), [])

    def test_unavailable_storage_keeps_hub_usable(self):
        self.connect()
        self.root.rename(self.base / "Disconnected")
        self.window.storage_panel.refresh_status()
        self.assertIn("Unavailable", self.window.storage_panel.status_label.text())
        self.assertEqual(self.window.storage_panel.locate_button.text(), "Locate Again")
        for page in self.window.pages:
            self.window.show_page(page)
            self.assertEqual(self.window.tabs.tabText(self.window.tabs.currentIndex()), page)

    def test_index_error_surfaces_without_losing_previous_index(self):
        self.connect()
        (self.root / "03_Experiments/a.csv").write_text("data")
        self.window.storage_panel.start_index()
        self.wait_for_index()
        before = self.store.provider.index_path.read_bytes()
        with patch.object(self.store.provider, "refresh", side_effect=ValueError("Invalid metadata cache")):
            self.window.storage_panel.start_index(True)
            self.wait_for_index()
        self.assertEqual(self.window.storage_panel.status_label.text(), "Index Error")
        self.assertIn("could not be read safely", self.window.storage_panel.error.message.text())
        self.assertTrue(self.window.storage_panel.error.details.isHidden())
        self.assertEqual(self.store.provider.index_path.read_bytes(), before)

    def test_shared_storage_settings_refresh_dashboard_form(self):
        self.connect()
        value = copy.deepcopy(self.store.project)
        value["goal"] = "Shared goal from project metadata"
        self.store.save_project(value)
        self.window.settings_tabs.setCurrentIndex(1)
        self.window.storage_changed()
        self.assertEqual(self.window.fields["goal"].toPlainText(), value["goal"])
        self.assertEqual(self.window.settings_tabs.currentIndex(), 1)

    def test_cancelled_index_returns_to_connected_without_error(self):
        self.connect()
        with patch.object(self.store.provider, "refresh", side_effect=IndexCancelled("Indexing cancelled. Previous index preserved.")):
            self.window.storage_panel.start_index(True)
            self.wait_for_index()
        self.assertEqual(self.window.storage_panel.status_label.text(), "Connected")
        self.assertIn("cancelled", self.window.storage_panel.notice.text())


if __name__ == "__main__":
    unittest.main()
