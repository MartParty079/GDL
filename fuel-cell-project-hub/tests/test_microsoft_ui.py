import os
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from app.services.storage import Store, ROOT, write_json, read_json
from app.ui.window import HubWindow


class MicrosoftUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.store = Store(ROOT, self.base / 'profile')
        with patch('app.ui.window.QTimer.singleShot'):
            self.window = HubWindow(self.store)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def fixture_legacy(self):
        project = {'provider': 'MicrosoftGraph', 'site_id': 'site', 'drive_id': 'drive', 'root_item_id': 'folder',
                   'web_url': 'https://university.sharepoint.com/old', 'legacy_project_id': 'LEG-OLD', 'data_origin': 'legacy',
                   'read_only_reference': True, 'name': 'Previous team', 'note': 'Historical pressure reference', 'imported_on': '2025-01-01', 'imported_by': 'user'}
        self.store.project['legacy_projects'] = [project]
        provider = self.window.storage_settings.provider(project)
        provider.index['records'] = [{'id': 'GRAPH-old', 'item_id': 'file', 'parent_item_id': 'folder', 'drive_id': 'drive',
            'relative_path': 'pressure.csv', 'name': 'pressure.csv', 'size': 123, 'modified': '2025-01-01T00:00:00Z',
            'web_url': 'https://university.sharepoint.com/pressure.csv', 'provider': 'MicrosoftGraph', 'is_folder': False,
            'archived': False, 'state': 'active', 'data_origin': 'current', 'experiment_id': '', 'sample_id': ''}]
        write_json(provider.index_path, provider.index)
        self.window.files_panel.reload()
        return project

    def test_root_is_editable_and_core_actions_visible(self):
        panel = self.window.storage_panel
        self.window.open_settings(1)
        self.assertFalse(panel.root.isReadOnly())
        captions = [b.text() for b in panel.findChildren(__import__('PySide6.QtWidgets', fromlist=['QPushButton']).QPushButton)]
        for caption in ('Browse', 'Change folder', 'Validate', 'Reset local mapping', 'Cloud & Old Test Data'):
            self.assertIn(caption, [text.replace('&&', '&') for text in captions])

    def test_account_and_gdl_tabs_are_independent(self):
        self.window.open_analysis_settings()
        self.assertEqual(self.window.settings_tabs.tabText(self.window.settings_tabs.currentIndex()), 'Analysis Tools')
        self.assertEqual(self.window.microsoft_panel.client.text(), '16fbe099-c7ed-4da8-94bf-d8abc1c4c5ec')

    def test_permissions_show_basic_connected_and_sharepoint_admin_block(self):
        auth = self.window.microsoft_auth
        auth.state = 'Connected'
        auth.account = {'display_name': 'Test researcher', 'id': 'test-user'}
        auth.permissions.update(basic='Available', sharepoint='Admin approval required')
        self.window.microsoft_panel.update_identity()
        self.window.cloud_panel.reload()
        text = self.window.microsoft_panel.permissions.text()
        self.assertIn('Microsoft account: Connected', text)
        self.assertIn('Basic Graph access: Available', text)
        self.assertIn('SharePoint cloud indexing: Admin approval required', text)
        self.assertIn('Local OneDrive', text)

    def test_cloud_picker_opens_without_any_graph_or_consent_request(self):
        from app.ui.microsoft_panels import CloudFolderPicker
        from unittest.mock import Mock
        graph = Mock()
        picker = CloudFolderPicker(graph)
        self.assertEqual(picker.tasks, [])
        graph.auth.enable_access.assert_not_called()
        graph.list_sites.assert_not_called()
        graph.list_drives.assert_not_called()
        picker.reject()

    def test_raw_consent_error_is_hidden_even_in_details(self):
        from app.ui.components import ErrorBanner
        banner = ErrorBanner()
        banner.show_error('Microsoft unavailable', 'AADSTS90094 consent_required access_token=secret')
        self.assertNotIn('secret', banner.details.text())
        self.assertNotIn('AADSTS', banner.details.text())

    def test_current_default_excludes_legacy_and_cache_origin_cannot_override(self):
        self.fixture_legacy()
        panel = self.window.files_panel
        self.assertEqual(panel.origin.currentData(), 'current')
        self.assertEqual(panel.table.rowCount(), 0)
        panel.origin.setCurrentIndex(panel.origin.findData('legacy'))
        self.assertEqual(panel.table.rowCount(), 1)
        self.assertIn('Old Test Data', panel.table.item(0, 6).text())
        panel.table.selectRow(0)
        self.assertEqual(panel.selected()['data_origin'], 'legacy')

    def test_legacy_search_note_and_clear_filter(self):
        self.fixture_legacy()
        panel = self.window.files_panel
        panel.origin.setCurrentIndex(1)
        panel.search.setText('Historical reference')
        self.assertEqual(panel.table.rowCount(), 1)
        panel.reload()
        self.assertEqual(panel.origin.currentData(), 'legacy')
        panel.clear_filters()
        self.assertEqual(panel.origin.currentData(), 'current')

    def test_legacy_open_uses_web_without_local_provider(self):
        self.fixture_legacy()
        panel = self.window.files_panel
        panel.origin.setCurrentIndex(1)
        panel.table.selectRow(0)
        with patch('app.services.software.open_resource') as opened:
            panel.open_selected()
            opened.assert_called_once_with('https://university.sharepoint.com/pressure.csv')

    def test_legacy_card_browse_selects_specific_project(self):
        project = self.fixture_legacy()
        self.window.cloud_panel.reload()
        self.window.cloud_panel.projects.setCurrentRow(0)
        self.window.cloud_panel.browse_legacy()
        self.assertEqual(self.window.files_panel.legacy_filter.currentData(), project['legacy_project_id'])
        self.assertEqual(self.window.workspace_section, 'Files & Data')

    def test_cancel_reset_does_not_change_mapping(self):
        self.store.local['local_project_root'] = 'C:/unchanged'
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
            self.window.storage_panel.reset_root()
        self.assertEqual(self.store.local['local_project_root'], 'C:/unchanged')

    def test_corrupt_current_cache_does_not_break_startup_or_local_mode(self):
        project = self.fixture_legacy()
        current = dict(project)
        for key in ('legacy_project_id', 'name', 'note'):
            current.pop(key, None)
        current['data_origin'] = 'current'
        self.store.project['current_cloud_connection'] = current
        provider = self.window.storage_settings.provider(current)
        provider.index_path.parent.mkdir(parents=True, exist_ok=True)
        provider.index_path.write_text('{invalid')
        self.window.cloud_panel.reload()
        self.assertIn('preserved', self.window.cloud_panel.connection.text())
        self.window.files_panel.reload()
        self.assertEqual(len(self.window.files_panel.items), 1)


if __name__ == '__main__':
    unittest.main()
