"""Test launcher controls and state transitions without opening external apps."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QFrame, QPushButton
from app.services.storage import Store, ROOT
from app.ui.window import HubWindow


class LauncherUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        store = Store(ROOT, Path(self.temp.name))
        # Suppress scheduled checks; launch behavior is tested explicitly.
        with patch("app.ui.window.QTimer.singleShot"):
            self.window = HubWindow(store)
        self.window.results = {i["id"]: {"path": "", "target": i.get("launch_target", ""), "status": "Needs test" if i.get("launch_type") == "uri" else "Ready", "source": "Test"} for i in store.manifest}
        self.window.render_software()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def item(self, key):
        return next(i for i in self.window.store.manifest if i["id"] == key)

    def buttons(self, key):
        frame = next(f for f in self.window.pages["Software"].findChildren(QFrame) if f.property("softwareId") == key)
        return {b.text(): b for b in frame.findChildren(QPushButton)}

    def test_type_specific_controls(self):
        self.assertIn("Test Launch", self.buttons("teams"))
        self.assertNotIn("Locate application", self.buttons("teams"))
        self.assertIn("Locate application", self.buttons("jmp"))
        self.assertIn("Open", self.buttons("github_web"))
        self.assertNotIn("Locate application", self.buttons("github_web"))

    def test_teams_success_updates_readiness_and_survives_rescan(self):
        with patch("app.services.software.os.startfile") as start:
            self.buttons("teams")["Test Launch"].click()
        start.assert_called_once_with("msteams://")
        self.assertEqual(self.window.results["teams"]["status"], "Ready")
        new_scan = dict(self.window.results)
        new_scan["teams"] = {"path": "", "target": "msteams://", "source": "Unverified", "status": "Needs test"}
        self.window.scan_done(new_scan)
        self.assertEqual(self.window.results["teams"]["status"], "Ready")

    def test_teams_failure_shows_recovery_and_changes_status(self):
        with patch("app.services.software.os.startfile", side_effect=OSError("No handler")), patch("app.ui.window.QMessageBox.exec", return_value=0), patch("app.ui.window.QMessageBox.addButton", autospec=True) as add:
            self.window.launch_item(self.item("teams"))
        self.assertEqual(self.window.results["teams"]["status"], "Launch failed")
        captions = [call.args[0] for call in add.call_args_list]
        self.assertIn("Open Teams Download Page", captions)
        self.assertIn("Retry", captions)

    def test_locate_is_noop_for_protocol_and_web_entries(self):
        with patch("app.ui.window.QFileDialog.getOpenFileName") as locator:
            self.window.locate(self.item("teams"))
            self.window.locate(self.item("github_web"))
        locator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
