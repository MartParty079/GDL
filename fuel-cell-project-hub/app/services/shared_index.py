"""Identity-bound, immutable publication for the existing NativeIndex.

OneDrive provides distribution, not locking or authorization. Enrollment is an
explicit owner action; authority transfer requires retiring the old device.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager, closing
from pathlib import Path
from app.services.storage import read_json, write_json, timestamp
from app.services.project_storage import normalized_relative, redirects

PENDING_METHODS = {'NativeIndex.set_override', 'NativeIndex.relate',
    'ResearchWorkspace.save', 'ResearchWorkspace.annotate', 'ResearchWorkspace.record_event',
    'SampleIntelligence.assign', 'SampleIntelligence.edit_image', 'SampleIntelligence.reset'}


class SharedIndex:
    def __init__(self, store, root, expected=None):
        self.store = store
        original = Path(root)
        if original.exists() and redirects(original.lstat()):
            raise ValueError('Choose a direct synchronized folder, not a filesystem link.')
        self.root = original.resolve()
        if not self.root.is_dir() or redirects(self.root.lstat()):
            raise ValueError('Locate your synchronized shared project folder.')
        self.control = self.root / '.project_hub'
        for relative in ('.project_hub', '.project_hub/index', '.project_hub/index/revisions',
                         '.project_hub/index/pending', '.project_hub/settings', '.project_hub/metadata', '.project_hub/logs'):
            path = self.root / relative
            if not path.resolve().is_relative_to(self.root) or (path.exists() and redirects(path.lstat())):
                raise ValueError('Shared project control folders cannot be filesystem links.')
        self.identity = read_json(self.control / 'identity.json', {})
        try:
            uuid.UUID(self.identity['project_id'])
            uuid.UUID(self.identity['authority_id'])
        except (KeyError, ValueError, TypeError):
            raise ValueError('Project identity unavailable. Ask the project owner to complete setup.') from None
        if expected and expected != self.identity['project_id']:
            raise ValueError('This is a different project. Select a synchronized copy of the configured project.')
        self.index = self.control / 'index'
        self.cache = store.local_dir / 'cache' / 'shared-index' / self.identity['project_id']
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.revision = None
        self.path = None
        self.verified_stat = None
        self.status = 'No published index yet'

    @classmethod
    def enroll(cls, store, root, confirmed=False, project_id=None, sources=None):
        if not confirmed:
            raise ValueError('Explicit project-owner confirmation is required.')
        original = Path(root)
        if original.exists() and redirects(original.lstat()):
            raise ValueError('Select a direct shared project folder.')
        root = original.resolve()
        if root.name != 'GDL research - General':
            raise ValueError('Initialize only the existing GDL research - General shared project.')
        if not root.is_dir() or redirects(root.lstat()):
            raise ValueError('Select an existing direct shared folder.')
        control = root / '.project_hub'
        if control.exists() and (redirects(control.lstat()) or not control.resolve().is_relative_to(root)):
            raise ValueError('The project control folder cannot be a filesystem link.')
        # Exclusive creation: never overwrite an existing identity.
        control.mkdir(exist_ok=True)
        identity = {'schema': 1, 'project_id': str(uuid.UUID(project_id)) if project_id else str(uuid.uuid4()),
                    'authority_id': str(uuid.uuid4()), 'created': timestamp(),
                    'drive_id': None, 'item_id': None, 'sources': sources or []}
        with (control / 'identity.json').open('x', encoding='utf-8') as output:
            json.dump(identity, output, indent=2)
        store.local['index_authority_id'] = identity['authority_id']
        store.save_local()
        return cls(store, root, identity['project_id'])

    @property
    def authority(self):
        latest = read_json(self.control / 'identity.json', {})
        return (latest == self.identity and
                self.store.local.get('index_authority_id') == self.identity['authority_id'])

    def manifest(self):
        # Conflicted copies require human reconciliation; do not guess a winner.
        if any(p.name != 'project_manifest.json' for p in self.index.glob('project_manifest*.json')):
            raise ValueError('Conflicting project manifests require owner review.')
        if any(p.name != 'identity.json' for p in self.control.glob('identity*.json')):
            raise ValueError('Conflicting project identities require owner review.')
        if any(p.name != '.project_hub' for p in self.root.glob('.project_hub*') if p.is_dir()):
            raise ValueError('Conflicting project control folders require owner review.')
        value = read_json(self.index / 'project_manifest.json', {})
        if value and value.get('project_id') != self.identity['project_id']:
            raise ValueError('Published index belongs to a different project.')
        return value

    @staticmethod
    def digest(path):
        with Path(path).open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    @staticmethod
    def validate(path):
        with closing(sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Index integrity verification failed.')

    def load(self):
        with self.lock:
            try:
                value = self.manifest()
                if not value:
                    raise ValueError('No committed shared revision is available.')
                revision = str(uuid.UUID(value['revision']))
                target = self.cache / (revision + '.sqlite3')
                source = self.index / 'revisions' / (revision + '.sqlite3')
                expected = value['sha256']
                if len(expected) != 64:
                    raise ValueError('Invalid index checksum.')
                if source.with_suffix('.sqlite3.sha256').read_text(encoding='ascii').strip() != expected:
                    raise ValueError('Index checksum is not synchronized yet.')
                allowed = {source.name, source.with_suffix('.sqlite3.sha256').name}
                if any(p.name not in allowed for p in source.parent.glob(revision + '*')):
                    raise ValueError('Conflicting index snapshots require owner review.')
                if self.revision == revision and self.path == target and target.exists():
                    info = target.stat()
                    if self.verified_stat == (info.st_size, info.st_mtime_ns):
                        self.status = 'Published index available'
                        return self.path
                if not target.exists() or self.digest(target) != expected:
                    temporary = target.with_suffix('.partial')
                    try:
                        shutil.copyfile(source, temporary)
                        if self.digest(temporary) != expected:
                            raise ValueError('Index synchronization incomplete.')
                        self.validate(temporary)
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
                self.validate(target)
                self.path, self.revision = target, revision
                info = target.stat()
                self.verified_stat = (info.st_size, info.st_mtime_ns)
                write_json(self.cache / 'verified.json', value)
                keep = {revision, value.get('previous')}
                for cached in self.cache.glob('*.sqlite3'):
                    if cached.stem not in keep and not cached.name.startswith(('working-', 'job-')):
                        try:
                            cached.unlink()
                        except OSError:
                            pass  # An existing reader can finish before later cache cleanup.
                self.status = 'Published index available'
            except (OSError, ValueError, KeyError, sqlite3.Error):
                self.status = 'Shared revision unavailable or conflicted; using last verified index'
                if self.path:
                    try:
                        info = self.path.stat()
                        if self.verified_stat != (info.st_size, info.st_mtime_ns):
                            self.path = None
                    except OSError:
                        self.path = None
                if self.path is None:
                    try:
                        previous = read_json(self.cache / 'verified.json', {})
                        revision = str(uuid.UUID(previous['revision']))
                        target = self.cache / (revision + '.sqlite3')
                        if previous['project_id'] == self.identity['project_id'] and self.digest(target) == previous['sha256']:
                            self.validate(target)
                            self.path, self.revision = target, revision
                            info = target.stat()
                            self.verified_stat = (info.st_size, info.st_mtime_ns)
                    except (OSError, ValueError, KeyError, sqlite3.Error):
                        pass
                if self.path is None:
                    self.status = 'No verified shared index available; reconnect or wait for the authority'
            return self.path

    def publish(self, working, base):
        if not self.authority:
            raise ValueError('Only the configured indexing authority may publish.')
        current = self.manifest()
        if current.get('revision') != base:
            raise ValueError('The published revision changed. Reload before publishing.')
        self.validate(working)
        revision = str(uuid.uuid4())
        folder = self.index / 'revisions'
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / (revision + '.sqlite3')
        with Path(working).open('rb') as incoming, destination.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush(); os.fsync(outgoing.fileno())
        checksum = self.digest(destination)
        with destination.with_suffix('.sqlite3.sha256').open('x', encoding='ascii') as output:
            output.write(checksum + '\n')
        value = {'project_id': self.identity['project_id'], 'revision': revision,
                 'sha256': checksum, 'published': timestamp(),
                 'authority_id': self.identity['authority_id'], 'previous': base}
        # Snapshot and checksum first, commit pointer last. Old snapshots retained.
        write_json(self.index / 'project_manifest.json', value)
        self.load()
        return value

    def submit(self, kind, payload, job_id=None):
        if kind not in ('refresh', 'mutation'):
            raise ValueError('Unsupported pending operation.')
        if len(json.dumps(payload, allow_nan=False)) > 1024 * 1024:
            raise ValueError('Split this edit into smaller pending requests.')
        identity = str(uuid.UUID(job_id)) if job_id else str(uuid.uuid4())
        folder = self.index / 'pending'
        folder.mkdir(parents=True, exist_ok=True)
        value = {'id': identity, 'project_id': self.identity['project_id'],
                 'kind': kind, 'payload': payload, 'created': timestamp()}
        path = folder / (identity + '.json')
        try:
            with path.open('x', encoding='utf-8') as output:
                json.dump(value, output, allow_nan=False)
        except FileExistsError:
            existing = read_json(path, {})
            if any(existing.get(k) != value[k] for k in ('id','project_id','kind','payload')):
                raise ValueError('Pending request identity already has different contents.') from None
        return identity

    def process_pending(self, catalog):
        from app.services.research_workspace import ResearchWorkspace
        from app.services.sample_intelligence import SampleIntelligence
        targets = {'NativeIndex': catalog, 'ResearchWorkspace': ResearchWorkspace(catalog),
                   'SampleIntelligence': SampleIntelligence(catalog)}
        with catalog.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS shared_jobs(id TEXT PRIMARY KEY, outcome TEXT)')
        for path in sorted((self.index / 'pending').glob('*.json')):
            if path.stat().st_size > 1024 * 1024:
                continue
            try:
                job = read_json(path, {})
                identity = str(uuid.UUID(job['id']))
                if path.stem != identity or job['project_id'] != self.identity['project_id']:
                    continue
                with catalog.connect() as db:
                    if db.execute('SELECT 1 FROM shared_jobs WHERE id=?', (identity,)).fetchone():
                        continue
                if job['kind'] == 'mutation':
                    payload = job['payload']
                    target = payload['target']
                    if target not in PENDING_METHODS:
                        continue
                    owner, method = target.split('.')
                    # A rejected job cannot partially mutate the next snapshot.
                    original = catalog._editing.path
                    temporary = self.cache / ('job-' + uuid.uuid4().hex + '.sqlite3')
                    shutil.copyfile(original, temporary)
                    catalog._editing.path = temporary
                    try:
                        getattr(targets[owner], method)(*payload['args'], **payload['kwargs'])
                        with catalog.connect() as db:
                            db.execute('INSERT INTO shared_jobs VALUES (?,?)', (identity, 'applied'))
                        os.replace(temporary, original)
                    finally:
                        catalog._editing.path = original
                        temporary.unlink(missing_ok=True)
                    continue
                elif job['kind'] != 'refresh':
                    continue
                with catalog.connect() as db:
                    db.execute('INSERT INTO shared_jobs VALUES (?,?)', (identity, 'applied'))
            except (ValueError, TypeError, KeyError, sqlite3.Error, OSError):
                catalog.log('pending_job_requires_review', job=path.stem)

    @contextmanager
    def working(self):
        """Only disposable local SQLite is writable; never a synced database."""
        with self.lock:
            if not self.authority:
                raise ValueError('Indexing is managed by the configured project authority.')
            lease = (self.cache / 'authority.lock').open('a+b')
            try:
                if os.name == 'nt':
                    import msvcrt
                    lease.seek(0); lease.write(b'0'); lease.flush(); lease.seek(0)
                    msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lease.close()
                raise ValueError('The indexing authority already has an active publisher.') from None
            try:
                yield from self._working()
            finally:
                lease.close()

    def _working(self):
        self.load()
        manifest = self.manifest()
        if manifest and (self.path is None or manifest['revision'] != self.revision):
            raise ValueError('Download the latest published revision before indexing.')
        base = self.revision
        path = self.cache / ('working-' + uuid.uuid4().hex + '.sqlite3')
        if self.path:
            shutil.copyfile(self.path, path)
        try:
            yield path, base
        finally:
            for suffix in ('', '-wal', '-shm', '-journal'):
                Path(str(path) + suffix).unlink(missing_ok=True)

    def locations(self):
        project = self.identity['project_id']
        legacy = []
        for source in self.identity.get('sources', []):
            identity = str(uuid.UUID(source['id']))
            relative = normalized_relative(source['relative_root'])
            if relative == '.' or relative.startswith('.project_hub'):
                raise ValueError('Choose a dedicated legacy folder inside the shared project.')
            if not (self.root / relative).resolve().is_relative_to(self.root):
                raise ValueError('Legacy mappings must stay inside the shared project.')
            legacy.append({'id': identity, 'name': source['name'], 'source_label': source['name'],
                'root_path': str(self.root / relative), 'source_type': 'legacy', 'project_type': 'legacy',
                'dataset_status': 'old_test_data', 'read_only': True, 'active': False})
        return {'enabled': True, 'shared_project': project,
                'active': {'id': project, 'name': 'GDL Research', 'source_label': 'GDL Research',
                    'root_path': str(self.root), 'source_type': 'active', 'project_type': 'active',
                    'read_only': False, 'dataset_status': 'current', 'created_date': self.identity['created'], 'active': True},
                'legacy': legacy, 'additional': [], 'projects': [],
                'shared_storage': str(self.root), 'database': str(self.index),
                'generated': str(self.root / 'Generated Outputs'), 'cache': str(self.cache),
                'backups': str(self.index / 'revisions')}
