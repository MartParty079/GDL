"""Authoritative local mappings and portable project storage definitions."""
import copy
import os
import uuid
from pathlib import Path

from app.services.storage import timestamp
from app.services.project_storage import LocalOneDriveProvider, normalized_relative
from app.services.file_classifier import classify_file, CATEGORIES

FOLDERS = dict(zip(('Procedures', 'Samples', 'Experiments', 'Raw Data', 'Processed Data', 'Analysis',
                   'Reports', 'Reference', 'Exports', 'Archive'),
                  ('01_Procedures', '02_Samples', '03_Experiments', '04_Raw_Data', '05_Processed_Data',
                   '06_Analysis', '07_Reports', '08_Reference', '09_Exports', '99_Archive')))
LEGACY_NOTE = 'Historical project data retained for reference and comparison; excluded from current project work.'


class StorageSettings:
    def __init__(self, store, unused=None):
        self.store = store
        from app.services.storage import read_json
        self.default_rules = read_json(store.config_dir / 'file_classification.json', {})
        from app.services.research_catalog import ProjectLocations
        self.locations = ProjectLocations(store)
        self.catalog = None
        if self.locations.value.get('enabled'):
            self.connect_catalog()

    def connect_catalog(self):
        from app.services.research_catalog import ResearchCatalog
        import sqlite3
        self.catalog_error = ''
        # The previous marker-based mapping is retained only as a migration
        # reference. Research settings must never write that shared source.
        self.store.provider = None
        try:
            self.catalog = ResearchCatalog(self.store, self.locations)
            self.catalog.import_snapshots()
            self.catalog.log('startup', project_id=self.locations.value['active']['id'])
        except (OSError, ValueError, sqlite3.Error):
            self.catalog = None
            self.catalog_error = ('Waiting for a verified shared revision from the indexing authority. Other tools remain available.'
                if self.store.shared_index else 'Research index unavailable. The existing database was preserved. Check the Index / Database location or restore a backup; Other application tools remain available.')

    def save_locations(self, value):
        if self.store.shared_index:
            self.locations.save(value)
            if not self.catalog:
                self.connect_catalog()
            return
        import sqlite3
        from app.services.research_catalog import ProjectLocations
        ProjectLocations.validate(value)
        if value == self.locations.value and self.catalog:
            return
        destination = Path(os.path.expandvars(value['database'])).expanduser().resolve() / 'research.sqlite3'
        if self.catalog and destination.resolve() != self.catalog.path.resolve():
            if destination.exists():
                raise ValueError('The destination already has a catalog. Choose an empty index folder to preserve both databases.')
            self.catalog.backup('before-relocation')
            destination.parent.mkdir(parents=True, exist_ok=True)
            from contextlib import closing
            with self.catalog.connect() as previous, closing(sqlite3.connect(destination)) as new:
                previous.backup(new)
        self.locations.save(value)
        self.connect_catalog()

    def validate_root(self, value):
        provider = LocalOneDriveProvider(value, self.store.local_dir / 'index')
        marker = provider.validate_root(require_marker=False)
        if not os.access(provider.root, os.R_OK):
            raise ValueError('The folder is not readable.')
        return provider, marker

    def change_root(self, value, initialize=False):
        self.protect_research_source(value)
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
        for key in ('project_folders', 'file_classification', 'file_overrides'):
            if key in preserved and key not in self.store.project:
                self.store.project[key] = preserved[key]
        if self.store.project != self.store.provider.settings_baseline:
            self.store.save_project(self.store.project, 'Storage mapping connected; portable project definitions retained')
        self.store.cache_project()
        return self.store.provider

    def protect_research_source(self, value):
        if self.store.shared_required:
            raise ValueError('Use verified shared project setup. The previous library initializer is disabled for shared-index Beta.')
        if not self.locations.value.get('enabled'):
            return
        target = Path(value).expanduser().resolve()
        for source in self.locations.sources():
            root = Path(source['root_path']).resolve()
            if target == root or root in target.parents or target in root.parents:
                raise ValueError('This is configured research storage. Use the Project and Indexing tabs to reference it without shared-library initialization or writes.')

    def reset_root(self):
        self.store.cache_project()
        self.store.provider = None
        self.store.local['local_project_root'] = ''
        self.store.storage_error = ''
        self.store.save_local()
        self.store.record('Storage', 'Local project mapping reset; project files preserved')

    def save_folders(self, folders):
        if set(folders) != set(FOLDERS):
            raise ValueError('All project folder mappings are required.')
        values = {key: normalized_relative(value.strip()) for key, value in folders.items()}
        if any(path == '.' for path in values.values()) or len(set(values.values())) != len(values):
            raise ValueError('Use separate, nonempty relative project folders.')
        value = copy.deepcopy(self.store.project)
        value['project_folders'] = values
        self.store.save_project(value, 'Project folder mappings changed; files preserved')

    def set_override(self, item, values):
        if self.catalog:
            self.catalog.set_override(item, values)
            return
        allowed = {'category', 'subcategory', 'experiment_id', 'sample_id', 'procedure_id', 'legacy_note'}
        if set(values) - allowed or any(not isinstance(v, str) for v in values.values()):
            raise ValueError('Unsupported file metadata override.')
        if values.get('category') and values['category'] not in CATEGORIES:
            raise ValueError('Choose a supported file category.')
        value = copy.deepcopy(self.store.project)
        value.setdefault('file_overrides', {})[item['id']] = values
        self.store.save_project(value, 'File classification metadata changed; file preserved')

    def files(self):
        if self.catalog:
            return self.catalog.query(limit=200)[0]
        local = self.store.provider
        if not local:
            return []
        try:
            items = local.list_items()
        except (OSError, ValueError):
            items = local.index.get('records', [])
        records = []
        for item in items:
            item = dict(item, data_origin='archive' if item['archived'] else 'current', provider='LocalOneDrive')
            manual = self.store.project.get('file_overrides', {}).get(item['id'], {})
            explicit = {k: item.get(k, '') for k in ('experiment_id', 'sample_id', 'run_id', 'procedure_id', 'procedure_version')}
            if item.get('classification_source') == 'metadata':
                explicit.update(category=item['category'], subcategory=item.get('subcategory', ''))
            item.update(classify_file(item['relative_path'], explicit=explicit, manual=manual,
                rules=self.store.project.get('file_classification', self.default_rules)))
            if 'legacy_note' in manual:
                item['legacy_note'] = manual['legacy_note']
            records.append(item)
        return records

    def open_item(self, item, parent=False):
        if item.get('provider') == 'ResearchLocal' and self.catalog:
            return self.catalog.open_item(item, parent)
        if not self.store.provider:
            raise ValueError('Reconnect the local project folder to open this file.')
        return self.store.provider.open_containing_folder(item['relative_path']) if parent else self.store.provider.open_item(item['relative_path'])
