"""Sidebar routing and stable record identity under native table sorting."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QPushButton, QTextBrowser
from app.ui.window import HubWindow
from app.ui.local_accounts import attach_account_ui
from app.ui.theme import appearance_tokens
from tools.ui_design_fixture import create_fixture


class SidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store, self.accounts, self.keys = create_fixture(Path(self.temp.name))
        with patch('app.ui.window.QTimer.singleShot'): self.window = HubWindow(self.store)
        attach_account_ui(self.window, self.accounts, lambda: None)
        self.window.account_timer.stop(); self.window.session_presence.stop()
        self.window.show(); self.app.processEvents()

    def tearDown(self):
        deadline = time.monotonic() + 30
        while self.window.workers or self.window.weekly_panel.tasks.busy() or self.window.meetings_panel.busy():
            self.app.processEvents(); time.sleep(.01)
            if time.monotonic() > deadline: self.fail('Fixture workers failed to settle')
        self.accounts.close(); self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); self.app.processEvents()

    def test_persistent_routes_preserve_member_permissions_and_original_pages(self):
        w = self.window
        self.assertTrue(w.tabs.tabBar().isHidden())
        for control in w.home_panel.category_buttons:
            control.click(); self.app.processEvents()
            self.assertIs(w.tabs.currentWidget(), w.organization_panel)
            self.assertTrue(control.isChecked()); self.assertTrue(w.workspace_rail.isVisible())
            self.assertIn(control.text().replace('&&', '&'), w.workspace_breadcrumb.text())
        w.workspace_rail.home.click()
        self.assertIs(w.tabs.currentWidget(), w.home_panel)
        rail_text = [b.text() for b in w.workspace_rail.findChildren(QPushButton)]
        self.assertNotIn('Team && Activity Audit', rail_text)
        self.assertFalse(w.gdl_settings.isEnabled()); self.assertFalse(hasattr(w, 'admin_workspace'))
        self.assertIn('Files && Analysis', rail_text)
        self.assertIn('Software', w.pages)

    def test_sorted_row_keeps_uuid_metadata_and_selection_after_refresh(self):
        panel = self.window.organization_panel
        self.window.home_panel.navigate('Experimental')
        panel.table.sortItems(1, Qt.DescendingOrder)
        self.assertTrue(panel.select_record(self.keys['sample']))
        self.assertEqual(panel.selected()['uuid'], self.keys['sample'])
        panel.reload()
        self.assertEqual(panel.selected()['uuid'], self.keys['sample'])
        self.assertIn('Carbon paper reference coupon', panel.details.toPlainText())
        self.window.home_panel.open_record(self.keys['procedure'])
        self.assertEqual(panel.selected()['uuid'], self.keys['procedure'])

    def test_keyboard_reaches_primary_dialogs_from_home_in_one_action(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtTest import QTest
        from app.ui.organization import RecordEditor
        from app.ui.intake import IntakeDialog
        self.window.workspace_rail.home.click()
        for caption, expected in (('New Experiment', RecordEditor), ('Register Sample', RecordEditor),
                                  ('Upload Files', IntakeDialog), ('Biweekly Submission', RecordEditor)):
            control = next(b for b in self.window.home_panel.findChildren(QPushButton) if b.text() == caption)
            seen = []
            def close_dialog():
                modal = QApplication.activeModalWidget()
                seen.append(isinstance(modal, expected))
                if modal: modal.reject()
            self.window.home_panel.ensureWidgetVisible(control)
            self.window.activateWindow(); self.app.processEvents()
            control.setFocus(); QTest.qWait(20); self.app.processEvents()
            self.assertTrue(control.hasFocus())
            QTimer.singleShot(150, close_dialog)
            QTest.keyClick(control, Qt.Key_Space)
            self.assertEqual(seen, [True], caption)

    def test_old_metadata_display_does_not_modify_snapshot(self):
        import copy
        service = self.window.organization_panel.service
        service.state['records'][self.keys['goal']]['fields'].pop('due_date')
        service.state['records'][self.keys['period']]['fields'].pop('due_at')
        service.state['records'][self.keys['experiment']]['fields'].pop('procedure_revision')
        before = copy.deepcopy(service.state)
        self.window.home_panel.reload()
        self.assertIn('Not scheduled', self.window.home_panel.cards['Current Goal'][1].toPlainText())
        self.assertIn('exact published procedure revision', self.window.home_panel.cards['Active Procedure & Parameters'][1].toPlainText())
        self.assertEqual(before, service.state)

    def test_enlarged_controls_remain_scrollable_and_offline_health_visible(self):
        from PySide6.QtTest import QTest
        self.store.local.update(text_scale=200)
        account = self.window.findChild(QPushButton, 'current-user')
        name = 'Aleksandra Wiśniewska-Kowalczyk — Research Documentation Coordinator · MEMBER'
        account.setText(name)
        self.window.resize(1366, 768); self.window.apply_theme()
        self.window.home_panel.navigate('Experimental'); QTest.qWait(50)
        panel = self.window.organization_panel
        self.assertTrue(self.window.workspace_header.stacked)
        self.assertGreaterEqual(self.window.global_search.width(), 220)
        self.assertEqual(account.toolTip(), name); self.assertEqual(account.accessibleName(), name)
        self.assertGreaterEqual(panel.table.height(), 160)
        self.assertGreater(panel.controls_scroll.verticalScrollBar().maximum(), 0)
        edit = next(b for b in panel.findChildren(QPushButton) if b.text() == 'Edit metadata')
        panel.controls_scroll.ensureWidgetVisible(edit); self.app.processEvents()
        visible = edit.visibleRegion()
        self.assertFalse(visible.isEmpty())
        panel.service.status = 'Offline/possibly stale · last-known-good snapshot'
        self.window.home_panel.reload()
        self.assertIn('Offline/possibly stale', self.window.banner.text())
        self.assertTrue(self.window.banner.isVisible())

    def test_appearance_is_local_and_high_contrast_uses_native_controls(self):
        self.store.local.update(appearance='dark', text_scale=200)
        self.window.apply_theme(); self.app.processEvents()
        self.assertIn('font-size: 26px', self.window.styleSheet())
        self.assertEqual(appearance_tokens(self.window).BACKGROUND_PRIMARY, '#171C24')
        with patch('app.ui.theme.high_contrast_enabled', return_value=True):
            self.window.apply_theme()
            self.assertNotIn('background:', self.window.styleSheet())
        self.store.local['text_scale'] = 'old-invalid-setting'
        self.window.apply_theme()
        self.assertIn('font-size: 13px', self.window.styleSheet())
        self.assertTrue(all(v.isReadOnly() for v in self.window.home_panel.findChildren(QTextBrowser)))

if __name__ == '__main__': unittest.main()
