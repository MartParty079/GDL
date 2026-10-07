"""Personal project locations and a transactional, read-only research catalog.

Provider JSON files are transport snapshots. SQLite is the combined searchable
catalog. Scanning never creates markers, reads placeholders or changes sources.
"""
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from collections import defaultdict
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

from app.services.storage import timestamp, read_json
from app.services.project_storage import EXCLUDED, placeholder, redirects, normalized_relative, IndexCancelled
from app.services.file_classifier import classify_file

RESEARCH_CATEGORIES = ('Literature', 'Research Papers', 'Standards', 'GDL Images', 'Microscopy',
    'Raw Experimental Data', 'Processed Data', 'Analysis', 'Python / MATLAB / Code',
    'Previous Reports', 'Presentations', 'Test Rig', 'Water Intrusion Testing',
    'Compression Testing', 'Pressure Testing', 'Image Analysis', 'CAD', 'Drawings',
    'Equipment', 'Calibration', 'Procedures', 'Meeting Notes', 'Project Management',
    'Funding / Grants', 'Miscellaneous')
PATH_LABELS = {'shared_storage': 'Shared Storage', 'database': 'Index / Database folder',
    'generated': 'Generated Output', 'cache': 'Temp / Cache', 'backups': 'Backups'}


def research_category(relative):
    value = relative.casefold().replace('_', ' ').replace('-', ' ')
    rules = [('microscopy', 'Microscopy'), ('water intrusion', 'Water Intrusion Testing'),
        ('compression', 'Compression Testing'), ('pressure', 'Pressure Testing'),
        ('calibration', 'Calibration'), ('standard', 'Standards'), ('literature', 'Literature'),
        ('paper', 'Research Papers'), ('presentation', 'Presentations'), ('meeting', 'Meeting Notes'),
        ('grant', 'Funding / Grants'), ('funding', 'Funding / Grants'), ('procedure', 'Procedures'),
        ('processed', 'Processed Data'), ('raw', 'Raw Experimental Data'), ('test rig', 'Test Rig'),
        ('equipment', 'Equipment'), ('drawing', 'Drawings'), ('report', 'Previous Reports'),
        ('analysis', 'Analysis'), ('management', 'Project Management')]
    for word, category in rules:
        if word in value:
            return category
    extension = Path(relative).suffix.lower()
    if extension in ('.py', '.m', '.jsl', '.ijm', '.ipynb', '.bat', '.ps1', '.r'):
        return 'Python / MATLAB / Code'
    kind = classify_file(relative)['category']
    return {'Image': 'GDL Images', 'CAD': 'CAD', 'Sensor Data': 'Raw Experimental Data',
            'Spreadsheet': 'Raw Experimental Data', 'Reference': 'Literature'}.get(kind, 'Miscellaneous')


