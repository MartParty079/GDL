import copy
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.storage import Store, ROOT, write_json
from app.services.research_catalog import ProjectLocations, ResearchCatalog, research_category
from app.services.project_storage import search_items, IndexCancelled


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.current, self.legacy = self.root / 'current', self.root / 'legacy'
        self.current.mkdir()
        self.legacy.mkdir()
        self.store = Store(ROOT, self.root / 'profile')
        self.locations = ProjectLocations(self.store)
        value = self.locations.value
        value['active']['root_path'] = str(self.current)
        value['legacy'][0]['root_path'] = str(self.legacy)
        value['shared_storage'] = str(self.current)
        self.locations.save(value)
        self.catalog = ResearchCatalog(self.store, self.locations)

    def tearDown(self):
        self.temp.cleanup()

    def seed(self):
        (self.current / 'image.png').write_bytes(b'identical')
        (self.legacy / 'image.png').write_bytes(b'identical')
        (self.legacy / 'report.txt').write_text('historical report')

    def test_configuration_reloads_without_source_markers(self):
        loaded = ProjectLocations(Store(ROOT, self.root / 'profile'))
        self.assertEqual(loaded.value, self.locations.value)
        self.assertEqual(list(self.current.iterdir()), [])
        self.assertEqual(self.store.project_folder(), str(self.current))

    def test_change_project_and_select_prior_identity(self):
        old = copy.deepcopy(self.locations.value['active'])
        value = copy.deepcopy(self.locations.value)
        value['active']['root_path'] = str(self.root / 'another')
        self.locations.save(value)
        self.assertNotEqual(old['id'], self.locations.value['active']['id'])
        value = copy.deepcopy(self.locations.value)
        value['active'] = old
        self.locations.save(value)
        self.assertEqual(self.locations.value['active']['id'], old['id'])

    def test_nonoverlapping_and_application_owned_paths(self):
        for key in ('database', 'generated', 'cache', 'backups'):
            value = copy.deepcopy(self.locations.value)
            value[key] = str(self.legacy / 'owned')
            with self.assertRaises(ValueError):
                self.locations.save(value)
        value = copy.deepcopy(self.locations.value)
        value['legacy'][0]['root_path'] = str(self.current / 'nested')
        with self.assertRaises(ValueError):
            self.locations.save(value)

    def test_current_legacy_combined_hash_duplicate_and_no_source_writes(self):
        self.seed()
        before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for folder in (self.current, self.legacy) for p in folder.iterdir()}
        summary = self.catalog.refresh()
        rows = self.catalog.rows()
        self.assertEqual(summary['new'], 3)
        self.assertEqual(len(search_items(rows, origin='current')), 1)
        self.assertEqual(len(search_items(rows, origin='legacy')), 2)
        self.assertEqual(len(search_items(rows, query='image')), 2)
        self.assertEqual(summary['duplicates'], 2)
        self.assertTrue(all(r['read_only'] and r['dataset_status'] == 'old_test_data' for r in rows if r['data_origin'] == 'legacy'))
        self.assertEqual(before, {p: (p.stat().st_size, p.stat().st_mtime_ns) for folder in (self.current, self.legacy) for p in folder.iterdir()})

    def test_incremental_updates_and_rename_keep_identity(self):
        self.seed()
        self.catalog.refresh()
        initial = next(r for r in self.catalog.rows() if r['data_origin'] == 'current')
        self.assertEqual(self.catalog.refresh(quick=True)['unchanged'], 3)
        (self.current / 'image.png').rename(self.current / 'renamed.png')
        self.catalog.refresh()
        renamed = next(r for r in self.catalog.rows() if r['data_origin'] == 'current')
        self.assertEqual(initial['id'], renamed['id'])
        (self.current / 'renamed.png').write_bytes(b'changed content')
        self.assertEqual(self.catalog.refresh()['updated'], 1)

    def test_missing_source_preserves_last_known_index(self):
        self.seed()
        self.catalog.refresh()
        self.legacy.rename(self.root / 'offline')
        summary = self.catalog.refresh()
        self.assertGreater(summary['errors'], 0)
        legacy = search_items(self.catalog.rows(), origin='legacy')
        self.assertEqual(len(legacy), 2)
        self.assertTrue(all(r['availability'] == 'Temporarily unavailable' for r in legacy))
        with self.assertRaisesRegex(ValueError, 'unavailable locally'):
            self.catalog.open_item(legacy[0])

    def test_online_only_never_reads_content(self):
        self.seed()
        with patch('app.services.research_catalog.placeholder', return_value=True), patch.object(Path, 'open', side_effect=AssertionError('hydration attempted')):
            # Logging opens are intentionally separate; scan contents must not open.
            with patch.object(self.catalog, 'log'):
                self.catalog.refresh()
        self.assertTrue(all(not r.get('hash') and r['availability'] == 'Online-only' for r in self.catalog.rows()))

    def test_large_resident_files_not_hashed(self):
        (self.current / 'large.bin').write_bytes(b'x' * (1024 * 1024 + 1))
        self.catalog.refresh()
        self.assertEqual(self.catalog.rows()[0]['hash'], '')

    def test_manual_category_tags_title_win_after_rebuild(self):
        self.seed()
        self.catalog.refresh()
        item = self.catalog.rows()[0]
        self.catalog.set_override(item, {'category': 'Standards', 'tags': 'water fuel', 'title': 'Reference', 'notes': 'important'})
        self.catalog.refresh(rebuild=True)
        row = next(r for r in self.catalog.rows() if r['id'] == item['id'])
        self.assertEqual(row['category'], 'Standards')
        self.assertEqual(len(search_items([row], tags='fuel', query='Reference important')), 1)
        self.assertTrue(list((self.root / 'profile/backups').glob('before-rebuild*')))

    def test_categories_and_extension_document_type_filters(self):
        self.assertEqual(research_category('Water Intrusion Testing/raw.csv'), 'Water Intrusion Testing')
        self.assertEqual(research_category('Microscopy/photo.tif'), 'Microscopy')
        self.assertEqual(research_category('code/tool.py'), 'Python / MATLAB / Code')
        self.seed()
        self.catalog.refresh()
        self.assertEqual(len(search_items(self.catalog.rows(), extension='.png', document_type='Image')), 2)

    def test_migration_backs_up_existing_database(self):
        self.seed()
        self.catalog.refresh()
        with self.catalog.connect() as db:
            db.execute('PRAGMA user_version=1')
        migrated = ResearchCatalog(self.store, self.locations)
        self.assertEqual(len(migrated.rows()), 3)
        self.assertTrue(list((self.root / 'profile/backups').glob('before-migration*')))
        with migrated.connect() as db:
            db.execute('PRAGMA user_version=99')
        with self.assertRaises(ValueError):
            ResearchCatalog(self.store, self.locations)

    def test_snapshot_migration_preserves_malformed_input(self):
        path = self.store.local_dir / 'index/file_index.json'
        write_json(path, {'records': [{'id': 'broken'}]})
        before = path.read_bytes()
        self.catalog.import_snapshots()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.catalog.rows(), [])

    def test_copy_import_preserves_original_and_avoids_overwrite(self):
        self.seed()
        self.catalog.refresh()
        item = next(r for r in self.catalog.rows() if r['data_origin'] == 'legacy' and r['name'] == 'image.png')
        before = (self.legacy / 'image.png').stat().st_mtime_ns
        destination = self.catalog.import_current(item)
        self.assertEqual(destination.name, 'image (import 1).png')
        self.assertEqual(destination.read_bytes(), b'identical')
        self.assertEqual((self.legacy / 'image.png').stat().st_mtime_ns, before)

    def test_cancel_does_not_commit_partial_scan(self):
        self.seed()
        with self.assertRaises(IndexCancelled):
            self.catalog.refresh(cancel=lambda: True)
        self.assertEqual(self.catalog.rows(), [])

    def test_likely_and_name_collision_classifications(self):
        rows = [{'name': 'a.txt', 'size': 2, 'modified': 'today', 'hash': ''},
                {'name': 'a.txt', 'size': 2, 'modified': 'today', 'hash': ''}]
        self.catalog.duplicates(rows)
        self.assertEqual(rows[0]['duplicate_status'], 'Likely duplicate')
        rows[1]['hash'], rows[0]['hash'] = 'abc', 'def'
        self.catalog.duplicates(rows)
        self.assertEqual(rows[0]['duplicate_status'], 'Same filename / different contents')

    def test_deleted_record_stays_visible(self):
        self.seed()
        self.catalog.refresh()
        (self.legacy / 'report.txt').unlink()
        self.catalog.refresh()
        row = next(r for r in self.catalog.rows() if r['name'] == 'report.txt')
        self.assertEqual(row['availability'], 'Deleted / moved')
        self.assertEqual(len(search_items([row])), 1)

    def test_existing_michelson_style_cache_is_migrated_as_legacy(self):
        self.store.local['local_project_root'] = str(self.legacy)
        write_json(self.store.local_dir / 'index/file_index.json', {'records': [
            {'id': 'OLD-STABLE-ID', 'relative_path': 'image.png', 'name': 'image.png',
             'category': 'Image', 'size': 9, 'modified': '2025-01-01', 'archived': False}]})
        (self.legacy / 'image.png').write_bytes(b'identical')
        self.catalog.import_snapshots()
        row = self.catalog.rows()[0]
        self.assertEqual(row['data_origin'], 'legacy')
        self.assertTrue(row['read_only'])
        self.assertEqual(self.catalog.summary()['current'], 0)
        self.catalog.refresh()
        self.assertEqual(self.catalog.rows()[0]['id'], 'OLD-STABLE-ID')
        self.assertEqual(self.catalog.summary()['legacy'], 1)

    def test_selected_subfolder_does_not_mark_other_sources_missing(self):
        self.seed()
        (self.current / 'chosen').mkdir()
        (self.current / 'chosen/data.txt').write_text('chosen')
        self.catalog.refresh()
        counts = self.catalog.refresh(selected='chosen', source_ids=[self.locations.value['active']['id']], quick=True)
        self.assertEqual(counts['scanned'], 1)
        self.assertEqual(len(self.catalog.rows()), 4)
        self.assertTrue(all(r['availability'] == 'Locally available' for r in self.catalog.rows()))
        with self.assertRaises(ValueError):
            self.catalog.refresh(selected='../escape')

    def test_catalog_relocation_preserves_data_and_refuses_overwrite(self):
        from app.services.storage_settings import StorageSettings
        self.seed()
        self.catalog.refresh()
        settings = StorageSettings(self.store, None)
        old_path = settings.catalog.path
        value = copy.deepcopy(settings.locations.value)
        value['database'] = str(self.root / 'relocated-index')
        settings.save_locations(value)
        self.assertTrue(old_path.exists())
        self.assertEqual(len(settings.catalog.rows()), 3)
        value = copy.deepcopy(settings.locations.value)
        value['database'] = str(old_path.parent)
        with self.assertRaises(ValueError):
            settings.save_locations(value)

    def test_project_settings_remain_editable_without_writing_previous_legacy_mapping(self):
        self.store.local['local_project_root'] = str(self.legacy)
        value = copy.deepcopy(self.store.project)
        value['goal'] = 'Current research goal'
        self.store.save_project(value)
        self.assertTrue((self.store.local_dir / 'project_settings.json').exists())
        self.assertEqual(list(self.legacy.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
