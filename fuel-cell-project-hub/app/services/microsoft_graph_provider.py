"""Graph metadata snapshots. Historical sources are permanently separated."""
import copy
import hashlib
from pathlib import Path, PurePosixPath

from app.services.project_storage import ProjectStorageProvider, IndexCancelled, normalized_relative, EXCLUDED
from app.services.storage import read_json, write_json, timestamp
from app.services.file_classifier import classify_file
from app.services.microsoft_graph import GraphError
from app.services.software import open_resource


class MicrosoftGraphProvider(ProjectStorageProvider):
    def __init__(self, client, connection, cache_dir, rules=None, overrides=None):
        self.client, self.connection = client, copy.deepcopy(connection)
        self.rules, self.overrides = rules or {}, overrides or {}
        identity = '|'.join(str(connection.get(k, '')) for k in ('drive_id', 'root_item_id', 'legacy_project_id'))
        self.index_path = Path(cache_dir) / (hashlib.sha256(identity.encode()).hexdigest() + '.json')
        self.index = read_json(self.index_path, {'records': [], 'last_index_time': '', 'warnings': []})
        if not isinstance(self.index, dict) or not isinstance(self.index.get('records'), list):
            raise ValueError('Invalid cloud index. Existing cache preserved.')
        for record in self.index['records']:
            if not isinstance(record, dict) or not all(isinstance(record.get(k), str) for k in ('id', 'relative_path', 'name', 'modified', 'web_url', 'item_id', 'drive_id')) or not isinstance(record.get('size'), int):
                raise ValueError('Invalid cloud index record. Existing cache preserved.')
            normalized_relative(record['relative_path'])
        self.last_error = ''

    def list_items(self):
        records = copy.deepcopy(self.index['records'])
        for item in records:
            legacy_id = self.connection.get('legacy_project_id', '')
            item.update(data_origin='legacy' if legacy_id else 'current', legacy_project_id=legacy_id, read_only_reference=bool(legacy_id))
            item.update(classify_file(item['relative_path'], manual=self.overrides.get(item['id']), rules=self.rules))
            if self.connection.get('legacy_project_id'):
                item.update(legacy_project_name=self.connection.get('name', ''), legacy_note=self.connection.get('note', ''))
            if 'legacy_note' in self.overrides.get(item['id'], {}):
                item['legacy_note'] = self.overrides[item['id']]['legacy_note']
        return records

    def get_item(self, relative_path):
        return next((i for i in self.list_items() if i['relative_path'] == relative_path), None)

    def open_item(self, relative_path):
        item = self.get_item(relative_path)
        if not item:
            raise ValueError('This file is not in the cached index.')
        open_resource(item['web_url'])

    def open_folder(self, relative_path='.'):
        if relative_path not in ('', '.'):
            item = self.get_item(relative_path)
            if item and item.get('is_folder'):
                return open_resource(item['web_url'])
        return open_resource(self.connection['web_url'])

    def exists(self, relative_path):
        return self.get_item(relative_path) is not None

    def refresh(self, rebuild=False, cancel=None, progress=None):
        cancel, progress = cancel or (lambda: False), progress or (lambda n: None)
        drive = self.connection['drive_id']
        root = self.connection['root_item_id']
        # Root access must succeed before making any changes to the previous snapshot.
        self.client.get_drive_item(drive, root)
        previous = {i['id']: i for i in self.index['records']}
        records, warnings, visited = {}, [], set()
        stack = [(root, '.', 0)]
        legacy_id = self.connection.get('legacy_project_id', '')
        while stack:
            if cancel():
                raise IndexCancelled('Cloud indexing cancelled. Previous index preserved.')
            item_id, parent, depth = stack.pop()
            if item_id in visited or depth > 128:
                warnings.append({'path': parent, 'message': 'Repeated or excessively deep folder skipped.'})
                continue
            visited.add(item_id)
            try:
                children = self.client.list_children(drive, item_id, cancel)
            except GraphError as exc:
                if parent == '.':
                    raise
                warnings.append({'path': parent, 'message': str(exc)})
                for key, prior in previous.items():
                    if prior['relative_path'] == parent or prior['relative_path'].startswith(parent + '/'):
                        records[key] = dict(prior, scan_unverified=True)
                continue
            for child in children:
                if cancel():
                    raise IndexCancelled('Cloud indexing cancelled. Previous index preserved.')
                try:
                    name, cloud_id = child['name'], child['id']
                    if not isinstance(name, str) or not isinstance(cloud_id, str) or '/' in name or '\\' in name or name in ('.', '..'):
                        raise ValueError('Invalid cloud item name or ID.')
                    if name.casefold() in EXCLUDED:
                        continue
                    relative = normalized_relative((PurePosixPath(parent) / name).as_posix())
                    is_folder = 'folder' in child
                    stable = 'GRAPH-' + hashlib.sha256((drive + '|' + cloud_id + '|' + legacy_id).encode()).hexdigest()[:24]
                    record = {'id': stable, 'item_id': cloud_id, 'parent_item_id': item_id, 'drive_id': drive,
                              'relative_path': relative, 'name': name, 'size': int(child.get('size', 0)),
                              'created': child.get('createdDateTime', ''), 'modified': child.get('lastModifiedDateTime', ''),
                              'web_url': child.get('webUrl', ''), 'is_folder': is_folder, 'state': 'active',
                              'archived': '99_Archive' in PurePosixPath(relative).parts, 'provider': 'MicrosoftGraph',
                              'data_origin': 'legacy' if legacy_id else 'current', 'legacy_project_id': legacy_id,
                              'legacy_project_name': self.connection.get('name', '') if legacy_id else '',
                              'legacy_note': self.connection.get('note', '') if legacy_id else '',
                              'read_only_reference': bool(legacy_id),
                              **classify_file(relative, manual=self.overrides.get(stable), rules=self.rules)}
                    records[stable] = record
                    if is_folder:
                        stack.append((cloud_id, relative, depth + 1))
                    progress(len(records))
                except (KeyError, ValueError, TypeError):
                    warnings.append({'path': parent, 'message': 'An invalid metadata item was skipped.'})
        if cancel():
            raise IndexCancelled('Cloud indexing cancelled. Previous index preserved.')
        updated = {'schema_version': 1, 'records': list(records.values()), 'warnings': warnings,
                   'last_index_time': timestamp(), 'delta_link': '', 'connection': self.connection}
        write_json(self.index_path, updated)
        self.index, self.last_error = updated, ''
        return self.summary()

    def status(self):
        tier = 'sharepoint' if self.connection.get('site_id') else 'files'
        state = self.client.auth.permission_status().get(tier)
        if state == 'Available':
            return 'Connected'
        if state == 'Admin approval required':
            return 'Admin approval required · cached index available'
        return 'Cached · cloud access unavailable'

    def summary(self):
        files = [i for i in self.index['records'] if not i.get('is_folder')]
        return {'files': len(files), 'total_size': sum(i['size'] for i in files), 'size': sum(i['size'] for i in files),
                'last_index_time': self.index.get('last_index_time', ''), 'warnings': self.index.get('warnings', []),
                'changes': {'added': 0, 'modified': 0, 'removed': 0}, 'status': self.status()}

    def missing_folders(self):
        return []

    def create_missing_folders(self):
        raise ValueError('Microsoft cloud access is read-only. Use OneDrive or SharePoint to create folders.')

    def read_project(self):
        return copy.deepcopy(self.connection)

    def save_project(self, settings, revision):
        raise ValueError('Graph never writes shared settings. Use the local metadata store.')

    def history(self):
        return []
