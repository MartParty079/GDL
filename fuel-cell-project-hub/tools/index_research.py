"""Configure personal research locations and perform read-only indexing validation.

Run from the app directory. No source folders are written. The report, catalog,
snapshot backups and personal profile are stored only in configured local data.
"""
import argparse
import gc
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.storage import Store, write_json
from app.services.research_catalog import ProjectLocations, ResearchCatalog
from app.services.project_storage import EXCLUDED, redirects, search_items


def inventory(root):
    result, errors = {}, 0
    def scan(folder):
        nonlocal errors
        try:
            if redirects(folder.lstat()):
                return
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name in EXCLUDED:
                        continue
                    path = Path(entry.path)
                    try:
                        info = path.lstat()
                        if redirects(info):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            scan(path)
                        elif entry.is_file(follow_symlinks=False):
                            result[path.relative_to(root).as_posix()] = (info.st_size, info.st_mtime_ns)
                    except OSError:
                        errors += 1
        except OSError:
            errors += 1
    scan(root)
    return result, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configure-defaults', action='store_true')
    parser.add_argument('--active-root')
    parser.add_argument('--legacy-root')
    parser.add_argument('--verify-sources', action='store_true')
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    store = Store()
    locations = ProjectLocations(store)
    if args.configure_defaults:
        value = locations.defaults()
        if args.active_root:
            value['active']['root_path'] = value['shared_storage'] = str(Path(args.active_root).resolve())
        if args.legacy_root:
            value['legacy'][0]['root_path'] = str(Path(args.legacy_root).resolve())
        ProjectLocations.validate(value)
        backups = Path(value['backups'])
        backups.mkdir(parents=True, exist_ok=True)
        for name in ('local.json', 'project_snapshot.json'):
            path = store.local_dir / name
            if path.exists():
                shutil.copy2(path, backups / (uuid.uuid4().hex + '-' + name))
        locations.save(value)
    if not locations.value.get('enabled'):
        parser.error('Save research locations in Settings first, or use --configure-defaults.')
    store.provider = None
    gc.collect()
    catalog = ResearchCatalog(store, locations)
    catalog.import_snapshots()
    before = {s['id']: inventory(Path(s['root_path'])) for s in locations.sources()} if args.verify_sources else {}
    summary = catalog.refresh(quick=args.quick, progress=lambda count: print(f'Scanned {count:,}', flush=True) if count % 10000 == 0 else None)
    rows = catalog.rows()
    validation = {'sources': locations.status(), 'index_run': summary,
        'current_filter': len(search_items(rows, origin='current', archive='all')),
        'legacy_filter': len(search_items(rows, origin='legacy', archive='all')),
        'combined_filter': len(search_items(rows, archive='all')),
        'legacy_read_only_old_test_data': all(r.get('read_only') and r.get('dataset_status') == 'old_test_data' for r in rows if r.get('provider') == 'ResearchLocal' and r['data_origin'] == 'legacy')}
    if args.verify_sources:
        validation['source_metadata_changes'] = {}
        for source in locations.sources():
            previous, errors_before = before[source['id']]
            after, errors_after = inventory(Path(source['root_path']))
            changed = sum(previous.get(k) != after.get(k) for k in previous.keys() | after.keys())
            validation['source_metadata_changes'][source['name']] = {'changes': changed, 'inventory_errors': errors_before + errors_after}
    write_json(store.local_dir / 'research-validation.json', validation)
    print(json.dumps(validation, indent=2))
    return 0 if not summary['errors'] else 1


if __name__ == '__main__':
    sys.exit(main())
