import copy
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.storage import Store, ROOT, write_json, read_json
from app.services.project_storage import LocalOneDriveProvider, IndexCancelled, search_items, validate_shared_settings
from app.services.microsoft_auth import MicrosoftAuth, AuthError, SCOPES, TIER_SCOPES
from app.services.microsoft_graph import MicrosoftGraphClient, GraphError
from app.services.microsoft_graph_provider import MicrosoftGraphProvider
from app.services.storage_settings import StorageSettings, FOLDERS
from app.services.file_classifier import classify_file
from app.services.path_registry import PathRegistry


class GraphStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.app_root = self.base / 'app'
        self.app_root.mkdir()
        (self.app_root / 'config').mkdir()
        write_json(self.app_root / 'config/project_defaults.json', read_json(ROOT / 'config/project_defaults.json', {}))
        self.store = Store(self.app_root, self.base / 'profile')
        self.auth = Mock()
        self.auth.get_access_token.return_value = 'DO-NOT-LOG-THIS-TOKEN'
        self.auth.connection_status.return_value = 'Connected'
        self.auth.get_account.return_value = {'id': 'user-1'}
        self.graph = Mock(auth=self.auth)
        self.graph.get_drive_item.return_value = {'id': 'folder-root', 'name': 'Old Rig', 'folder': {}, 'webUrl': 'https://university.sharepoint.com/old'}
        self.settings = StorageSettings(self.store, self.graph)
        self.selection = {'drive_id': 'drive-1', 'root_item_id': 'folder-root', 'site_id': 'site-1'}

    def tearDown(self):
        self.temp.cleanup()

    def local_root(self, name='Project'):
        root = self.base / name
        root.mkdir()
        provider = LocalOneDriveProvider(root, self.store.local_dir / 'index')
        provider.accept_root('Test project', self.store.project, allow_unmarked=True)
        self.store.connect_storage(root)
        return root

    def item(self, name='pressure.csv', item_id='file-1', folder=False):
        return {'id': item_id, 'name': name, 'size': 123, 'lastModifiedDateTime': '2026-01-01T12:00:00Z',
                'createdDateTime': '2025-01-01T12:00:00Z', 'webUrl': 'https://university.sharepoint.com/' + name,
                'folder' if folder else 'file': {}}

    def test_metadata_pagination_and_get_only(self):
        request = Mock(side_effect=[(200, {}, {'value': [{'id': '1'}], '@odata.nextLink': 'https://graph.microsoft.com/v1.0/me/drives?$skiptoken=x'}), (200, {}, {'value': [{'id': '2'}]})])
        client = MicrosoftGraphClient(self.auth, request)
        self.assertEqual([i['id'] for i in client.list_drives()], ['1', '2'])
        self.assertEqual(request.call_count, 2)

    def test_pagination_cannot_exfiltrate_token(self):
        request = Mock(return_value=(200, {}, {'value': [], '@odata.nextLink': 'https://attacker.example/v1.0/me/drives'}))
        with self.assertRaises(GraphError):
            MicrosoftGraphClient(self.auth, request).list_drives()
        self.assertEqual(request.call_count, 1)

    def test_content_endpoints_rejected_before_token(self):
        client = MicrosoftGraphClient(self.auth, Mock())
        for path in ('drives/x/items/y/content', 'drives/x/items/y/%63ontent', 'https://graph.microsoft.com:443/v1.0/me', 'https://graph.microsoft.com/v1.0/drives/x/items/y/$value'):
            with self.assertRaises(GraphError):
                client.get(path)
        self.auth.get_access_token.assert_not_called()

    def test_graph_selects_scope_tier_for_each_resource(self):
        client = MicrosoftGraphClient(self.auth, Mock(return_value=(200, {}, {'value': []})))
        client.get_me()
        self.auth.get_access_token.assert_called_with('basic')
        client.list_drives()
        self.auth.get_access_token.assert_called_with('files')
        client.list_sites('Fuel Cell')
        self.auth.get_access_token.assert_called_with('sharepoint')
        client.register_connection(self.selection)
        client.list_children('drive-1')
        self.auth.get_access_token.assert_called_with('sharepoint')
        self.auth.enable_access.assert_not_called()

    def test_cloudonly_falls_back_to_local_when_permission_is_blocked(self):
        root = self.local_root()
        (root / 'local_pressure.csv').write_text('test')
        self.store.provider.refresh()
        self.settings.connect_cloud(self.selection)
        self.settings.set_mode('CloudOnly')
        self.auth.permission_status.return_value = {'basic': 'Available', 'files': 'Not enabled', 'sharepoint': 'Admin approval required'}
        self.assertIn('local_pressure.csv', [item['name'] for item in self.settings.files()])
        self.assertEqual(self.store.local['storage_mode'], 'CloudOnly')
        self.auth.enable_access.assert_not_called()

    def test_retry_and_permission_errors_hide_tokens(self):
        sleep = Mock()
        request = Mock(side_effect=[(429, {'Retry-After': '2'}, {}), (503, {'Retry-After': '1'}, {}), (200, {}, {'id': 'me'})])
        self.assertEqual(MicrosoftGraphClient(self.auth, request, sleep).get_me()['id'], 'me')
        self.assertEqual(sleep.call_count, 3)
        request = Mock(side_effect=RuntimeError('DO-NOT-LOG-THIS-TOKEN'))
        with self.assertRaises(GraphError) as caught:
            MicrosoftGraphClient(self.auth, request).get_me()
        self.assertNotIn('DO-NOT-LOG', str(caught.exception))
        with self.assertRaisesRegex(GraphError, 'Admin approval'):
            MicrosoftGraphClient(self.auth, Mock(return_value=(403, {}, {}))).get_me()

    def test_throttle_cancellation(self):
        calls = [False, True]
        with self.assertRaises(IndexCancelled):
            MicrosoftGraphClient(self.auth, Mock(return_value=(429, {}, {})), Mock()).get('me', cancel=lambda: calls.pop(0))

    def test_legacy_import_is_permanent_and_duplicate_checked(self):
        project = self.settings.connect_cloud(self.selection, legacy=True, name='Past team')
        self.assertTrue(project['legacy_project_id'].startswith('LEG-'))
        self.assertEqual(project['data_origin'], 'legacy')
        self.assertTrue(project['read_only_reference'])
        self.assertEqual(project['imported_by'], 'user-1')
        with self.assertRaisesRegex(ValueError, 'already'):
            self.settings.connect_cloud(self.selection, legacy=True)
        with self.assertRaisesRegex(ValueError, 'historical'):
            self.settings.connect_cloud(self.selection)
        validate_shared_settings(self.store.project)

    def test_current_and_legacy_cannot_be_same_root(self):
        self.settings.connect_cloud(self.selection)
        with self.assertRaisesRegex(ValueError, 'current'):
            self.settings.connect_cloud(self.selection, legacy=True)

    def test_legacy_refresh_metadata_classification_and_offline_search(self):
        project = self.settings.connect_cloud(self.selection, legacy=True, name='2025 team', note='Water breakthrough comparison')
        self.graph.list_children.return_value = [self.item()]
        provider = self.settings.provider(project)
        provider.refresh()
        self.auth.connection_status.return_value = 'Signed Out'
        files = self.settings.files()
        self.assertEqual(files[0]['subcategory'], 'Pressure')
        self.assertEqual(len(search_items(files, query='2025 breakthrough', origin='legacy')), 1)
        self.assertEqual(search_items(files, origin='current'), [])
        self.assertIn('Cached', self.settings.provider(project).summary()['status'])
        self.graph.get_drive_item.assert_called()
        self.graph.list_children.assert_called()

    def test_nested_failure_retains_cached_descendants(self):
        project = self.settings.connect_cloud(self.selection, legacy=True)
        provider = self.settings.provider(project)
        self.graph.list_children.side_effect = [[self.item('rig', 'sub', True)], [self.item()]]
        provider.refresh()
        self.graph.list_children.side_effect = [[self.item('rig', 'sub', True)], GraphError('Access denied')]
        summary = provider.refresh()
        self.assertEqual(summary['files'], 1)
        self.assertTrue(provider.get_item('rig/pressure.csv')['scan_unverified'])
        self.assertEqual(len(summary['warnings']), 1)

    def test_cancel_and_root_failure_preserve_previous_index(self):
        project = self.settings.connect_cloud(self.selection, legacy=True)
        provider = self.settings.provider(project)
        self.graph.list_children.return_value = [self.item()]
        provider.refresh()
        old = provider.index_path.read_bytes()
        with self.assertRaises(IndexCancelled):
            provider.refresh(cancel=lambda: True)
        self.assertEqual(provider.index_path.read_bytes(), old)
        self.graph.get_drive_item.side_effect = GraphError('Folder removed')
        with self.assertRaises(GraphError):
            provider.refresh()
        self.assertEqual(provider.index_path.read_bytes(), old)

    def test_duplicate_relative_names_across_legacy_projects(self):
        first = self.settings.connect_cloud(self.selection, True, 'First')
        self.graph.get_drive_item.return_value['id'] = 'another-root'
        second = self.settings.connect_cloud(dict(self.selection, root_item_id='another-root', drive_id='drive-2'), True, 'Second')
        self.graph.list_children.return_value = [self.item()]
        self.settings.provider(first).refresh()
        self.settings.provider(second).refresh()
        files = self.settings.files()
        self.assertEqual(len(files), 2)
        self.assertNotEqual(files[0]['id'], files[1]['id'])
        self.assertEqual(len(search_items(files, legacy_project=second['legacy_project_id'])), 1)

    def test_edit_note_and_manual_override_survive_refresh(self):
        project = self.settings.connect_cloud(self.selection, True)
        self.graph.list_children.return_value = [self.item()]
        self.settings.provider(project).refresh()
        item = self.settings.files()[0]
        self.settings.set_override(item, {'category': 'Report', 'subcategory': 'Lab Report', 'sample_id': 'S-044', 'legacy_note': 'Chosen reference'})
        self.settings.edit_note(project['legacy_project_id'], 'Updated project note')
        project = self.store.project['legacy_projects'][0]
        self.settings.provider(project).refresh()
        item = self.settings.files()[0]
        self.assertEqual((item['category'], item['sample_id'], item['legacy_note']), ('Report', 'S-044', 'Chosen reference'))
        self.assertEqual(item['data_origin'], 'legacy')

    def test_root_change_and_reset_keep_cloud_legacy_and_files(self):
        old_root = self.local_root()
        file = old_root / 'data.csv'
        file.write_text('unchanged')
        project = self.settings.connect_cloud(self.selection, True)
        new_root = self.base / 'New mapping'
        new_root.mkdir()
        self.settings.change_root(new_root, initialize=True)
        self.assertEqual(self.store.project['legacy_projects'][0]['legacy_project_id'], project['legacy_project_id'])
        self.assertEqual(file.read_text(), 'unchanged')
        self.assertFalse((new_root / 'data.csv').exists())
        self.settings.reset_root()
        reloaded = Store(self.app_root, self.store.local_dir)
        self.assertEqual(reloaded.local['local_project_root'], '')
        self.assertEqual(reloaded.project['legacy_projects'][0]['legacy_project_id'], project['legacy_project_id'])

    def test_wrong_project_root_rejected_without_changes(self):
        self.local_root()
        other = self.base / 'Other'
        other.mkdir()
        LocalOneDriveProvider(other, self.base / 'other-cache').accept_root('Other', {}, True)
        before = copy.deepcopy(self.store.local)
        with self.assertRaisesRegex(ValueError, 'another project'):
            self.settings.change_root(other)
        self.assertEqual(self.store.local, before)

    def test_folder_mappings_are_portable_and_drive_gdl_defaults(self):
        root = self.local_root()
        folders = dict(FOLDERS, **{'Raw Data': 'custom/raw', 'Reports': 'custom/reports'})
        self.settings.save_folders(folders)
        registry = PathRegistry(self.store)
        self.assertEqual(registry.resolve('default_input_folder'), str(root / 'custom/raw'))
        self.assertEqual(registry.resolve('report_output_folder'), str(root / 'custom/reports'))
        with self.assertRaises(ValueError):
            self.settings.save_folders(dict(folders, Reports='../outside'))

    def test_cache_change_keeps_old_snapshot_searchable(self):
        project = self.settings.connect_cloud(self.selection, True)
        self.graph.list_children.return_value = [self.item()]
        provider = self.settings.provider(project)
        provider.refresh()
        new = self.base / 'new-cache'
        self.settings.set_legacy_cache(new)
        self.assertTrue(provider.index_path.exists())
        self.assertFalse(new.exists())
        self.assertEqual(len(self.settings.files()), 1)
        self.settings.provider(project).refresh()
        self.assertTrue(new.exists())
        self.assertTrue(provider.index_path.exists())

    def test_hybrid_open_prefers_existing_local_file(self):
        root = self.local_root()
        (root / 'pressure.csv').write_text('contents')
        self.store.provider.refresh()
        connection = self.settings.connect_cloud(self.selection)
        self.graph.list_children.return_value = [self.item()]
        self.settings.provider(connection).refresh()
        self.settings.set_mode('Hybrid')
        item = dict(self.item(), provider='MicrosoftGraph', relative_path='pressure.csv', web_url='https://example.com/x')
        with patch.object(self.store.provider, 'open_item') as opened:
            self.settings.open_item(item)
            opened.assert_called_once_with('pressure.csv')

    def test_cloud_read_only_provider_rejects_writes(self):
        provider = self.settings.provider(self.settings.connect_cloud(self.selection, True))
        with self.assertRaisesRegex(ValueError, 'read-only'):
            provider.create_missing_folders()
        with self.assertRaises(ValueError):
            provider.save_project({}, {})

    def test_shared_settings_reject_credentials_and_absolute_folders(self):
        for value in ({'access_token': 'secret'}, {'storage': {'refresh_token': 'secret'}}, {'project_folders': {'Reports': 'C:/outside'}}):
            with self.assertRaises(ValueError):
                validate_shared_settings(value)

    def test_classifier_precedence_and_no_fabricated_ids(self):
        self.assertEqual(classify_file('01_Procedures/start.docx')['category'], 'Procedure')
        self.assertEqual(classify_file('07_Reports/results.pdf')['category'], 'Report')
        self.assertEqual(classify_file('08_Reference/paper.pdf')['category'], 'Reference')
        self.assertEqual(classify_file('04_Raw_Data/pressure.csv')['category'], 'Sensor Data')
        self.assertEqual(classify_file('04_Raw_Data/pre_imaging/image.tif')['subcategory'], 'Pre Imaging')
        self.assertEqual(classify_file('temperature_log.txt')['category'], 'Sensor Data')
        self.assertEqual(classify_file('01_Procedures/a.pdf', {'category': 'Document'}, {'category': 'Report'})['category'], 'Report')
        self.assertEqual(classify_file('2025 team/Test 1/foam_5/image.tif')['sample_id'], '')
        self.assertEqual(classify_file('data/E-001_pressure.csv')['experiment_id'], 'E-001')


class MicrosoftAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SimpleNamespace(local={}, local_dir=Path(self.temp.name), save_local=Mock())
        self.auth = MicrosoftAuth(self.store)
        self.app = Mock()
        self.auth._application = self.app

    def tearDown(self):
        self.temp.cleanup()

    def test_no_secret_no_write_scopes(self):
        self.assertEqual(SCOPES, ['User.Read'])
        self.assertEqual(TIER_SCOPES['files'], ['User.Read', 'Files.Read'])
        self.assertEqual(TIER_SCOPES['sharepoint'], ['User.Read', 'Sites.Read.All'])
        self.assertFalse(any('Write' in s for scopes in TIER_SCOPES.values() for s in scopes))

    def test_interactive_identity_and_sign_out(self):
        self.app.acquire_token_interactive.return_value = {'access_token': 'secret', 'id_token_claims': {'oid': 'user', 'name': 'Researcher', 'preferred_username': 'name@university.edu', 'tid': 'tenant'}}
        account = self.auth.sign_in()
        self.app.acquire_token_interactive.assert_called_once_with(scopes=['User.Read'], timeout=180)
        self.assertEqual(account['id'], 'user')
        self.assertNotIn('secret', repr(account))
        self.app.get_accounts.return_value = [{'home_account_id': 'x'}]
        self.auth.sign_out()
        self.app.remove_account.assert_called_once()
        self.assertEqual(self.auth.get_account(), {})

    def test_silent_refresh_and_consent_error(self):
        self.app.get_accounts.return_value = [{'home_account_id': 'x'}]
        self.app.acquire_token_silent.return_value = {'access_token': 'secret'}
        self.assertEqual(self.auth.refresh(), 'secret')
        self.app.acquire_token_silent.return_value = {'error': 'consent_required', 'error_description': 'secret'}
        with self.assertRaises(AuthError) as caught:
            self.auth.refresh()
        self.assertNotIn('secret', str(caught.exception))
        self.assertEqual(self.auth.connection_status(), 'Admin approval required')

    def test_sharepoint_denial_preserves_basic_identity_and_permission(self):
        self.app.acquire_token_interactive.return_value = {'access_token': 'basic', 'id_token_claims': {'oid': 'user', 'name': 'Researcher'}}
        self.auth.sign_in()
        self.app.get_accounts.return_value = [{'home_account_id': 'x'}]
        self.app.acquire_token_silent.return_value = None
        self.app.acquire_token_interactive.return_value = {'error': 'access_denied', 'error_description': 'AADSTS90094 raw consent payload'}
        with self.assertRaisesRegex(AuthError, 'Admin approval required') as caught:
            self.auth.enable_access('sharepoint')
        self.assertNotIn('AADSTS', str(caught.exception))
        self.assertEqual(self.auth.state, 'Connected')
        self.assertEqual(self.auth.get_account()['id'], 'user')
        self.assertEqual(self.auth.permission_status()['basic'], 'Available')
        self.assertEqual(self.auth.permission_status()['sharepoint'], 'Admin approval required')
        self.app.acquire_token_interactive.assert_called_with(scopes=['User.Read', 'Sites.Read.All'], timeout=180)

    def test_background_sharepoint_token_check_never_opens_consent(self):
        self.auth.state = 'Connected'
        self.app.get_accounts.return_value = [{'home_account_id': 'x'}]
        self.app.acquire_token_silent.return_value = None
        with self.assertRaises(AuthError):
            self.auth.get_access_token('sharepoint')
        self.app.acquire_token_interactive.assert_not_called()
        self.assertEqual(self.auth.state, 'Connected')

    def test_own_files_denial_does_not_request_sharepoint(self):
        self.auth.state = 'Connected'
        self.auth.permissions['basic'] = 'Available'
        self.app.get_accounts.return_value = [{'home_account_id': 'x'}]
        self.app.acquire_token_silent.return_value = None
        self.app.acquire_token_interactive.return_value = {'error': 'consent_required'}
        with self.assertRaises(AuthError):
            self.auth.enable_access('files')
        self.app.acquire_token_interactive.assert_called_once_with(scopes=['User.Read', 'Files.Read'], timeout=180)
        self.assertEqual(self.auth.permissions['sharepoint'], 'Not enabled')
        self.assertEqual(self.auth.permissions['basic'], 'Available')

    def test_auth_exception_never_displays_raw_details(self):
        self.app.acquire_token_interactive.side_effect = RuntimeError('access_token=secret')
        with self.assertRaises(AuthError) as caught:
            self.auth.sign_in()
        self.assertNotIn('secret', str(caught.exception))

    def test_missing_registration_keeps_local_mode(self):
        self.auth._application = None
        with self.assertRaisesRegex(AuthError, 'Application ID'):
            self.auth.get_access_token()

    @unittest.skipUnless(os.name == 'nt', 'DPAPI requires Windows')
    def test_real_windows_cache_is_encrypted_and_not_in_synced_store(self):
        from msal_extensions import FilePersistenceWithDataProtection
        path = Path(self.temp.name) / 'token.bin'
        persistence = FilePersistenceWithDataProtection(str(path))
        persistence.save('test-only-noncredential-cache-value')
        self.assertNotIn(b'test-only-noncredential-cache-value', path.read_bytes())
        self.assertEqual(persistence.load(), 'test-only-noncredential-cache-value')


if __name__ == '__main__':
    unittest.main()
