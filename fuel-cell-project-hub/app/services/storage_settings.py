"""Authoritative local mappings and portable project storage definitions."""
import copy
import os
import uuid
from pathlib import Path

from app.services.storage import timestamp
from app.services.project_storage import LocalOneDriveProvider, normalized_relative
from app.services.microsoft_graph_provider import MicrosoftGraphProvider
from app.services.file_classifier import classify_file, CATEGORIES

FOLDERS = dict(zip(('Procedures', 'Samples', 'Experiments', 'Raw Data', 'Processed Data', 'Analysis',
                   'Reports', 'Reference', 'Exports', 'Archive'),
                  ('01_Procedures', '02_Samples', '03_Experiments', '04_Raw_Data', '05_Processed_Data',
                   '06_Analysis', '07_Reports', '08_Reference', '09_Exports', '99_Archive')))
LEGACY_NOTE = 'Historical project data retained for reference and comparison; excluded from current project work.'


class StorageSettings:
    def __init__(self, store, graph):
        self.store, self.graph = store, graph
        from app.services.storage import read_json
        self.default_rules = read_json(store.config_dir / 'file_classification.json', {})

    def validate_root(self, value):
        provider = LocalOneDriveProvider(value, self.store.local_dir / 'index')
        marker = provider.validate_root(require_marker=False)
        if not os.access(provider.root, os.R_OK):
            raise ValueError('The folder is not readable.')
        return provider, marker

    def change_root(self, value, initialize=False):
        provider = LocalOneDriveProvider(value, self.store.local_dir / 'index')
        marker = provider.validate_root(require_marker=False, allow_unmarked=initialize)
        previous_id = self.store.local.get('project_id', '')
        if marker and previous_id and marker['project_id'] != previous_id:
            raise ValueError('This folder belongs to another project. Select a synced copy of this project or an unmarked folder to initialize.')
        if not marker:
            if not initialize:
                raise ValueError('Confirm initialization of this folder before changing the mapping.')
            provider.accept_root(self.store.project['storage']['project_name'], copy.deepcopy(self.store.project), True)
            if previous_id:
                from app.services.storage import read_json, write_json
                path = provider.root / '.projecthub' / 'project.json'
                data = read_json(path, {})
                data['project_id'] = previous_id
                write_json(path, data)
        preserved = copy.deepcopy(self.store.project)
        self.store.connect_storage(str(provider.root))
        # The shared marker is authoritative for same-project reconnects. Carry forward
        # definitions only when missing (e.g. an older synchronized marker).
        for key in ('current_cloud_connection', 'legacy_projects', 'project_folders', 'file_classification', 'file_overrides'):
            if key in preserved and key not in self.store.project:
                self.store.project[key] = preserved[key]
        if self.store.project != self.store.provider.settings_baseline:
            self.store.save_project(self.store.project, 'Storage mapping connected; portable project definitions retained')
        self.store.cache_project()
        return self.store.provider

    def reset_root(self):
        self.store.cache_project()
        self.store.provider = None
        self.store.local['local_project_root'] = ''
        self.store.storage_error = ''
        self.store.save_local()
        self.store.record('Storage', 'Local project mapping reset; project files preserved')

    def set_mode(self, mode):
        if mode not in ('LocalOnly', 'CloudOnly', 'Hybrid'):
            raise ValueError('Choose LocalOnly, CloudOnly, or Hybrid.')
        self.store.local['storage_mode'] = mode
        self.store.save_local()

    def save_folders(self, folders):
        if set(folders) != set(FOLDERS):
            raise ValueError('All project folder mappings are required.')
        values = {key: normalized_relative(value.strip()) for key, value in folders.items()}
        if any(path == '.' for path in values.values()) or len(set(values.values())) != len(values):
            raise ValueError('Use separate, nonempty relative project folders.')
        value = copy.deepcopy(self.store.project)
        value['project_folders'] = values
        self.store.save_project(value, 'Project folder mappings changed; files preserved')

    def set_legacy_cache(self, value):
        path = Path(value).expanduser().resolve()
        # Cache changes never move or remove the existing index.
        if path == Path(path.anchor) or path == Path.home().resolve():
            raise ValueError('Select a dedicated cache folder, not a drive or user root.')
        if self.store.provider:
            try:
                path.relative_to(self.store.provider.root)
            except ValueError:
                pass
            else:
                raise ValueError('Keep the per-user legacy cache outside shared project storage.')
        parent = path if path.exists() else path.parent
        if not parent.is_dir() or not os.access(parent, os.R_OK | os.W_OK):
            raise ValueError('Choose an accessible writable cache folder or an existing parent.')
        previous = str(self.cache_dir())
        self.store.local.setdefault('previous_legacy_caches', [])
        if previous != str(path) and previous not in self.store.local['previous_legacy_caches']:
            self.store.local['previous_legacy_caches'].append(previous)
        self.store.local['legacy_cache_root'] = str(path)
        self.store.save_local()

    def cache_dir(self):
        return Path(self.store.local.get('legacy_cache_root') or self.store.local_dir / 'legacy')

    def provider(self, connection):
        self.graph.register_connection(connection)
        cache = self.cache_dir() if connection.get('legacy_project_id') else self.store.local_dir / 'cloud_index'
        provider = MicrosoftGraphProvider(self.graph, connection, cache, self.store.project.get('file_classification', self.default_rules), self.store.project.get('file_overrides'))
        if connection.get('legacy_project_id') and not provider.index_path.exists():
            for old in reversed(self.store.local.get('previous_legacy_caches', [])):
                prior = MicrosoftGraphProvider(self.graph, connection, old, provider.rules, provider.overrides)
                if prior.index_path.exists():
                    provider.index = prior.index
                    break
        return provider

    def connect_cloud(self, selection, legacy=False, name='', note=LEGACY_NOTE):
        self.graph.register_connection(selection)
        item = self.graph.get_drive_item(selection['drive_id'], selection['root_item_id'])
        if 'folder' not in item:
            raise ValueError('Select a project folder or library root.')
        connection = {'provider': 'MicrosoftGraph', 'site_id': selection.get('site_id', ''),
                      'drive_id': selection['drive_id'], 'root_item_id': item['id'], 'web_url': item.get('webUrl', '')}
        value = copy.deepcopy(self.store.project)
        identity = (connection['drive_id'], connection['root_item_id'])
        current = value.get('current_cloud_connection', {})
        if legacy and identity == (current.get('drive_id'), current.get('root_item_id')):
            raise ValueError('This folder is already the current project. Select a different historical project folder.')
        if not legacy and any(identity == (p['drive_id'], p['root_item_id']) for p in value.get('legacy_projects', [])):
            raise ValueError('This folder is a historical reference. Select the current project folder instead.')
        if legacy:
            projects = value.setdefault('legacy_projects', [])
            if any(p['drive_id'] == connection['drive_id'] and p['root_item_id'] == connection['root_item_id'] for p in projects):
                raise ValueError('This previous project has already been imported.')
            connection.update(legacy_project_id='LEG-' + uuid.uuid4().hex[:12].upper(), name=name.strip() or item['name'],
                              note=note.strip() or LEGACY_NOTE, imported_on=timestamp(), imported_by=self.graph.auth.get_account().get('id', ''),
                              read_only_reference=True, data_origin='legacy')
            projects.append(connection)
        else:
            connection['data_origin'] = 'current'
            value['current_cloud_connection'] = connection
        self.store.save_project(value, 'Previous project reference added' if legacy else 'Current cloud connection changed')
        return connection

    def disconnect_cloud(self):
        value = copy.deepcopy(self.store.project)
        value.pop('current_cloud_connection', None)
        self.store.save_project(value, 'Current cloud connection disconnected; files preserved')

    def edit_note(self, legacy_id, note):
        value = copy.deepcopy(self.store.project)
        project = next(p for p in value.get('legacy_projects', []) if p['legacy_project_id'] == legacy_id)
        project['note'] = note.strip()
        self.store.save_project(value, 'Historical project note changed')

    def set_override(self, item, values):
        allowed = {'category', 'subcategory', 'experiment_id', 'sample_id', 'procedure_id', 'legacy_note'}
        if set(values) - allowed or any(not isinstance(v, str) for v in values.values()):
            raise ValueError('Unsupported file metadata override.')
        if values.get('category') and values['category'] not in CATEGORIES:
            raise ValueError('Choose a supported file category.')
        value = copy.deepcopy(self.store.project)
        value.setdefault('file_overrides', {})[item['id']] = values
        self.store.save_project(value, 'File classification metadata changed; file preserved')

    def files(self):
        mode = self.store.local.get('storage_mode', 'LocalOnly')
        records = []
        local = self.store.provider
        cloud = self.store.project.get('current_cloud_connection')
        tier = 'sharepoint' if cloud and cloud.get('site_id') else 'files'
        cloud_available = cloud and self.graph.auth.permission_status().get(tier) == 'Available'
        if local and (mode != 'CloudOnly' or not cloud_available):
            try:
                local_items = local.list_items()
            except (OSError, ValueError):
                local_items = local.index.get('records', []) if local.index.get('project_id') == self.store.local.get('project_id') else []
            for item in local_items:
                item = dict(item, data_origin='archive' if item['archived'] else 'current', provider='LocalOneDrive')
                manual = self.store.project.get('file_overrides', {}).get(item['id'], {})
                explicit = {k: item.get(k, '') for k in ('experiment_id', 'sample_id', 'run_id', 'procedure_id', 'procedure_version')}
                if item.get('classification_source') == 'metadata':
                    explicit.update(category=item['category'], subcategory=item.get('subcategory', ''))
                item.update(classify_file(item['relative_path'], explicit=explicit, manual=manual, rules=self.store.project.get('file_classification', self.default_rules)))
                if 'legacy_note' in manual:
                    item['legacy_note'] = manual['legacy_note']
                records.append(item)
        if cloud and mode != 'LocalOnly':
            try:
                current = self.provider(cloud).list_items()
            except (OSError, ValueError):
                current = []
            local_paths = {i['relative_path'] for i in records}
            records.extend(i for i in current if not i.get('is_folder') and i['relative_path'] not in local_paths)
        for project in self.store.project.get('legacy_projects', []):
            try:
                records.extend(i for i in self.provider(project).list_items() if not i.get('is_folder'))
            except (OSError, ValueError):
                continue
        return records

    def open_item(self, item, parent=False):
        if item.get('provider') != 'MicrosoftGraph':
            if not self.store.provider:
                raise ValueError('Reconnect the local project folder to open this file.')
            return self.store.provider.open_containing_folder(item['relative_path']) if parent else self.store.provider.open_item(item['relative_path'])
        if not item.get('legacy_project_id') and self.store.local.get('storage_mode') == 'Hybrid' and self.store.provider:
            try:
                if self.store.provider.exists(item['relative_path']):
                    return self.store.provider.open_item(item['relative_path'])
            except (OSError, ValueError):
                pass
        if parent:
            url = self.graph.get_web_url(item['drive_id'], item['parent_item_id'])
        else:
            url = item['web_url']
        from app.services.software import open_resource
        return open_resource(url)
