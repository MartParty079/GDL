"""Single local SQLite index: streaming scans, bounded extraction and FTS5."""
import copy
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from app.services.storage import timestamp, read_json
from app.services.project_locations import ProjectLocations, RESEARCH_CATEGORIES, research_category
from app.services.project_storage import placeholder, redirects, normalized_relative, IndexCancelled
from app.services.file_classifier import classify_file, CATEGORIES
from app.indexing.scanner import discover
from app.indexing.hashing import hash_file
from app.indexing.extractor import extract, DEFAULT_LIMITS, SUPPORTED
from app.indexing.search import match_expression, predicates

SCALARS = ('source_id', 'relative_path', 'name', 'name_key', 'parent_folder', 'extension',
    'source_name', 'project_name', 'data_origin', 'category', 'subcategory', 'document_type',
    'modified', 'availability', 'hash', 'inode', 'signature', 'tags', 'title', 'notes',
    'experiment_id', 'run_id', 'sample_id', 'procedure_id', 'duplicate_status', 'content_status', 'seen_run')


class NativeIndex:
    SCHEMA = 3

    def __init__(self, store, locations=None):
        self.phase = 'Idle'
        self.logging_unavailable = False
        self.store = store
        self.locations = locations or ProjectLocations(store)
        self.path = Path(self.locations.value['database']) / 'research.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()
        self.sync_sources()

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
        self.log('backup_complete', label=label)
        return destination

    def restore(self, backup_path):
        path = Path(backup_path).resolve()
        path.relative_to(Path(self.locations.value['backups']).resolve())
        with closing(sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True)) as source:
            if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('The backup is invalid. The current index was preserved.')
            version = source.execute('PRAGMA user_version').fetchone()[0]
            if not 1 <= version <= self.SCHEMA:
                raise ValueError('Choose a compatible research index backup.')
            self.backup('before-restore')
            with self.connect() as destination:
                source.backup(destination)
        self.migrate()
        self.sync_sources()
        self.log('restore_complete')

    def log(self, event, **values):
        # Database job/error records remain authoritative if a log location is offline.
        try:
            folder = Path(self.locations.value['cache']) / 'logs'
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / 'native-index.jsonl').open('a', encoding='utf-8') as output:
                output.write(json.dumps({'time': timestamp(), 'event': event, **values}) + '\n')
        except OSError:
            self.logging_unavailable = True

    def migrate(self):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > self.SCHEMA:
            raise ValueError('The index needs a newer application; database preserved.')
        if version and version < self.SCHEMA:
            self.backup('before-migration')
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS overrides(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            invalid = db.execute("""SELECT count(*) FROM files WHERE CASE WHEN json_valid(payload)
                THEN json_type(payload,'$.id') IS NOT 'text' OR json_type(payload,'$.name') IS NOT 'text'
                OR json_type(payload,'$.relative_path') IS NOT 'text' OR json_type(payload,'$.modified') IS NOT 'text'
                OR json_type(payload,'$.size') IS NOT 'integer' ELSE 1 END""").fetchone()[0]
            if invalid:
                raise ValueError('Invalid index records; existing database preserved.')
            db.execute('CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,root_path TEXT,created_at TEXT,active INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,root_path TEXT,type TEXT,read_only INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS directories(source TEXT,path TEXT,parent TEXT,modified TEXT,PRIMARY KEY(source,path))')
            db.execute('CREATE TABLE IF NOT EXISTS file_metadata(id TEXT PRIMARY KEY,' + ','.join(c + ' TEXT' for c in SCALARS) + ',size INTEGER,archived INTEGER,favorite INTEGER)')
            db.execute('CREATE INDEX IF NOT EXISTS native_path ON file_metadata(source_id,relative_path)')
            db.execute('CREATE INDEX IF NOT EXISTS native_inode ON file_metadata(source_id,inode)')
            db.execute('CREATE INDEX IF NOT EXISTS native_hash ON file_metadata(hash)')
            db.execute('CREATE INDEX IF NOT EXISTS native_name ON file_metadata(name_key,size,modified)')
            db.execute('CREATE INDEX IF NOT EXISTS native_source ON file_metadata(source_id,data_origin,category)')
            db.execute('CREATE TABLE IF NOT EXISTS content_index(id TEXT PRIMARY KEY,text TEXT,metadata TEXT,status TEXT,signature TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS fts_keys(id TEXT PRIMARY KEY)')
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(file_id UNINDEXED,name,title,tags,category,project,source,path,body,tokenize="unicode61")')
            db.execute('CREATE TABLE IF NOT EXISTS index_runs(id TEXT PRIMARY KEY,started TEXT,ended TEXT,mode TEXT,sources TEXT,result TEXT,summary TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS index_errors(run_id TEXT,file_id TEXT,path TEXT,message TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS relationships(from_id TEXT,to_id TEXT,type TEXT,PRIMARY KEY(from_id,to_id,type))')
            if version < self.SCHEMA:
                cursor = db.execute('SELECT payload FROM files')
                while batch := cursor.fetchmany(250):
                    for (payload,) in batch:
                        row = json.loads(payload)
                        self.upsert(db, row, update_search=True)
                db.execute('PRAGMA user_version=3')
        if version != self.SCHEMA:
            self.log('migration', previous=version, current=self.SCHEMA)

    def sync_sources(self):
        value = self.locations.value
        project = value['active']
        with self.connect() as db:
            db.execute('UPDATE projects SET active=0')
            for p in [project, *value.get('projects', [])]:
                db.execute('INSERT OR REPLACE INTO projects VALUES (?,?,?,?,?)',
                    (p['id'], p['name'], p['root_path'], p.get('created_date', timestamp()), int(p['id'] == project['id'])))
            for source in self.locations.sources():
                db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?)',
                    (source['id'], project['id'], source.get('source_label', source['name']), source['root_path'], source['source_type'], int(source['read_only'])))

    def upsert(self, db, row, update_search=False, body=None):
        row = dict(row)
        override = db.execute('SELECT payload FROM overrides WHERE id=?', (row['id'],)).fetchone()
        if override:
            row.update(json.loads(override[0]), classification_source='manual')
        row.setdefault('source_id', 'retired-snapshot')
        row.setdefault('document_type', row.get('category', 'Other'))
        row.setdefault('content_status', 'Pending')
        row.setdefault('archived', False)
        row['name_key'] = row['name'].casefold()
        for key in SCALARS:
            row.setdefault(key, '')
        row.setdefault('favorite', False)
        row['provider'] = 'ResearchLocal' if row['source_id'] in {s['id'] for s in self.locations.sources()} else 'RetiredSnapshot'
        values = [row[k] if not isinstance(row[k], (dict, list)) else json.dumps(row[k]) for k in SCALARS]
        db.execute('INSERT INTO files VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET source=excluded.source,payload=excluded.payload', (row['id'], row['source_id'], json.dumps(row)))
        db.execute('INSERT INTO file_metadata VALUES (' + ','.join('?' for _ in range(len(SCALARS) + 4)) + ') ON CONFLICT(id) DO UPDATE SET ' +
                   ','.join(k + '=excluded.' + k for k in (*SCALARS, 'size', 'archived', 'favorite')),
                   [row['id'], *values, row['size'], int(row['archived']), int(row['favorite'])])
        if update_search:
            if body is None:
                content = db.execute('SELECT text FROM content_index WHERE id=?', (row['id'],)).fetchone()
                body = content[0] if content else ''
            db.execute('INSERT OR IGNORE INTO fts_keys VALUES (?)', (row['id'],))
            search_id = db.execute('SELECT rowid FROM fts_keys WHERE id=?', (row['id'],)).fetchone()[0]
            db.execute('DELETE FROM content_fts WHERE rowid=?', (search_id,))
            db.execute('INSERT INTO content_fts(rowid,file_id,name,title,tags,category,project,source,path,body) VALUES (?,?,?,?,?,?,?,?,?,?)', (search_id, row['id'], row['name'], row['title'], row['tags'],
                row['category'], row['project_name'], row['source_name'], row['relative_path'], '\n'.join((row.get('notes', ''), row.get('description', ''), body))))
        return row

    def content_preview(self, identity):
        with self.connect() as db:
            row = db.execute('SELECT substr(text,1,5000),metadata,status FROM content_index WHERE id=?', (identity,)).fetchone()
        return {'preview': row[0], 'metadata': json.loads(row[1]), 'status': row[2]} if row else {'status': 'Pending'}

    def query(self, query='', offset=0, limit=200, **filters):
        sources = [s['id'] for s in self.locations.sources()]
        clauses, args = predicates(filters, sources)
        expression = match_expression(query)
        join = ' JOIN content_fts ON content_fts.file_id=m.id' if expression else ''
        order = 'm.data_origin<>\'current\',m.relative_path COLLATE NOCASE,m.id'
        if expression:
            clauses.append('content_fts MATCH ?')
            args.append(expression)
            order = "CASE WHEN lower(m.name)=lower(?) THEN 0 WHEN instr(lower(m.name),lower(?))>0 THEN 1 ELSE 2 END,bm25(content_fts,0,10,8,6,4,2,2,1,3),m.data_origin<>'current',m.id"
        where = ' AND '.join(clauses)
        with self.connect() as db:
            total = db.execute('SELECT count(*) FROM file_metadata m' + join + ' WHERE ' + where, args).fetchone()[0]
            rank_args = [query, query] if expression else []
            data = db.execute('SELECT f.payload,m.duplicate_status FROM file_metadata m JOIN files f ON f.id=m.id' + join +
                ' WHERE ' + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', [*args, *rank_args, min(max(int(limit), 1), 1000), max(int(offset), 0)]).fetchall()
        rows = []
        for payload, duplicate in data:
            row = json.loads(payload)
            row['duplicate_status'] = duplicate
            rows.append(row)
        return rows, total

    def rows(self, all_sources=False):
        """Compatibility diagnostics only; the UI and scanner use SQL pages."""
        with self.connect() as db:
            query = 'SELECT f.payload,m.duplicate_status FROM files f JOIN file_metadata m ON m.id=f.id'
            args = []
            if not all_sources:
                query += ' WHERE m.source_id IN (' + ','.join('?' for _ in self.locations.sources()) + ')'
                args = [s['id'] for s in self.locations.sources()]
            return [dict(json.loads(p), duplicate_status=d) for p, d in db.execute(query, args)]

    def facets(self):
        result = {}
        sources = [s['id'] for s in self.locations.sources()]
        for field in ('category', 'extension', 'document_type', 'source_name', 'project_name', 'availability', 'duplicate_status', 'experiment_id', 'run_id', 'sample_id', 'procedure_id'):
            with self.connect() as db:
                result[field] = [v for (v,) in db.execute('SELECT DISTINCT ' + field + ' FROM file_metadata WHERE source_id IN (' +
                    ','.join('?' for _ in sources) + ') AND ' + field + "<>'' ORDER BY 1", sources)]
        return result

    def summary(self):
        ids = [s['id'] for s in self.locations.sources()]
        where = 'source_id IN (' + ','.join('?' for _ in ids) + ')'
        with self.connect() as db:
            totals = dict(db.execute('SELECT data_origin,count(*) FROM file_metadata WHERE ' + where + ' GROUP BY data_origin', ids))
            statuses = dict(db.execute('SELECT content_status,count(*) FROM file_metadata WHERE ' + where + ' GROUP BY content_status', ids))
            online = db.execute("SELECT count(*) FROM file_metadata WHERE " + where + " AND availability='Online-only'", ids).fetchone()[0]
            duplicates = db.execute("SELECT count(*) FROM file_metadata WHERE " + where + " AND duplicate_status<>''", ids).fetchone()[0]
            metadata = dict(db.execute('SELECT key,value FROM metadata'))
        content_count = sum(statuses.get(s, 0) for s in ('Content indexed', 'Partial'))
        return dict(current=totals.get('current', 0), legacy=totals.get('legacy', 0), reference=totals.get('reference', 0), archive=totals.get('archive', 0),
            last_indexed=metadata.get('last_indexed', ''), sources=len(ids), last_run=json.loads(metadata.get('last_summary', '{}')),
            content_indexed=content_count, metadata_only=sum(totals.values()) - content_count, online_only=online,
            duplicates=duplicates, content_statuses=statuses)

    def set_override(self, item, values):
        allowed = {'category', 'subcategory', 'experiment_id', 'run_id', 'sample_id', 'procedure_id', 'legacy_note', 'tags', 'title', 'notes', 'description', 'favorite'}
        if ('favorite' in values and not isinstance(values['favorite'], bool)) or set(values) - allowed or any(not isinstance(v, str) for k, v in values.items() if k != 'favorite'):
            raise ValueError('Unsupported metadata override.')
        if values.get('category') and values['category'] not in (*CATEGORIES, *RESEARCH_CATEGORIES):
            raise ValueError('Choose a supported category.')
        with self.connect() as db:
            previous = db.execute('SELECT payload FROM overrides WHERE id=?', (item['id'],)).fetchone()
            overrides = {**(json.loads(previous[0]) if previous else {}), **values}
            db.execute('INSERT OR REPLACE INTO overrides VALUES (?,?)', (item['id'], json.dumps(overrides)))
            row = db.execute('SELECT payload FROM files WHERE id=?', (item['id'],)).fetchone()
            if row:
                self.upsert(db, json.loads(row[0]), update_search=True)
        self.log('manual_metadata', file_id=item['id'])

    def relate(self, from_id, to_id, kind='related_to'):
        if kind not in ('derived_from', 'related_to', 'supersedes', 'previous_version', 'references') or from_id == to_id:
            raise ValueError('Choose two different files and a supported relationship.')
        with self.connect() as db:
            if db.execute('SELECT count(*) FROM files WHERE id IN (?,?)', (from_id, to_id)).fetchone()[0] != 2:
                raise ValueError('Both files must be indexed.')
            db.execute('INSERT OR REPLACE INTO relationships VALUES (?,?,?)', (from_id, to_id, kind))

    def related(self, identity):
        with self.connect() as db:
            return [dict(from_id=a, to_id=b, type=t) for a, b, t in db.execute('SELECT * FROM relationships WHERE from_id=? OR to_id=?', (identity, identity))]

    def history(self):
        with self.connect() as db:
            return [dict(id=i, started=a, ended=b, mode=m, sources=json.loads(s), result=r, summary=json.loads(c))
                for i, a, b, m, s, r, c in db.execute('SELECT * FROM index_runs ORDER BY started DESC LIMIT 100')]

    def errors(self, run_id=None, limit=100):
        with self.connect() as db:
            rows = db.execute('SELECT run_id,file_id,path,message FROM index_errors' +
                (' WHERE run_id=?' if run_id else '') + ' ORDER BY rowid DESC LIMIT ?',
                ([run_id] if run_id else []) + [min(max(int(limit), 1), 1000)]).fetchall()
        return [dict(run_id=r, file_id=f, path=p, message=m) for r, f, p, m in rows]

    def duplicate_analysis(self, db):
        db.execute("UPDATE file_metadata SET duplicate_status=''")
        db.execute("""UPDATE file_metadata SET duplicate_status='Same filename / different contents' WHERE name_key IN
            (SELECT name_key FROM file_metadata WHERE availability<>'Deleted / moved' GROUP BY name_key
             HAVING count(DISTINCT size)>1 OR count(DISTINCT nullif(hash,''))>1)""")
        db.execute("""UPDATE file_metadata SET duplicate_status='Likely duplicate' WHERE duplicate_status='' AND
            (name_key,size,modified) IN (SELECT name_key,size,modified FROM file_metadata WHERE availability<>'Deleted / moved'
             GROUP BY name_key,size,modified HAVING count(*)>1)""")
        db.execute("""UPDATE file_metadata SET duplicate_status='Exact duplicate' WHERE hash<>'' AND hash IN
            (SELECT hash FROM file_metadata WHERE hash<>'' AND availability<>'Deleted / moved' GROUP BY hash HAVING count(*)>1)""")
        db.execute("""UPDATE file_metadata SET duplicate_status='Potential renamed copy' WHERE duplicate_status='Exact duplicate' AND hash IN
            (SELECT hash FROM file_metadata WHERE hash<>'' GROUP BY hash HAVING count(DISTINCT name_key)>1)""")

    @staticmethod
    def duplicates(rows):
        groups = defaultdict(list)
        for row in rows:
            row['duplicate_status'] = ''
            groups[row['name'].casefold()].append(row)
        for group in groups.values():
            if len(group) < 2:
                continue
            same = len({r.get('hash') for r in group if r.get('hash')}) == 1 and all(r.get('hash') for r in group)
            different = len({r['size'] for r in group}) > 1 or len({r.get('hash') for r in group if r.get('hash')}) > 1
            for row in group:
                row['duplicate_status'] = 'Exact duplicate' if same else 'Same filename / different contents' if different else 'Likely duplicate'

    def rebuild_search(self, cancel=None, progress=None):
        self.phase = 'Rebuilding search index'
        self.backup('before-search-rebuild')
        run_id, count, result = str(uuid.uuid4()), 0, 'Complete'
        with self.connect() as db:
            db.execute('INSERT INTO index_runs VALUES (?,?,?,?,?,?,?)',
                (run_id, timestamp(), '', 'search', json.dumps([s['id'] for s in self.locations.sources()]), 'Rebuilding search', '{}'))
        try:
            with self.connect() as db:
                db.execute('DELETE FROM content_fts')
                cursor = db.execute('SELECT payload FROM files')
                while batch := cursor.fetchmany(250):
                    if cancel and cancel():
                        raise IndexCancelled('Search rebuild cancelled; previous search index preserved.')
                    for (payload,) in batch:
                        self.upsert(db, json.loads(payload), update_search=True)
                        count += 1
                    if progress:
                        progress(count)
            self.log('search_rebuilt', files=count)
            return {'scanned': count, 'errors': 0}
        except IndexCancelled:
            result = 'Cancelled'
            raise
        except Exception:
            result = 'Failed'
            raise
        finally:
            with self.connect() as db:
                db.execute('UPDATE index_runs SET ended=?,result=?,summary=? WHERE id=?',
                    (timestamp(), result, json.dumps({'scanned': count, 'errors': int(result == 'Failed')}), run_id))

    def refresh(self, rebuild=False, cancel=None, progress=None, source_ids=None, selected=None, quick=False, mode=None):
        if mode == 'search':
            return self.rebuild_search(cancel, progress)
        if rebuild:
            self.backup('before-rebuild')
        self.phase = 'Scanning'
        run_id, started = str(uuid.uuid4()), timestamp()
        counts = dict(scanned=0, new=0, updated=0, unchanged=0, moved=0, current=0, legacy=0,
            duplicates=0, errors=0, unsupported=0, unavailable=0, online_only=0, content_indexed=0, metadata_only=0)
        sources = [s for s in self.locations.sources() if source_ids is None or s['id'] in source_ids]
        selected = normalized_relative(selected) if selected else ''
        limits = {**DEFAULT_LIMITS, **self.store.local.get('native_indexing', {}).get('limits', {})}
        rules = self.store.local.get('native_category_rules') or read_json(self.store.config_dir / 'indexing_rules.json', {}).get('keywords', {'astm': 'Standards', 'microscopy': 'Microscopy', 'water intrusion': 'Water Intrusion Testing'})
        hash_budget = limits['hash_budget']
        scan_mode = 'rebuild' if rebuild else 'quick' if quick else 'full'
        self.log('index_start', mode=scan_mode, sources=[s['id'] for s in sources])
        with self.connect() as db:
            db.execute('INSERT INTO index_runs VALUES (?,?,?,?,?,?,?)', (run_id, started, '', scan_mode, json.dumps([s['id'] for s in sources]), 'Scanning', '{}'))
        result = 'Complete'
        try:
            for source in sources:
                root = Path(source['root_path'])
                uncertain = []
                with self.connect() as db:
                    for path, info, problem in discover(root / selected if selected else root, cancel):
                        relative = path.relative_to(root).as_posix()
                        if info is None:
                            uncertain.append(relative)
                            counts['errors'] += 1
                            self.log('source_unavailable', source_id=source['id'], path=relative, message=problem)
                            db.execute('INSERT INTO index_errors VALUES (?,?,?,?)', (run_id, '', relative, problem))
                            continue
                        if problem == 'directory':
                            db.execute('INSERT OR REPLACE INTO directories VALUES (?,?,?,?)', (source['id'], relative, path.parent.relative_to(root).as_posix(), datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()))
                            continue
                        counts['scanned'] += 1
                        signature = [info.st_size, info.st_mtime_ns]
                        previous = db.execute('SELECT f.payload FROM file_metadata m JOIN files f ON f.id=m.id WHERE m.source_id=? AND m.relative_path=?', (source['id'], relative)).fetchone()
                        prior = json.loads(previous[0]) if previous else None
                        inode = str(info.st_dev) + ':' + str(info.st_ino) if info.st_ino else ''
                        moved = False
                        if not prior and inode:
                            candidates = db.execute('SELECT f.payload FROM file_metadata m JOIN files f ON f.id=m.id WHERE m.source_id=? AND m.inode=? LIMIT 2', (source['id'], inode)).fetchall()
                            if len(candidates) == 1:
                                candidate = json.loads(candidates[0][0])
                                if not (root / candidate['relative_path']).exists():
                                    prior, moved = candidate, True
                        identity = prior['id'] if prior else str(uuid.uuid5(uuid.UUID(source['id']), relative.casefold() if os.name == 'nt' else relative))
                        changed = not prior or prior.get('signature') != signature
                        resident = not placeholder(info)
                        row = dict(prior or {})
                        row.update(id=identity, source_id=source['id'], source_type=source['source_type'],
                            source_name=source.get('source_label', source['name']), project_name=source['name'],
                            dataset_status=source['dataset_status'], read_only=source['read_only'], full_path=str(path),
                            name=path.name, relative_path=relative, parent_folder=path.parent.relative_to(root).as_posix(),
                            extension=path.suffix.lower(), size=info.st_size, signature=signature, inode=inode,
                            created=datetime.fromtimestamp(getattr(info, 'st_birthtime', info.st_ctime), timezone.utc).isoformat(),
                            modified=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(), indexed=timestamp(),
                            availability='Locally available' if resident else 'Online-only', archived=source['source_type'] == 'archive' or '99_Archive' in path.relative_to(root).parts, state='active',
                            data_origin={'active': 'current', 'legacy': 'legacy'}.get(source['source_type'], source['source_type']),
                            legacy_project_id=source['id'] if source['source_type'] == 'legacy' else '',
                            legacy_project_name=source['name'] if source['source_type'] == 'legacy' else '', seen_run=run_id)
                        content = db.execute('SELECT signature,status FROM content_index WHERE id=?', (identity,)).fetchone()
                        content_signature = json.dumps([signature, limits], sort_keys=True)
                        process = changed or rebuild or not content or content[0] != content_signature or (not resident and content[1] != 'Online-only') or (resident and limits['enabled'] and content[1] in ('Online-only', 'Extraction disabled'))
                        extracted = None
                        if changed or moved or rebuild:
                            row.update(classify_file(relative))
                            row.update(document_type=row['category'], category=research_category(relative), hash='')
                        if process:
                            self.phase = 'Extracting content' if resident else 'Indexing metadata'
                            extracted = extract(path, limits) if resident else {'text': '', 'metadata': {}, 'status': 'Online-only', 'error': ''}
                            row['content_status'] = extracted['status']
                            row['extracted_metadata'] = extracted['metadata']
                            if extracted['metadata'].get('title'):
                                row['title'] = extracted['metadata']['title']
                            context = (row.get('title', '') + ' ' + extracted['text'][:10000]).casefold()
                            if row['category'] == 'Miscellaneous':
                                row['category'] = next((category for word, category in rules.items() if word.casefold() in context), row['category'])
                            db.execute('INSERT OR REPLACE INTO content_index VALUES (?,?,?,?,?)', (identity, extracted['text'], json.dumps(extracted['metadata']), extracted['status'], content_signature))
                            if extracted['error']:
                                self.log('file_error', file_id=identity, path=relative, message=extracted['error'])
                                counts['errors'] += 1
                                db.execute('INSERT INTO index_errors VALUES (?,?,?,?)', (run_id, identity, relative, extracted['error']))
                        if process and resident:
                            try:
                                after = path.stat()
                                if [after.st_size, after.st_mtime_ns] != signature:
                                    row['availability'] = 'Still syncing'
                                    row['signature'] = []  # Retry content next refresh.
                            except OSError:
                                row['availability'] = 'Temporarily unavailable'
                        if resident and (changed or rebuild or not quick and not row.get('hash')) and info.st_size <= limits['max_hash_bytes'] and info.st_size <= hash_budget:
                            try:
                                row['hash'], availability = hash_file(path, signature)
                                hash_budget -= info.st_size
                                if availability != 'Locally available':
                                    row['availability'] = availability
                            except OSError:
                                row['availability'] = 'Temporarily unavailable'
                                counts['errors'] += 1
                                db.execute('INSERT INTO index_errors VALUES (?,?,?,?)', (run_id, identity, relative, 'Hash unavailable; metadata retained'))
                        self.upsert(db, row, update_search=process or moved or rebuild, body=extracted['text'] if extracted else None)
                        counts['new' if not prior else 'updated' if changed else 'unchanged'] += 1
                        counts['moved'] += int(moved)
                        if row['data_origin'] in ('current', 'legacy'):
                            counts[row['data_origin']] += 1
                        counts['online_only'] += int(not resident)
                        counts['unsupported'] += int(path.suffix.lower() not in SUPPORTED)
                        counts['content_indexed' if row.get('content_status') in ('Content indexed', 'Partial') else 'metadata_only'] += 1
                        if counts['scanned'] % 250 == 0:
                            db.commit()
                            if progress:
                                progress(counts['scanned'])
                    # Reconcile missing records only after completing this source.
                    cursor = db.execute('SELECT f.payload FROM file_metadata m JOIN files f ON f.id=m.id WHERE m.source_id=? AND m.seen_run<>?', (source['id'], run_id))
                    while missing_batch := cursor.fetchmany(250):
                        for (payload,) in missing_batch:
                            row = json.loads(payload)
                            rel = row['relative_path']
                            if selected and not (rel == selected or rel.startswith(selected.rstrip('/') + '/')):
                                continue
                            row['availability'] = 'Temporarily unavailable' if any(p == '.' or rel == p or rel.startswith(p + '/') for p in uncertain) else 'Deleted / moved'
                            counts['unavailable'] += 1
                            self.upsert(db, row)
                        db.commit()
            if cancel and cancel():
                raise IndexCancelled('Index cancelled; completed batches are preserved.')
            self.phase = 'Checking duplicates'
            if progress:
                progress(counts['scanned'])
            with self.connect() as db:
                self.duplicate_analysis(db)
                counts['duplicates'] = db.execute("SELECT count(*) FROM file_metadata WHERE duplicate_status<>''").fetchone()[0]
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('last_indexed', timestamp()))
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('last_summary', json.dumps(counts)))
            result = 'Completed with Errors' if counts['errors'] else 'Complete'
            self.phase = result
            self.log('index_complete', **counts)
            return counts
        except IndexCancelled:
            result = 'Cancelled'
            self.phase = result
            self.log('index_cancelled')
            raise
        except Exception:
            result = 'Failed'
            self.phase = result
            self.log('index_failed', action='database and source files preserved')
            raise
        finally:
            with self.connect() as db:
                db.execute('UPDATE index_runs SET ended=?,result=?,summary=? WHERE id=?', (timestamp(), result, json.dumps(counts), run_id))

    def import_snapshots(self):
        # v2 migration already preserves prior provider records. Do not import
        # abandoned remote snapshots into the native filesystem catalog.
        return None

    def ingest(self, records):
        with self.connect() as db:
            for row in records:
                self.upsert(db, row, update_search=True)

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
