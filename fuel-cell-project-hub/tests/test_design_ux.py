"""Behavioral coverage for the design system and UX states."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton
from app.services.storage import ROOT, Store
from app.services.project_storage import LocalOneDriveProvider
from app.ui.window import HubWindow
from app.ui.components import Button, ResponsiveCards, AppCard, friendly_error, local_datetime


class DesignUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.store = Store(ROOT, self.base / "local")
        with patch("app.ui.window.QTimer.singleShot"):
            self.window = HubWindow(self.store)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def connect(self):
        root = self.base / "Project"
        root.mkdir()
        (root / "03_Experiments").mkdir()
        provider = LocalOneDriveProvider(root, self.store.local_dir / "index")
        provider.accept_root("Project", self.store.project)
        self.store.connect_storage(root)
        return root

    def test_settings_are_grouped_and_storage_index_preserved(self):
        names = [self.window.settings_tabs.tabText(i) for i in range(self.window.settings_tabs.count())]
        self.assertEqual(names, ["General", "Storage", "Software", "Project resources", "Updates", "History", "Analysis Tools"])
        self.assertIn("goal", self.window.fields)

    def test_unconnected_files_have_actionable_empty_state(self):
        panel = self.window.files_panel
        self.assertEqual(panel.empty_state.title, "Connect project storage")
        panel.empty_state.state_button.click()
        self.assertEqual(self.window.tabs.tabText(self.window.tabs.currentIndex()), "Settings")
        self.assertEqual(self.window.settings_tabs.currentIndex(), 1)

    def test_search_empty_state_and_clear_filters(self):
        root = self.connect()
        (root / "03_Experiments/data.csv").write_text("data")
        self.store.provider.refresh()
        panel = self.window.files_panel
        panel.reload()
        panel.search.setText("not-found")
        self.assertEqual(panel.empty_state.title, "No matching files")
        self.assertTrue(panel.table.isHidden())
        panel.empty_state.state_button.click()
        self.assertEqual(panel.search.text(), "")
        self.assertEqual(panel.table.rowCount(), 1)
        self.assertTrue(panel.search.isClearButtonEnabled())

    def test_sorting_retains_correct_open_target(self):
        root = self.connect()
        small = root / "03_Experiments/a.csv"
        large = root / "03_Experiments/z.csv"
        small.write_bytes(b"a")
        large.write_bytes(b"z" * 100)
        self.store.provider.refresh()
        panel = self.window.files_panel
        panel.reload()
        panel.table.sortItems(5, Qt.DescendingOrder)
        panel.table.selectRow(0)
        self.assertEqual(panel.selected()["name"], "z.csv")
        with patch("app.services.project_storage.os.startfile") as start:
            panel.open_selected()
        start.assert_called_once_with(str(large.resolve()))

    def test_loading_shows_skeleton_or_last_known_data(self):
        panel = self.window.files_panel
        panel.set_loading(True)
        self.assertFalse(panel.skeleton.isHidden())
        self.assertTrue(panel.empty_state.isHidden())
        panel.set_loading(False)
        self.assertTrue(panel.skeleton.isHidden())
        self.assertFalse(panel.empty_state.isHidden())

    def test_recoverable_error_is_inline_and_details_hidden(self):
        def fail():
            raise PermissionError("[WinError 5] Access is denied: C:/private/file")
        with patch("app.ui.window.QMessageBox.warning") as modal:
            self.window.guard(fail)
        modal.assert_not_called()
        self.assertNotIn("WinError", self.window.global_error.message.text())
        self.assertIn("retry", self.window.global_error.message.text())
        self.assertTrue(self.window.global_error.details.isHidden())

    def test_update_check_failure_is_nonmodal_and_other_pages_work(self):
        self.window.update_checking = True
        self.window.update_failed("[WinError 10013] Network denied")
        self.assertNotIn("WinError", self.window.update_status.text())
        for page in self.window.pages:
            self.window.show_page(page)
            self.assertEqual(self.window.tabs.tabText(self.window.tabs.currentIndex()), page)

    def test_update_available_uses_notification_without_downloading(self):
        with patch("app.ui.window.QMessageBox.exec") as modal, patch("app.ui.window.open_resource") as open_url:
            self.window.update_done({"tag": "v0.2.0", "url": "https://github.com/team/repo/releases/tag/v0.2.0", "name": "0.2.0"})
        modal.assert_not_called()
        open_url.assert_not_called()
        self.assertIn("Update available", self.window.toasts.message.text())
        self.assertFalse(self.window.release_button.isHidden())

    def test_personal_update_preference_saves_without_confirmation(self):
        with patch("app.ui.window.QMessageBox.question") as question:
            self.window.update_toggle.setChecked(False)
        question.assert_not_called()
        self.assertFalse(Store(ROOT, self.store.local_dir).local["check_updates_at_startup"])

    def test_shared_changes_still_require_confirmation(self):
        self.window.fields["goal"].setPlainText("New goal")
        with patch("app.ui.window.QMessageBox.question", return_value=QMessageBox.No) as question:
            self.window.apply_settings()
        question.assert_called_once()
        self.assertEqual(self.store.project["goal"], "")

    def test_button_loading_restores_label_and_keyboard_target(self):
        control = Button("Refresh index")
        control.set_loading(True, "Refreshing…")
        self.assertFalse(control.isEnabled())
        self.assertEqual(control.text(), "Refreshing…")
        control.set_loading(False)
        self.assertTrue(control.isEnabled())
        self.assertEqual(control.text(), "Refresh index")
        self.assertGreaterEqual(control.minimumHeight(), 40)

    def test_workspace_navigation_and_sidebar_selection(self):
        self.window.open_workspace("Files & Data")
        self.assertEqual(self.window.tabs.tabText(self.window.tabs.currentIndex()), "Project")
        self.assertEqual(self.window.project_tabs.currentIndex(), 1)
        controls = self.window.project_sidebar.findChildren(QPushButton)
        selected = [c.property("workspacePage") for c in controls if c.isChecked()]
        self.assertEqual(selected, ["Files & Data"])
        self.window.open_workspace("Overview")
        self.assertEqual(self.window.tabs.tabText(self.window.tabs.currentIndex()), "Dashboard")

    def test_filters_survive_reload_and_workspace_return(self):
        root = self.connect()
        (root / "03_Experiments/sample.mp4").write_bytes(b"video")
        self.store.provider.refresh()
        panel = self.window.files_panel
        panel.reload()
        panel.search.setText("sample")
        panel.filters["category"].setCurrentIndex(panel.filters["category"].findData("Video"))
        self.window.open_workspace("Files & Data")
        panel.reload()
        self.assertEqual(panel.search.text(), "sample")
        self.assertEqual(panel.filters["category"].currentData(), "Video")

    def test_reports_filter_survives_empty_index_refresh(self):
        self.window.open_workspace("Reports")
        self.window.files_panel.reload()
        self.assertEqual(self.window.files_panel.filters["category"].currentData(), "Report")
        selected = [c.property("workspacePage") for c in self.window.project_sidebar.findChildren(QPushButton) if c.isChecked()]
        self.assertEqual(selected, ["Reports"])

    def test_readable_dates_and_error_messages(self):
        self.assertNotIn("T", local_datetime("2026-10-06T20:42:00+00:00"))
        self.assertNotIn("Traceback", friendly_error("Traceback: OSError [WinError 123]"))

    def test_cards_stack_at_narrow_workspace_width(self):
        cards = ResponsiveCards([AppCard("One"), AppCard("Two")])
        cards.resize(500, 300)
        cards.show()
        self.app.processEvents()
        self.assertEqual(cards.columns, 1)
        cards.close()

    def test_minimum_laptop_layout_preserves_global_navigation(self):
        self.window.resize(1024, 700)
        self.window.show_page("Dashboard")
        self.app.processEvents()
        self.assertEqual(self.window.width(), 1024)
        self.assertEqual(self.window.tabs.count(), 6)
        self.assertLessEqual(self.window.tabs.tabBar().sizeHint().width(), self.window.width())
        cards = self.window.pages["Dashboard"].findChildren(AppCard)
        for card in cards:
            self.assertGreaterEqual(card.height(), card.layout().minimumSize().height())

    def test_file_actions_fit_standard_window(self):
        root = self.connect()
        (root / "03_Experiments/data.csv").write_text("data")
        self.store.provider.refresh()
        self.window.files_panel.reload()
        self.window.open_workspace("Files & Data")
        self.app.processEvents()
        actions = self.window.files_panel.file_actions
        position = actions.mapTo(self.window, actions.rect().bottomLeft())
        self.assertLess(position.y(), self.window.height() - 20)


if __name__ == "__main__":
    unittest.main()
