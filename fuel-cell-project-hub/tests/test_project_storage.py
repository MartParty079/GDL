import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.storage import Store, ROOT, read_json, write_json
from app.services.project_storage import (LocalOneDriveProvider, STANDARD_FOLDERS, classify,
    infer_relationships, normalized_relative, placeholder, redirects, search_items, IndexCancelled)


class ProjectStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "Synced Project"
        self.root.mkdir()
        (self.root / "03_Experiments").mkdir()
        self.provider = LocalOneDriveProvider(self.root, self.base / "cache")
        self.provider.accept_root("Fuel Cell Capstone")

    def tearDown(self):
        self.temp.cleanup()

    def file(self, relative, content=b"data"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def store(self):
        return Store(ROOT, self.base / "profile")

    def test_select_project_root_and_connect(self):
        store = self.store()
        store.connect_storage(self.root)
        self.assertEqual(store.provider.status(), "Connected")

    def test_root_saved_only_in_local_profile(self):
        store = self.store()
        store.connect_storage(self.root)
        loaded = read_json(store.local_dir / "local.json", {})
        self.assertEqual(loaded["local_project_root"], str(self.root.resolve()))
        self.assertNotIn(str(self.root), json.dumps(store.project))
        self.assertNotIn(str(self.root), (self.root / ".projecthub/project.json").read_text())

    def test_shared_settings_cannot_store_absolute_paths(self):
        store = self.store()
        store.connect_storage(self.root)
        value = copy.deepcopy(store.project)
        value["links"]["Reports"] = "C:/Users/Someone/Reports"
        before = (self.root / ".projecthub/project.json").read_bytes()
        with self.assertRaises(ValueError):
            store.save_project(value)
        self.assertEqual((self.root / ".projecthub/project.json").read_bytes(), before)

    def test_marker_schema_validation(self):
        write_json(self.root / ".projecthub/project.json", {"schema_version": 2, "project_name": "Future"})
        with self.assertRaises(ValueError):
            self.provider.validate_root()

    def test_invalid_marker_preserved(self):
        marker = self.root / ".projecthub/project.json"
        marker.write_text("{invalid")
        with self.assertRaises(ValueError):
            self.provider.accept_root("Do not replace")
        self.assertEqual(marker.read_text(), "{invalid")

    def test_missing_folders_detected(self):
        missing = self.provider.missing_folders()
        self.assertIn("99_Archive", missing)
        self.assertNotIn("03_Experiments", missing)
        self.assertNotIn(".projecthub", missing)

    def test_create_missing_folders_preserves_existing_data(self):
        path = self.file("03_Experiments/existing.txt", b"keep")
        self.provider.create_missing_folders()
        self.assertEqual(self.provider.missing_folders(), [])
        self.assertEqual(path.read_bytes(), b"keep")

    def test_normal_files_indexed_with_required_fields(self):
        self.file("03_Experiments/image.tif")
        summary = self.provider.refresh()
        self.assertEqual(summary["files"], 1)
        item = self.provider.get_item("03_Experiments/image.tif")
        for key in ("id", "relative_path", "name", "extension", "size", "modified", "category", "archived", "experiment_id", "run_id", "sample_id", "procedure_id"):
            self.assertIn(key, item)
        self.assertNotIn("content", item)

    def test_excluded_folders_and_transient_files_not_indexed(self):
        for folder in (".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", ".projecthub"):
            self.file(folder + "/junk.txt")
        for name in ("~$office.docx", "partial.part", "downloading.crdownload", "cache.tmp"):
            self.file("03_Experiments/" + name)
        self.file("03_Experiments/keep.csv")
        self.provider.refresh()
        self.assertEqual([i["name"] for i in self.provider.list_items()], ["keep.csv"])

    def test_image_classification(self):
        self.assertEqual(classify("test.TIFF"), "Image")

    def test_video_classification(self):
        self.assertEqual(classify("test.mp4"), "Video")

    def test_spreadsheet_classification(self):
        self.assertEqual(classify("test.xlsm"), "Spreadsheet")

    def test_document_classification(self):
        self.assertEqual(classify("test.pdf"), "Document")

    def test_code_classification(self):
        self.assertEqual(classify("test.jsl"), "Code")

    def test_folder_context_classification(self):
        for folder, category in (("01_Procedures", "Procedure"), ("07_Reports", "Report"), ("08_Reference", "Reference")):
            self.assertEqual(classify(folder + "/file.docx"), category)

    def test_relative_paths_normalized_and_boundaries_enforced(self):
        self.assertEqual(normalized_relative("03_Experiments\\E-001\\file.csv"), "03_Experiments/E-001/file.csv")
        for path in ("../outside", "C:/Users/Other", "/outside", "03_Experiments/../../outside", "file.txt:stream"):
            with self.assertRaises(ValueError):
                self.provider.path(path)

    def test_incremental_update_preserves_ids_and_logs_modification(self):
        path = self.file("04_Raw_Data/data.csv")
        self.provider.refresh()
        original = self.provider.get_item("04_Raw_Data/data.csv")
        path.write_bytes(b"modified data")
        summary = self.provider.refresh()
        item = self.provider.get_item("04_Raw_Data/data.csv")
        self.assertEqual(item["id"], original["id"])
        self.assertTrue(item["modified_after_initial_index"])
        self.assertTrue(item["raw_data"])
        self.assertEqual(summary["changes"]["modified"], 1)

    def test_deleted_records_retained_and_hidden_from_active_search(self):
        path = self.file("03_Experiments/deleted.csv")
        self.provider.refresh()
        path.unlink()
        summary = self.provider.refresh()
        self.assertEqual(summary["changes"]["removed"], 1)
        self.assertEqual(self.provider.list_items()[0]["state"], "unavailable")
        self.assertEqual(search_items(self.provider.list_items()), [])

    def test_reappearing_file_retains_identity(self):
        path = self.file("03_Experiments/restored.csv")
        self.provider.refresh()
        original = self.provider.list_items()[0]["id"]
        path.unlink()
        self.provider.refresh()
        path.write_bytes(b"restored")
        self.provider.refresh()
        self.assertEqual(self.provider.list_items()[0]["id"], original)
        self.assertEqual(self.provider.list_items()[0]["state"], "active")

    def test_archive_detection_and_default_hiding(self):
        self.file("99_Archive/video.mp4")
        self.provider.refresh()
        self.assertTrue(self.provider.list_items()[0]["archived"])
        self.assertEqual(search_items(self.provider.list_items()), [])
        self.assertEqual(len(search_items(self.provider.list_items(), archive="all")), 1)

    def test_sample_id_inference(self):
        self.assertEqual(infer_relationships("03_Experiments/E-20261010-A/R03/S-001/video.mp4")["sample_id"], "S-001")

    def test_experiment_id_inference(self):
        self.assertEqual(infer_relationships("03_Experiments/E-20261010-A/R03/video.mp4")["experiment_id"], "E-20261010-A")

    def test_run_id_inference(self):
        self.assertEqual(infer_relationships("03_Experiments/E-20261010-A/R03/video.mp4")["run_id"], "E-20261010-A-R03")

    def test_explicit_metadata_preferred_and_inherited(self):
        self.file("03_Experiments/E-001/experiment.json", json.dumps({"sample_id": "S-001", "procedure": {"id": "P-001", "version": "2.1"}}).encode())
        self.file("03_Experiments/E-001/R03/run.json", json.dumps({"sample_id": "S-002"}).encode())
        self.file("03_Experiments/E-001/R03/video/capture.mp4")
        self.provider.refresh()
        item = self.provider.get_item("03_Experiments/E-001/R03/video/capture.mp4")
        self.assertEqual(item["sample_id"], "S-002")
        self.assertEqual(item["procedure_id"], "P-001")
        self.assertEqual(item["procedure_version"], "2.1")

    def test_open_indexed_file(self):
        file = self.file("03_Experiments/data.csv")
        self.provider.refresh()
        with patch("app.services.project_storage.os.startfile") as start:
            self.provider.open_item("03_Experiments/data.csv")
        start.assert_called_once_with(str(file.resolve()))

    def test_open_containing_folder(self):
        file = self.file("03_Experiments/data.csv")
        with patch("app.services.project_storage.os.startfile") as start:
            self.provider.open_containing_folder("03_Experiments/data.csv")
        start.assert_called_once_with(str(file.parent.resolve()))

    def test_search_filename_case_insensitive(self):
        self.file("03_Experiments/My Capture.mp4")
        self.provider.refresh()
        self.assertEqual(len(search_items(self.provider.list_items(), query="my CAPTURE")), 1)

    def test_search_sample_across_experiments_without_duplication(self):
        for experiment in ("E-001", "E-002"):
            self.file(f"03_Experiments/{experiment}/experiment.json", b'{"sample_id":"S-001"}')
            self.file(f"03_Experiments/{experiment}/R01/video.mp4")
        self.provider.refresh()
        self.assertEqual(len(search_items(self.provider.list_items(), query="S-001", category="Video")), 2)

    def test_category_filter(self):
        self.file("03_Experiments/video.mp4")
        self.file("03_Experiments/image.png")
        self.provider.refresh()
        self.assertEqual([i["name"] for i in search_items(self.provider.list_items(), category="Video")], ["video.mp4"])

    def test_all_relationship_and_date_filters(self):
        self.file("03_Experiments/E-001/R01/S-001/P-001/data.csv")
        self.provider.refresh()
        results = search_items(self.provider.list_items(), experiment="E-001", run="E-001-R01", sample="S-001", procedure="P-001", date_from="2000-01-01", date_to="2099-01-01")
        self.assertEqual(len(results), 1)
        self.assertEqual(search_items(self.provider.list_items(), experiment="E-999"), [])

    def test_invalid_root_handling(self):
        for root in (Path.home(), Path(self.root.anchor), self.base / "missing"):
            provider = LocalOneDriveProvider(root, self.base / "cache")
            with self.assertRaises(ValueError):
                provider.validate_root(require_marker=False, allow_unmarked=True)

    def test_unrelated_folder_requires_explicit_acceptance(self):
        root = self.base / "Other"
        root.mkdir()
        provider = LocalOneDriveProvider(root, self.base / "othercache")
        with self.assertRaises(ValueError):
            provider.accept_root("Other")
        provider.accept_root("Other", allow_unmarked=True)
        self.assertEqual(provider.status(), "Connected")

    def test_disconnected_root_does_not_destroy_index(self):
        self.file("03_Experiments/data.csv")
        self.provider.refresh()
        before = self.provider.index_path.read_bytes()
        moved = self.base / "Unavailable"
        self.root.rename(moved)
        with self.assertRaises(ValueError):
            self.provider.refresh()
        self.assertEqual(self.provider.index_path.read_bytes(), before)
        self.assertEqual(self.provider.status(), "Unavailable")

    def test_files_not_read_to_index_and_placeholder_attributes(self):
        self.file("03_Experiments/large.mp4")
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.suffix == ".mp4":
                raise AssertionError("Content read during indexing")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            self.provider.refresh()
        self.assertTrue(placeholder(SimpleNamespace(st_file_attributes=0x400000)))

    def test_cloud_only_metadata_not_read(self):
        metadata = self.file("03_Experiments/experiment.json", b'{"sample_id":"S-001"}')
        self.file("03_Experiments/video.mp4")
        original = Path.lstat
        def cloud_stat(path):
            info = original(path)
            if path == metadata:
                return SimpleNamespace(st_file_attributes=0x400000, st_mode=info.st_mode, st_size=info.st_size)
            return info
        with patch.object(Path, "lstat", cloud_stat):
            summary = self.provider.refresh()
        self.assertTrue(summary["warnings"])
        self.assertEqual(self.provider.get_item("03_Experiments/video.mp4")["sample_id"], "")

    def test_malformed_metadata_keeps_index_and_last_known_relationships(self):
        metadata = self.file("03_Experiments/experiment.json", b'{"sample_id":"S-001"}')
        self.file("03_Experiments/video.mp4")
        self.provider.refresh()
        metadata.write_text("{invalid")
        summary = self.provider.refresh()
        self.assertTrue(summary["warnings"])
        self.assertEqual(self.provider.get_item("03_Experiments/video.mp4")["sample_id"], "S-001")

    def test_malformed_cache_not_overwritten(self):
        self.provider.index_path.parent.mkdir(parents=True)
        self.provider.index_path.write_text("{invalid")
        provider = LocalOneDriveProvider(self.root, self.provider.cache_dir)
        with self.assertRaises(ValueError):
            provider.refresh(rebuild=True)
        self.assertEqual(provider.index_path.read_text(), "{invalid")

    def test_cancel_preserves_previous_index(self):
        self.file("03_Experiments/a.csv")
        self.provider.refresh()
        before = self.provider.index_path.read_bytes()
        with self.assertRaises(IndexCancelled):
            self.provider.refresh(rebuild=True, cancel=lambda: True)
        self.assertEqual(self.provider.index_path.read_bytes(), before)

    def test_rebuild_retains_ids(self):
        self.file("03_Experiments/a.csv")
        self.provider.refresh()
        before = self.provider.list_items()[0]["id"]
        self.provider.refresh(rebuild=True)
        self.assertEqual(self.provider.list_items()[0]["id"], before)
        self.assertEqual(self.provider.index["last_operation"], "rebuild")

    def test_other_project_cache_not_shown(self):
        self.file("03_Experiments/a.csv")
        self.provider.refresh()
        second = self.base / "SecondProject"
        second.mkdir()
        provider = LocalOneDriveProvider(second, self.provider.cache_dir)
        provider.accept_root("Second", allow_unmarked=True)
        self.assertEqual(provider.list_items(), [])

    def test_link_escape_not_indexed_or_opened(self):
        outside = self.base / "outside.csv"
        outside.write_text("outside")
        link = self.root / "03_Experiments/linked.csv"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Windows symlink privilege unavailable")
        self.provider.refresh()
        self.assertEqual(self.provider.list_items(), [])
        with self.assertRaises(ValueError):
            self.provider.open_item("03_Experiments/linked.csv")

    def test_permission_error_retains_records_as_unverified(self):
        self.file("03_Experiments/locked/a.csv")
        self.provider.refresh()
        original = os.scandir
        def guarded(path):
            if Path(path).name == "locked":
                raise PermissionError("locked")
            return original(path)
        with patch("app.services.project_storage.os.scandir", guarded):
            summary = self.provider.refresh()
        self.assertTrue(summary["warnings"])
        self.assertEqual(self.provider.list_items()[0]["state"], "active")
        self.assertTrue(self.provider.list_items()[0]["scan_unverified"])

    def test_shared_settings_history_and_stale_edit_detection(self):
        store = self.store()
        store.connect_storage(self.root)
        value = copy.deepcopy(store.project)
        value["goal"] = "Test durability"
        store.save_project(value)
        self.assertEqual(self.provider.read_project()["settings"]["goal"], "Test durability")
        self.assertEqual(len(store.history()), 1)
        marker = self.provider.read_project()
        marker["settings"]["goal"] = "Another user edit"
        write_json(self.root / ".projecthub/project.json", marker)
        with self.assertRaises(ValueError):
            store.save_project(value)

    def test_two_users_resolve_same_relative_reference(self):
        self.file("03_Experiments/a.csv")
        self.provider.refresh()
        other = self.base / "OtherUserRoot"
        import shutil
        shutil.copytree(self.root, other)
        provider = LocalOneDriveProvider(other, self.base / "othercache")
        provider.refresh()
        relative = self.provider.list_items()[0]["relative_path"]
        self.assertNotEqual(self.provider.path(relative), provider.path(relative))
        self.assertEqual(provider.list_items()[0]["relative_path"], relative)

    def test_junction_escape_not_indexed_or_opened(self):
        if os.name != "nt":
            self.skipTest("Windows junction test")
        import subprocess
        outside = self.base / "External Folder"
        outside.mkdir()
        (outside / "secret.csv").write_text("outside")
        junction = self.root / "03_Experiments/junction"
        command = f'mklink /J "{junction}" "{outside}"'
        result = subprocess.run([os.environ.get("COMSPEC", "cmd.exe"), "/C", command], capture_output=True, text=True)
        if result.returncode:
            self.skipTest("Junction creation unavailable: " + result.stderr)
        try:
            self.provider.refresh()
            self.assertEqual(self.provider.list_items(), [])
            with self.assertRaises(ValueError):
                self.provider.open_item("03_Experiments/junction/secret.csv")
        finally:
            # Remove only the junction itself, never its external target.
            junction.rmdir()

    def test_corrupt_record_cache_is_preserved_and_reported(self):
        write_json(self.provider.index_path, {"schema_version": 1, "records": [{"id": "broken"}]})
        provider = LocalOneDriveProvider(self.root, self.provider.cache_dir)
        self.assertTrue(provider.cache_error)
        with self.assertRaises(ValueError):
            provider.refresh()

    def test_legacy_absolute_paths_migrate_without_shared_leak(self):
        app_root = self.base / "LegacyApp"
        defaults = json.loads((ROOT / "config/project_defaults.json").read_text())
        legacy = copy.deepcopy(defaults)
        legacy["project_folder"] = "C:/Users/Legacy/Project"
        legacy["links"]["Reports"] = "C:/Users/Legacy/Reports"
        for name, value in (("project_defaults.json", defaults), ("project.json", legacy), ("software_manifest.json", [])):
            write_json(app_root / "config" / name, value)
        store = Store(app_root, self.base / "legacy_profile")
        store.save_project(store.project)
        persisted = read_json(store.local_dir / "local.json", {})
        self.assertEqual(persisted["local_project_folder"], legacy["project_folder"])
        self.assertEqual(persisted["local_resource_paths"]["Reports"], legacy["links"]["Reports"])
        self.assertNotIn("C:/Users", (app_root / "config/project.json").read_text())

    def test_atomic_write_rejects_non_json_number_preserving_old_file(self):
        path = self.base / "valid.json"
        write_json(path, {"value": 1})
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            write_json(path, {"value": float("nan")})
        self.assertEqual(path.read_bytes(), before)

    def test_name_surrogate_paths_rejected_without_skipping_cloud_reparse_files(self):
        redirected = self.root / "03_Experiments/redirected"
        redirected.mkdir()
        (redirected / "outside.csv").write_text("outside")
        from contextlib import contextmanager
        original_scan, original_lstat = os.scandir, Path.lstat
        class Entry:
            def __init__(self, entry):
                self.entry = entry
                self.name, self.path = entry.name, entry.path
            def stat(self, follow_symlinks=False):
                info = self.entry.stat(follow_symlinks=follow_symlinks)
                return SimpleNamespace(st_mode=info.st_mode, st_reparse_tag=0xA0000003) if self.name == "redirected" else info
        @contextmanager
        def scan(path):
            with original_scan(path) as entries:
                yield (Entry(entry) for entry in entries)
        def lstat(path):
            info = original_lstat(path)
            return SimpleNamespace(st_mode=info.st_mode, st_reparse_tag=0xA0000003) if path == redirected else info
        with patch("app.services.project_storage.os.scandir", scan), patch.object(Path, "lstat", lstat):
            self.provider.refresh()
            self.assertEqual(self.provider.list_items(), [])
            with self.assertRaises(ValueError):
                self.provider.path("03_Experiments/redirected/outside.csv")
        self.assertFalse(redirects(SimpleNamespace(st_mode=0o100644, st_reparse_tag=0x9000001A)))
        self.assertTrue(redirects(SimpleNamespace(st_mode=0o40755, st_reparse_tag=0xA0000003)))

    def test_invalid_index_header_does_not_block_hub_connection(self):
        write_json(self.provider.index_path, {"schema_version": 1, "records": []})
        provider = LocalOneDriveProvider(self.root, self.provider.cache_dir)
        self.assertEqual(provider.status(), "Index Error")
        self.assertEqual(provider.summary()["files"], 0)

    def test_open_code_uses_folder_workflow_instead_of_executing(self):
        self.file("06_Analysis/script.py", b"print('do not execute')")
        with patch("app.services.project_storage.os.startfile") as start:
            with self.assertRaises(ValueError):
                self.provider.open_item("06_Analysis/script.py")
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