class ProjectLocations:
    def __init__(self, store):
        self.store = store
        self.value = copy.deepcopy(store.local.get('project_locations') or self.defaults())
        self.validate(self.value)

    def defaults(self):
        from app.services.resources import RESOURCE_ROOT
        template = read_json(RESOURCE_ROOT / 'config/research_defaults.json', {})
        drive = Path(os.environ.get('OneDriveCommercial') or os.environ.get('OneDrive') or
                     Path.home() / 'OneDrive - tarleton.edu (NTNET)')
        def source(name, folder, kind):
            return {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, 'research-hub:' + kind + ':' + folder)),
                    'name': name, 'root_path': str(drive / folder), 'project_type': kind,
                    'source_type': kind, 'dataset_status': 'old_test_data' if kind == 'legacy' else 'current',
                    'read_only': kind == 'legacy', 'created_date': timestamp(), 'active': kind == 'active'}
        active = template.get('active', {'name': 'GDL Research', 'folder': 'GDL research - General'})
        legacy = template.get('legacy', [{'name': 'Michelson GDL Stuffs', 'folder': "Michelson, Andrew's files - GDL Stuffs"}])
        return {'enabled': False, 'active': source(active['name'], active['folder'], 'active'),
            'legacy': [source(s['name'], s['folder'], 'legacy') for s in legacy],
            'projects': [], 'shared_storage': str(drive / 'GDL research - General'),
            **{k: str(self.store.local_dir / v) for k, v in template.get('application_folders',
               {'database': 'catalog', 'generated': 'generated', 'cache': 'cache', 'backups': 'backups'}).items()}}

    @staticmethod
    def validate(value):
        roots = []
        identities = set()
        for source in [value['active'], *value['legacy']]:
            try:
                uuid.UUID(source['id'])
            except (ValueError, KeyError, TypeError):
                raise ValueError('The project identity is invalid. Restore valid personal configuration.') from None
            if source['id'] in identities:
                raise ValueError('Each research source needs a separate project identity.')
            identities.add(source['id'])
            path = Path(source['root_path']).expanduser()
            if not path.is_absolute() or path == Path(path.anchor) or path == Path.home():
                raise ValueError('Choose a dedicated absolute research folder.')
            if path.exists() and redirects(path.lstat()):
                raise ValueError('Choose a direct research folder, not a filesystem link.')
            if any(path == root or path in root.parents or root in path.parents for root in roots):
                raise ValueError('Current and legacy sources must be separate, non-overlapping folders.')
            roots.append(path)
        for key in PATH_LABELS:
            path = Path(value[key]).expanduser()
            if not path.is_absolute() or path == Path(path.anchor) or path == Path.home():
                raise ValueError('Choose dedicated absolute storage folders.')
            if key != 'shared_storage':
                path = path.resolve()
                if any(path == root.resolve() or root.resolve() in path.parents for root in roots):
                    raise ValueError('Keep databases, generated output, cache and backups outside research sources.')
        if len({str(Path(value[k]).resolve()) for k in ('database', 'generated', 'cache', 'backups')}) != 4:
            raise ValueError('Use separate application-owned storage folders.')

    def save(self, value):
        value = copy.deepcopy(value)
        self.validate(value)
        # Changing projects creates a stable identity; remapping the same project
        # can retain its ID through the explicit project selector.
        old = self.value['active']
        if old['root_path'] != value['active']['root_path'] and old['id'] == value['active']['id']:
            value['active']['id'] = str(uuid.uuid4())
            value['active']['created_date'] = timestamp()
        if old['id'] != value['active']['id']:
            projects = {s['id']: s for s in value.get('projects', [])}
            projects[old['id']] = dict(old, active=False)
            value['projects'] = [s for identity, s in projects.items() if identity != value['active']['id']]
        for source in value['legacy']:
            source.update(source_type='legacy', project_type='legacy', dataset_status='old_test_data', read_only=True, active=False)
        value['active'].update(source_type='active', project_type='active', dataset_status='current', active=True)
        value['enabled'] = True
        self.store.local['project_locations'] = value
        self.store.save_local()
        self.value = value
        self.store.record('Configuration', 'Research project locations changed; source files preserved')

    def sources(self):
        return [self.value['active'], *self.value['legacy']]

    def status(self):
        return [{'name': s['name'], 'status': 'Available' if Path(s['root_path']).is_dir() and
                 os.access(s['root_path'], os.R_OK) else 'Disconnected / inaccessible'} for s in self.sources()]


