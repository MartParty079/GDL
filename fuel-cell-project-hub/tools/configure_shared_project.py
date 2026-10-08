"""Explicit owner enrollment and read-only catalog migration into NativeIndex.

Research files are never copied or moved. Legacy files outside the shared root
remain disconnected references until the owner approves a file migration.
"""
import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.storage import Store, write_json, timestamp
from app.services.shared_index import SharedIndex


def import_catalog(shared, source):
    if not shared.authority or shared.manifest():
        raise ValueError('Initial import requires the configured authority and no published revision.')
    with shared.working() as (working, base):
        print('Preparing a consistent read-only catalog copy...', flush=True)
        with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)) as original:
            with closing(sqlite3.connect(working)) as destination:
                original.backup(destination)
        shared.validate(working)
        print('Validating record counts and portable source references...', flush=True)
        with closing(sqlite3.connect(working)) as db:
            sources = {s['id']: s for s in [shared.locations()['active'], *shared.locations()['legacy']]}
            before = {t: db.execute('SELECT count(*) FROM ' + t).fetchone()[0]
                      for t in ('files','research_objects','overrides','relationships')}
            unknown = set(r[0] for r in db.execute('SELECT DISTINCT source FROM files')) - set(sources)
            if unknown:
                raise ValueError('Map every existing source before importing. Original index preserved.')
            with db:
                rows = db.execute('SELECT id,payload FROM files')
                while batch := rows.fetchmany(500):
                    for identity, payload in batch:
                        row = json.loads(payload)
                        row['full_path'] = row['relative_path']
                        source = sources[row['source_id']]
                        if not Path(source['root_path']).is_dir():
                            row['availability'] = 'Disconnected / migration pending'
                            db.execute('UPDATE file_metadata SET availability=? WHERE id=?', (row['availability'], identity))
                        db.execute('UPDATE files SET payload=? WHERE id=?', (json.dumps(row), identity))
                for identity, source in sources.items():
                    relative = Path(source['root_path']).relative_to(shared.root).as_posix()
                    db.execute('UPDATE sources SET root_path=? WHERE id=?', (relative, identity))
                db.execute("UPDATE projects SET root_path='.'")
            after = {t: db.execute('SELECT count(*) FROM ' + t).fetchone()[0] for t in before}
            if before != after:
                raise ValueError('Migration validation failed; original index preserved.')
        value = shared.publish(working, base)
        write_json(shared.index / 'legacy_manifest.json', {'project_id':shared.identity['project_id'],
            'initial_import_revision':value['revision'], 'counts':after,
            'research_files_moved':False, 'outside_root_references':'Owner-approved file migration required'})
        return after


def main():
    from app.edition import BETA
    if not BETA:
        raise ValueError('This development setup tool cannot enroll Stable.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--confirm-owner', action='store_true')
    parser.add_argument('--source-index')
    parser.add_argument('--source-locations', help='Existing local.json; only project_locations are read')
    parser.add_argument('--source-settings', help='Explicitly reviewed portable project-settings JSON, never an auth profile')
    parser.add_argument('--transfer-authority', action='store_true')
    parser.add_argument('--confirm-old-device-retired', action='store_true')
    args = parser.parse_args()
    store = Store()
    project_id, sources = None, []
    if args.source_index:
        if not args.source_locations:
            raise ValueError('Supply existing source mappings for catalog migration.')
        value = json.loads(Path(args.source_locations).read_text(encoding='utf-8'))['project_locations']
        if Path(value['active']['root_path']).resolve() != Path(args.root).resolve():
            raise ValueError('The previous active project must match the fixed shared root.')
        project_id = value['active']['id']
        for number, source in enumerate(value['legacy']):
            sources.append({'id':source['id'], 'name':source['name'],
                            'relative_root':'Legacy Data' if number == 0 else 'Legacy Data ' + str(number + 1)})
    if (Path(args.root) / '.project_hub/identity.json').exists():
        shared = SharedIndex(store, args.root, store.local.get('shared_project_id'))
    else:
        shared = SharedIndex.enroll(store, args.root, confirmed=args.confirm_owner,
                                    project_id=project_id, sources=sources)
    if args.transfer_authority:
        if not args.confirm_owner or not args.confirm_old_device_retired or args.source_index:
            raise ValueError('Owner confirmation and retirement of the old publisher are required for transfer.')
        import uuid
        identity = dict(shared.identity, authority_id=str(uuid.uuid4()), transferred=timestamp())
        write_json(shared.control / 'settings/authority-history' / (uuid.uuid4().hex + '.json'), shared.identity)
        write_json(shared.control / 'identity.json', identity)
        store.local['index_authority_id'] = identity['authority_id']
        store.save_local()
        shared = SharedIndex(store, args.root, identity['project_id'])
    store.attach_shared(args.root)
    counts = import_catalog(shared, args.source_index) if args.source_index else {}
    if shared.authority and not store.project_data('settings/project_settings.json').exists():
        if args.source_settings:
            store.project = json.loads(Path(args.source_settings).read_text(encoding='utf-8'))
        store.save_project(store.project, 'Shared project settings initialized; research files preserved')
    print(json.dumps({'project_id':shared.identity['project_id'], 'authority':shared.authority,
                      'counts':counts, 'research_files_moved':False}))


if __name__ == '__main__':
    main()
