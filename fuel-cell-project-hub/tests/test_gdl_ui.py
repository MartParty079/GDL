"""GDL UI acceptance with isolated settings and mocked external processes."""
import copy
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from app.services.storage import ROOT, Store
from app.services.gdl_analysis import GDLAnalysisService
from app.ui.window import HubWindow


class GDLUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        fixture = self.base / "app"
        (fixture / "config").mkdir(parents=True)
        for name in ("project_defaults.json", "software_manifest.json"):
            shutil.copyfile(ROOT / "config" / name, fixture / "config" / name)
        self.store = Store(fixture, self.base / "local")
        fiji = self.base / "Fiji/fiji-windows-x64.exe"
        fiji.parent.mkdir()
        fiji.write_bytes(b"fixture")
        (fiji.parent / "jars").mkdir()
        (fiji.parent / "plugins").mkdir()
        jmp = self.base / "JMP/jmp.exe"
        jmp.parent.mkdir()
        jmp.write_bytes(b"fixture")
        self.input = self.base / "input"
        self.input.mkdir()
        self.output = self.base / "output"
        GDLAnalysisService(self.store).registry.save_paths({"fiji_executable": str(fiji), "jmp_executable": str(jmp),
            "default_input_folder": str(self.input), "default_output_folder": str(self.output)},
            input_mode="Configured folder", output_mode="Custom configured folder")
        with patch("app.ui.window.QTimer.singleShot"):
            self.window = HubWindow(self.store)
        self.window.show()
        self.app.processEvents()

    def drain(self):
        deadline = time.monotonic() + 15
        while self.window.workers:
            self.app.processEvents()
            if time.monotonic() > deadline:
                raise TimeoutError("Background UI operation did not finish")
            time.sleep(0.01)
        self.app.processEvents()

    def tearDown(self):
        self.window.gdl_panel.timer.stop()
        self.drain()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def test_analysis_navigation_and_editable_path_controls(self):
        self.window.open_workspace("Analysis")
        self.assertEqual(self.window.project_tabs.currentIndex(), 2)
        selected = [b.property("workspacePage") for b in self.window.project_sidebar.findChildren(QPushButton) if b.isChecked()]
        self.assertEqual(selected, ["Analysis"])
        self.window.open_analysis_settings()
        self.drain()
        self.assertEqual(self.window.settings_tabs.tabText(self.window.settings_tabs.currentIndex()), "Analysis Tools")
        self.assertEqual(len(self.window.gdl_settings.fields), 10)
        self.assertTrue(all(not field.isReadOnly() for field in self.window.gdl_settings.fields.values()))

    def test_declining_clean_fiji_warning_never_launches_process(self):
        with patch("app.ui.gdl_panels.QMessageBox.question", return_value=QMessageBox.No) as question, patch("app.services.gdl_analysis.subprocess.Popen") as process:
            self.window.gdl_panel.launch()
        self.assertIn("close all open Fiji", question.call_args.args[2])
        process.assert_not_called()

    def test_full_adapter_flow_from_button_without_real_fiji(self):
        process = Mock(pid=4321)
        process.poll.return_value = None
        with patch("app.ui.gdl_panels.QMessageBox.question", return_value=QMessageBox.Yes), patch("app.services.gdl_analysis.subprocess.Popen", return_value=process):
            self.window.gdl_panel.launch()
            self.drain()
        self.assertEqual(self.window.gdl_service.session["state"], "STARTING")
        self.assertIn("Starting", self.window.gdl_panel.state.text())
        self.window.gdl_panel.timer.stop()
        self.window.gdl_panel.stop()
        self.drain()
        self.assertIn("Monitoring stopped", self.window.gdl_panel.state.text())
        process.terminate.assert_not_called()

    def test_invalid_edited_path_has_inline_validation_and_no_save(self):
        settings = self.window.gdl_settings
        original = copy.deepcopy(self.store.local)
        settings.fields["jmp_executable"].setText(str(self.base / "missing.exe"))
        settings.apply()
        self.drain()
        self.assertEqual(settings.fields["jmp_executable"].property("state"), "error")
        self.assertIn("JMP", settings.statuses["jmp_executable"].text())
        self.assertEqual(self.store.local, original)

    def test_technical_failure_details_stay_collapsed(self):
        self.window.gdl_panel.display_status({"state": "FAILED", "message": "Check paths and retry.", "details": "Traceback: private engine internals"})
        self.assertNotIn("Traceback", self.window.gdl_panel.run_detail.text())
        self.assertTrue(self.window.gdl_panel.error.details.isHidden())

    def test_reopened_failed_session_resumes_watchdog_polling(self):
        self.window.gdl_service.session = {"state": "FAILED", "status_file": str(self.base / "status.json"), "message": "Retrying"}
        self.window.gdl_panel.refresh()
        self.assertTrue(self.window.gdl_panel.timer.isActive())
        self.window.gdl_panel.timer.stop()

    def test_corrupt_gdl_settings_do_not_break_other_pages(self):
        self.window.gdl_service.registry.config_path.write_text("broken JSON")
        with patch("app.ui.window.QTimer.singleShot"):
            other = HubWindow(Store(self.store.root, self.store.local_dir))
        try:
            self.assertTrue(other.gdl_service.registry.config_error)
            for name in other.pages:
                other.show_page(name)
        finally:
            other.close()
            other.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