class ResearchCatalog:
    SCHEMA = 2

    def __init__(self, store, locations=None):
        self.store = store
        self.locations = locations or ProjectLocations(store)
        self.path = Path(self.locations.value['database']) / 'research.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute('PRAGMA busy_timeout=30000')
            with db:
                yield db
        finally:
            db.close()

    def backup(self, label='catalog'):
        target = Path(self.locations.value['backups'])
        target.mkdir(parents=True, exist_ok=True)
        destination = target / (label + '-' + uuid.uuid4().hex + '.sqlite3')
        with self.connect() as source, closing(sqlite3.connect(destination)) as copy_db:
            source.backup(copy_db)
        return destination

    def migrate(self):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > self.SCHEMA:
            raise ValueError('This index needs a newer Hub. The database has been preserved.')
        if version and version < self.SCHEMA:
            self.backup('before-migration')
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS overrides (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS files_source ON files(source)')
            db.execute('PRAGMA user_version=2')
            invalid = db.execute("""SELECT count(*) FROM files WHERE CASE WHEN json_valid(payload)
                THEN json_type(payload,'$.id') IS NOT 'text' OR json_type(payload,'$.name') IS NOT 'text'
                OR json_type(payload,'$.relative_path') IS NOT 'text' OR json_type(payload,'$.modified') IS NOT 'text'
                OR json_type(payload,'$.size') IS NOT 'integer' ELSE 1 END""").fetchone()[0]
            if invalid:
                raise ValueError('The index contains invalid records. Restore a backup; the existing database was preserved.')
        if version != self.SCHEMA:
            self.log('migration', previous=version, current=self.SCHEMA)

    def log(self, event, **values):
        folder = Path(self.locations.value['cache']) / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / 'catalog.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'time': timestamp(), 'event': event, **values}) + '\n')

    def rows(self, all_sources=False):
        revision = (self.path.stat().st_mtime_ns, self.path.stat().st_size)
        cached = getattr(self, '_rows_cache', {})
        if cached.get('revision') == revision and all_sources in cached:
            return cached[all_sources]
        with self.connect() as db:
            rows = [json.loads(row[0]) for row in db.execute('SELECT payload FROM files')]
            overrides = {i: json.loads(p) for i, p in db.execute('SELECT id,payload FROM overrides')}
        allowed = {s['id'] for s in self.locations.sources()}
        rows = [r for r in rows if all_sources or r.get('source_id') in allowed or r.get('provider') not in ('ResearchLocal', 'UnmappedSnapshot')]
        for row in rows:
            if row['id'] in overrides:
                row.update(overrides[row['id']], classification_source='manual')
        self.duplicates(rows)
        if cached.get('revision') != revision:
            cached = {'revision': revision}
        cached[all_sources] = rows
        self._rows_cache = cached
        return rows

    @staticmethod
    def duplicates(rows):
        names, hashes, likely = defaultdict(list), defaultdict(list), defaultdict(list)
        for row in rows:
            row['duplicate_status'] = ''
            if row.get('availability') == 'Deleted / moved':
                continue
            names[row['name'].casefold()].append(row)
            if row.get('hash'):
                hashes[row['hash']].append(row)
            likely[(row['name'].casefold(), row['size'], row['modified'])].append(row)
        for group in names.values():
            if len(group) > 1:
                known = {r.get('hash') for r in group if r.get('hash')}
                if len(known) > 1 or len({r['size'] for r in group}) > 1:
                    for row in group:
                        row['duplicate_status'] = 'Same filename / different contents'
        for group in likely.values():
            if len(group) > 1:
                for row in group:
                    if not row['duplicate_status']:
                        row['duplicate_status'] = 'Likely duplicate'
        for group in hashes.values():
            if len(group) > 1:
                for row in group:
                    row['duplicate_status'] = 'Exact duplicate'

    def set_override(self, item, values):
        allowed = {'category', 'subcategory', 'experiment_id', 'sample_id', 'procedure_id', 'legacy_note', 'tags', 'title', 'notes'}
        if set(values) - allowed or any(not isinstance(v, str) for v in values.values()):
            raise ValueError('Unsupported file metadata.')
        from app.services.file_classifier import CATEGORIES
        if values.get('category') and values['category'] not in (*CATEGORIES, *RESEARCH_CATEGORIES):
            raise ValueError('Choose a supported category.')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO overrides VALUES (?,?)', (item['id'], json.dumps(values)))
        self.log('classification_changed', file_id=item['id'])

    def import_snapshots(self):
        """Non-destructive, one-time migration; preserve malformed inputs."""
        with self.connect() as db:
            done = {r[0] for r in db.execute("SELECT key FROM metadata WHERE key LIKE 'snapshot:%'")}
        candidates = [*self.store.local_dir.glob('index/file_index.json'),
                      *self.store.local_dir.glob('cloud_index/*.json'), *self.store.local_dir.glob('legacy/*.json')]
        for path in candidates:
            key = 'snapshot:' + str(path)
            if key in done:
                continue
            try:
                value = read_json(path, {})
                records = value.get('records', [])
                if not isinstance(records, list):
                    raise ValueError()
                backup_dir = Path(self.locations.value['backups']) / 'provider-snapshots'
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup_dir / (uuid.uuid4().hex + '.json'))
                mapped = next((s for s in self.locations.sources() if
                    Path(s['root_path']).resolve() == Path(self.store.local.get('local_project_root') or self.store.local_dir).resolve()), None) if path.parent.name == 'index' else None
                with self.connect() as db:
                    for identity, override in self.store.project.get('file_overrides', {}).items():
                        db.execute('INSERT OR IGNORE INTO overrides VALUES (?,?)', (identity, json.dumps(override)))
                    for row in records:
                        if not isinstance(row, dict) or not all(k in row for k in ('id', 'name', 'size', 'modified', 'relative_path')):
                            raise ValueError()
                        if any(not isinstance(row[k], str) for k in ('id', 'name', 'modified', 'relative_path')) or not isinstance(row['size'], int) or row['size'] < 0:
                            raise ValueError()
                        row = dict(row)
                        row.setdefault('provider', 'ProviderSnapshot')
                        row.setdefault('data_origin', 'legacy' if 'legacy' in path.parts else 'current')
                        row.setdefault('archived', False)
                        for k in ('category', 'experiment_id', 'run_id', 'sample_id', 'procedure_id'):
                            row.setdefault(k, '')
                        if mapped:
                            row.update(provider='ResearchLocal', source_id=mapped['id'], source_name=mapped['name'],
                                project_name=mapped['name'], source_type=mapped['source_type'],
                                dataset_status=mapped['dataset_status'], read_only=mapped['read_only'],
                                data_origin='legacy' if mapped['source_type'] == 'legacy' else 'current',
                                legacy_project_id=mapped['id'] if mapped['source_type'] == 'legacy' else '',
                                legacy_project_name=mapped['name'] if mapped['source_type'] == 'legacy' else '',
                                document_type=row['category'], category=research_category(row['relative_path']),
                                full_path=str(Path(mapped['root_path']) / normalized_relative(row['relative_path'])),
                                extension=Path(row['relative_path']).suffix.lower(), availability='Not checked since migration', state='active')
                        else:
                            # Keep unmatched snapshots recoverable without presenting
                            # another project's data as current research.
                            row.update(provider='UnmappedSnapshot', source_id='unmapped-snapshot')
                        db.execute('INSERT OR IGNORE INTO files VALUES (?,?,?)', (row['id'], row.get('source_id', 'snapshot'), json.dumps(row)))
                    db.execute('INSERT INTO metadata VALUES (?,?)', (key, timestamp()))
                self.log('snapshot_migrated', records=len(records))
            except (OSError, ValueError, TypeError):
                self.log('snapshot_unavailable', action='original preserved')

    def ingest(self, records):
        """Update transport snapshots in the unified catalog without dropping offline rows."""
        with self.connect() as db:
            for row in records:
                db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?)',
                           (row['id'], row.get('source_id', 'provider'), json.dumps(row)))

    def refresh(self, rebuild=False, cancel=None, progress=None, source_ids=None, selected=None, quick=False):
        if rebuild:
            self.backup('before-rebuild')
        self.log('index_start', mode='rebuild' if rebuild else 'quick' if quick else 'full')
        counts = dict(scanned=0, new=0, updated=0, unchanged=0, current=0, legacy=0,
                      duplicates=0, errors=0, unsupported=0, unavailable=0)
        old = {r['id']: r for r in self.rows(all_sources=True)}
        old_paths = {(r.get('source_id'), r.get('relative_path')): r for r in old.values()}
        hash_budget = 32 * 1024 * 1024
        staged = []
        selected = normalized_relative(selected) if selected else ''
        for source in self.locations.sources():
            if source_ids and source['id'] not in source_ids:
                continue
            root = Path(source['root_path'])
            seen, uncertain = set(), []
            previous = [r for r in old.values() if r.get('source_id') == source['id']]
            inode_map = defaultdict(list)
            for row in previous:
                if row.get('inode'):
                    inode_map[row['inode']].append(row)
            def scan(folder):
                nonlocal hash_budget
                try:
                    if redirects(folder.lstat()):
                        raise OSError()
                    with os.scandir(folder) as entries:
                        for entry in entries:
                            if cancel and cancel():
                                raise IndexCancelled('Index cancelled; the previous catalog was preserved.')
                            if entry.name in EXCLUDED:
                                continue
                            path = Path(entry.path)
                            relative = path.relative_to(root).as_posix()
                            try:
                                info = path.lstat()
                                if redirects(info):
                                    uncertain.append(relative)
                                    continue
                                if entry.is_dir(follow_symlinks=False):
                                    scan(path)
                                    continue
                                if not entry.is_file(follow_symlinks=False):
                                    continue
                                counts['scanned'] += 1
                                inode = str(info.st_dev) + ':' + str(info.st_ino) if info.st_ino else ''
                                identity = str(uuid.uuid5(uuid.UUID(source['id']), relative.casefold() if os.name == 'nt' else relative))
                                prior = old_paths.get((source['id'], relative)) or old.get(identity)
                                if prior:
                                    identity = prior['id']
                                if not prior and inode and len(inode_map[inode]) == 1:
                                    candidate = inode_map[inode][0]
                                    if not (root / candidate['relative_path']).exists():
                                        prior, identity = candidate, candidate['id']
                                seen.add(identity)
                                signature = [info.st_size, info.st_mtime_ns]
                                resident = not placeholder(info)
                                row = dict(prior or {})
                                row.update(id=identity, source_id=source['id'], source_name=source['name'],
                                    source_type=source['source_type'], dataset_status=source['dataset_status'],
                                    read_only=source['read_only'], project_name=source['name'], full_path=str(path),
                                    relative_path=relative, parent_folder=path.parent.relative_to(root).as_posix(),
                                    name=entry.name, extension=path.suffix.lower(), size=info.st_size,
                                    created=datetime.fromtimestamp(getattr(info, 'st_birthtime', info.st_ctime), timezone.utc).isoformat(),
                                    modified=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                                    indexed=timestamp(), signature=signature, inode=inode,
                                    availability='Locally available' if resident else 'Online-only', state='active', archived=False,
                                    provider='ResearchLocal', data_origin='legacy' if source['source_type'] == 'legacy' else 'current',
                                    legacy_project_id=source['id'] if source['source_type'] == 'legacy' else '',
                                    legacy_project_name=source['name'] if source['source_type'] == 'legacy' else '')
                                changed = not prior or prior.get('signature') != signature
                                if changed or rebuild:
                                    row.update(classify_file(relative))
                                    row['document_type'] = row['category']
                                    row.update(category=research_category(relative), hash='')
                                elif prior.get('relative_path') != relative:
                                    row.update(classify_file(relative), category=research_category(relative))
                                if resident and not row.get('hash') and not quick and info.st_size <= 1024 * 1024 and info.st_size <= hash_budget:
                                    # Check flags again immediately before opening; never read cloud placeholders.
                                    if not placeholder(path.stat()):
                                        digest = hashlib.sha256()
                                        with path.open('rb') as stream:
                                            for chunk in iter(lambda: stream.read(65536), b''):
                                                digest.update(chunk)
                                        after = path.stat()
                                        hash_budget -= info.st_size
                                        if [after.st_size, after.st_mtime_ns] == signature:
                                            row['hash'] = digest.hexdigest()
                                        else:
                                            row['availability'] = 'Still syncing'
                                for key in ('tags', 'title', 'notes', 'subcategory', 'legacy_note'):
                                    row.setdefault(key, '')
                                if row['document_type'] == 'Other':
                                    counts['unsupported'] += 1
                                counts['new' if not prior else 'updated' if changed or prior.get('relative_path') != relative else 'unchanged'] += 1
                                counts['legacy' if source['source_type'] == 'legacy' else 'current'] += 1
                                staged.append(row)
                                if progress and counts['scanned'] % 100 == 0:
                                    progress(counts['scanned'])
                            except OSError:
                                uncertain.append(relative)
                                counts['errors'] += 1
                except OSError:
                    uncertain.append(folder.relative_to(root).as_posix())
                    counts['errors'] += 1
            scan(root / selected if selected else root)
            for row in previous:
                relative = row['relative_path']
                if row['id'] in seen or selected and not (relative == selected or relative.startswith(selected.rstrip('/') + '/')):
                    continue
                missing = dict(row)
                missing['availability'] = 'Temporarily unavailable' if any(p == '.' or relative == p or relative.startswith(p + '/') for p in uncertain) else 'Deleted / moved'
                missing['state'] = 'active'  # Visible last-known reference, with explicit availability.
                counts['unavailable'] += 1
                staged.append(missing)
        if cancel and cancel():
            raise IndexCancelled('Index cancelled; the previous catalog was preserved.')
        with self.connect() as db:
            for row in staged:
                db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?)', (row['id'], row['source_id'], json.dumps(row)))
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('last_indexed', timestamp()))
        rows = self.rows()
        counts['duplicates'] = sum(bool(r['duplicate_status']) for r in rows)
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('last_summary', json.dumps(counts)))
        self.log('index_complete', **counts)
        if counts['unavailable']:
            self.log('missing_files_preserved', count=counts['unavailable'])
        return counts

    def summary(self):
        revision = (self.path.stat().st_mtime_ns, self.path.stat().st_size)
        if getattr(self, '_summary_revision', None) == revision:
            return self._summary
        with self.connect() as db:
            metadata = dict(db.execute('SELECT key,value FROM metadata'))
            source_ids = [s['id'] for s in self.locations.sources()]
            placeholders = ','.join('?' for _ in source_ids)
            totals = dict(db.execute(f"SELECT coalesce(json_extract(payload,'$.data_origin'),'current'),count(*) FROM files WHERE source IN ({placeholders}) OR json_extract(payload,'$.provider')='MicrosoftGraph' GROUP BY 1", source_ids))
        self._summary_revision = revision
        self._summary = dict(current=sum(count for kind, count in totals.items() if kind != 'legacy'),
                    legacy=totals.get('legacy', 0),
                    last_indexed=metadata.get('last_indexed', ''), sources=len(self.locations.sources()),
                    **{'last_run': json.loads(metadata.get('last_summary', '{}'))})
        return self._summary

    def safe_path(self, item):
        source = next((s for s in self.locations.sources() if s['id'] == item.get('source_id')), None)
        if not source:
            raise ValueError('Reconnect the source project to open this reference.')
        root = Path(source['root_path']).resolve()
        path = root / normalized_relative(item['relative_path'])
        cursor = path
        while cursor != root:
            if cursor.exists() and redirects(cursor.lstat()):
                raise ValueError('Filesystem links cannot be opened through the catalog.')
            cursor = cursor.parent
        if root.exists() and redirects(root.lstat()):
            raise ValueError('Reconnect a direct research folder.')
        path.resolve().relative_to(root)
        return path

    def open_item(self, item, parent=False):
        path = self.safe_path(item)
        target = path.parent if parent else path
        if not target.exists() or (not parent and placeholder(target.stat())):
            raise ValueError('File currently unavailable locally. Download it in OneDrive or reconnect its source.')
        if not parent and path.suffix.lower() in ('.exe', '.bat', '.cmd', '.ps1', '.py', '.m', '.js', '.vbs', '.lnk', '.url', '.com', '.scr', '.msi'):
            raise ValueError('Use Open Containing Folder to inspect code; the Hub does not execute indexed scripts.')
        from app.services.software import open_resource
        return open_resource(str(target))

    def import_current(self, item):
        if item.get('data_origin') != 'legacy':
            raise ValueError('Choose a legacy reference to import.')
        source = self.safe_path(item)
        if not source.is_file() or placeholder(source.stat()):
            raise ValueError('File currently unavailable locally. Download it before importing.')
        root = Path(self.locations.value['active']['root_path'])
        if not root.is_dir() or redirects(root.lstat()):
            raise ValueError('Reconnect the current project before importing.')
        destination = root / source.name
        number = 1
        while destination.exists():
            destination = root / (source.stem + f' (import {number})' + source.suffix)
            number += 1
        # Exclusive creation prevents overwriting a file arriving during a sync.
        with source.open('rb') as incoming, destination.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        self.log('legacy_copied_to_current', file_id=item['id'])
        return destination
