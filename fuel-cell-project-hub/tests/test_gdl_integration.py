"""GDL compatibility, path, session and package tests; never launch Fiji/JMP."""
import ast
import codecs
import copy
import json
import math
import os
import re
import runpy
import shutil
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.storage import ROOT, Store, write_json
from app.services.project_storage import LocalOneDriveProvider, validate_shared_settings
from app.services.path_registry import PathRegistry, detect_dependency
from app.services.gdl_analysis import GDLAnalysisService
from app.services.gdl_package import stage_zip, inspect_engine

BASELINE = ROOT / "analysis/gdl/baseline"
ENGINE = ROOT / "analysis/gdl/engine"
PACKAGE_FIXTURE = BASELINE if BASELINE.is_dir() else ROOT / "tests/fixtures/gdl_legacy_v209"


def functions(path, names, namespace=None):
    tree = ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(body) != len(names):
        raise AssertionError("Missing compatibility function")
    scope = dict(namespace or {})
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), scope)
    return scope


class GDLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        fixture = self.base / "app"
        (fixture / "config").mkdir(parents=True)
        for name in ("project_defaults.json", "software_manifest.json"):
            shutil.copyfile(ROOT / "config" / name, fixture / "config" / name)
        self.store = Store(fixture, self.base / "local")
        self.service = GDLAnalysisService(self.store)
        self.registry = self.service.registry
        self.fiji = self.base / "Fiji/fiji-windows-x64.exe"
        self.fiji.parent.mkdir()
        self.fiji.write_bytes(b"fixture")
        (self.fiji.parent / "jars").mkdir()
        (self.fiji.parent / "plugins").mkdir()
        self.jmp = self.base / "JMP/jmp.exe"
        self.jmp.parent.mkdir()
        self.jmp.write_bytes(b"fixture")
        self.input = self.base / "input"
        self.input.mkdir()
        self.output = self.base / "output"
        self.registry.save_paths({"fiji_executable": str(self.fiji), "jmp_executable": str(self.jmp),
                                  "default_input_folder": str(self.input), "default_output_folder": str(self.output)},
                                  input_mode="Configured folder", output_mode="Custom configured folder")

    def tearDown(self):
        self.temp.cleanup()

    def connect(self):
        root = self.base / "Project"
        root.mkdir()
        (root / "04_Raw_Data").mkdir()
        provider = LocalOneDriveProvider(root, self.store.local_dir / "index")
        provider.accept_root("Project", self.store.project)
        self.store.connect_storage(root)
        return root

    def archive(self, name="v209.zip", broken=False):
        destination = self.base / name
        with zipfile.ZipFile(destination, "w") as bundle:
            for path in PACKAGE_FIXTURE.rglob("*"):
                if path.is_file() and not (broken and path.name == "06B_Fiber_Fixer.py"):
                    bundle.write(path, "Package/" + path.relative_to(PACKAGE_FIXTURE).as_posix())
        return destination

    def test_valid_dependencies_and_engine(self):
        rows = self.service.validate_paths()
        for key in ("fiji_executable", "jmp_executable", "analysis_engine_root", "module_folder", "quick_run_folder", "swift_magnification_folder", "default_input_folder", "default_output_folder", "temp_work_folder"):
            self.assertEqual(rows[key]["status"], "Ready", key)

    def test_invalid_dependency_structure_and_names(self):
        (self.fiji.parent / "plugins").rmdir()
        self.assertNotEqual(self.registry.validate("fiji_executable", str(self.fiji))["status"], "Ready")
        self.assertNotEqual(self.registry.validate("jmp_executable", str(self.fiji))["status"], "Ready")

    def test_fiji_auto_detection_bounded_dynamic_home(self):
        self.store.local["paths"].pop("fiji")
        with patch("app.services.path_registry.Path.home", return_value=self.base), patch("app.services.path_registry.detect", return_value={"path": ""}):
            self.assertEqual(detect_dependency(self.store, "fiji_executable"), str(self.fiji))

    def test_jmp_auto_detection_multiple_editions(self):
        self.store.local["paths"].pop("jmp")
        fixture = self.base / "programs/JMP/JMPPRO/21/jmp.exe"
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(b"fixture")
        with patch.dict(os.environ, {"ProgramFiles": str(self.base / "programs")}), patch("app.services.path_registry.detect", return_value={"path": ""}):
            self.assertEqual(detect_dependency(self.store, "jmp_executable"), str(fixture))

    def test_explicit_invalid_path_never_silently_replaced(self):
        self.store.local["paths"]["fiji"] = str(self.base / "gone.exe")
        self.assertEqual(detect_dependency(self.store, "fiji_executable"), str(self.base / "gone.exe"))

    def test_missing_module_and_missing_swift(self):
        empty = self.base / "empty"
        empty.mkdir()
        self.assertNotEqual(self.registry.validate("module_folder", str(empty))["status"], "Ready")
        self.assertNotEqual(self.registry.validate("swift_magnification_folder", str(empty))["status"], "Ready")
        self.assertEqual(self.registry.validate("quick_run_folder", str(empty))["status"], "Ready")

    def test_writable_output_check(self):
        self.output.mkdir()
        with patch("app.services.path_registry.tempfile.NamedTemporaryFile", side_effect=PermissionError()):
            self.assertEqual(self.registry.validate("default_output_folder", str(self.output), writable=True)["status"], "Not writable")

    def test_shared_folder_is_relative_and_executables_stay_local(self):
        root = self.connect()
        output = root / "05_Processed_Data"
        self.registry.save_paths({"default_output_folder": str(output)}, shared=True)
        self.assertEqual(self.store.project["gdl_analysis"]["paths"]["default_output_folder"], "05_Processed_Data")
        self.assertEqual(self.registry.resolve("default_output_folder"), str(output))
        self.assertNotIn(str(self.fiji), json.dumps(self.store.project))
        self.assertTrue(self.store.history())

    def test_absolute_shared_paths_rejected(self):
        project = copy.deepcopy(self.store.project)
        project["gdl_analysis"] = {"paths": {"default_output_folder": "C:/Users/someone/output"}}
        with self.assertRaises(ValueError):
            validate_shared_settings(project)
        project["gdl_analysis"] = {"paths": {"fiji_executable": "Fiji/fiji.exe"}}
        with self.assertRaises(ValueError):
            validate_shared_settings(project)

    def test_local_settings_do_not_create_shared_revision(self):
        self.assertNotIn("gdl_analysis", self.store.project)
        self.assertEqual(self.store.history(), [])
        self.registry.save_paths({"fiji_executable": str(self.fiji)})
        self.assertEqual(self.store.history(), [])

    def test_corrupt_local_config_is_preserved_and_blocks_writes(self):
        self.registry.config_path.write_text("invalid JSON")
        service = GDLAnalysisService(self.store)
        self.assertTrue(service.registry.config_error)
        with self.assertRaises(ValueError):
            service.registry.save_paths({"default_output_folder": str(self.output)})
        self.assertEqual(self.registry.config_path.read_text(), "invalid JSON")

    def test_reset_returns_bundled_default(self):
        self.registry.save_paths({"quick_run_folder": str(self.input)})
        self.registry.save_paths({"quick_run_folder": ""})
        self.assertEqual(self.registry.resolve("quick_run_folder"), str(ENGINE / "Quick Runs"))

    def test_session_schema_and_local_runtime(self):
        session = self.service.build_session_config()
        self.assertEqual(session["schema_version"], 1)
        self.assertEqual(session["engine_version"], "209")
        self.assertTrue(Path(session["status_file"]).is_relative_to(self.store.local_dir))
        self.assertEqual(session["input_folder"], str(self.input))

    def launch(self):
        process = Mock(pid=4567)
        process.poll.return_value = None
        with patch("app.services.gdl_analysis.subprocess.Popen", return_value=process) as popen:
            session = self.service.launch_analysis()
        return session, process, popen

    def test_launch_env_command_and_no_shell(self):
        session, process, popen = self.launch()
        args, kwargs = popen.call_args
        self.assertTrue(args[0][1].endswith("GDL_Analysis_Launcher_v209.py"))
        self.assertEqual(read_json_local(kwargs["env"]["GDL_SESSION_CONFIG"])["session_id"], session["session_id"])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(self.service.read_status()["state"], "STARTING")

    def test_watchdog_states_and_stale_status(self):
        session, _, _ = self.launch()
        for state in ("RUNNING", "RESTARTING", "COMPLETED", "CANCELED", "FAILED"):
            write_json(Path(session["status_file"]), {"session_id": session["session_id"], "state": state, "message": "fixture"})
            self.assertEqual(self.service.read_status()["state"], state)
        write_json(Path(session["status_file"]), {"session_id": "stale", "state": "COMPLETED"})
        self.assertEqual(self.service.read_status()["state"], "FAILED")

    def test_status_output_cannot_escape_selected_parent(self):
        session, _, _ = self.launch()
        write_json(Path(session["status_file"]), {"session_id": session["session_id"], "state": "COMPLETED", "output_folder": str(self.input)})
        self.assertNotIn("actual_output", self.service.read_status())
        actual = self.output / "GDL_run"
        write_json(Path(session["status_file"]), {"session_id": session["session_id"], "state": "COMPLETED", "output_folder": str(actual)})
        self.assertEqual(self.service.read_status()["actual_output"], str(actual.resolve()))

    def test_completion_offers_only_existing_report(self):
        session, _, _ = self.launch()
        write_json(Path(session["status_file"]), {"session_id": session["session_id"], "state": "COMPLETED"})
        self.assertEqual(self.service.read_status()["reports"], [])
        report = self.output / "Word_Report/report.docx"
        report.parent.mkdir()
        report.write_bytes(b"fixture")
        self.assertEqual(self.service.read_status()["reports"], [str(report)])

    def test_process_exit_and_launch_failure(self):
        _, process, _ = self.launch()
        process.poll.return_value = 5
        self.assertEqual(self.service.read_status()["state"], "FAILED")
        with patch("app.services.gdl_analysis.subprocess.Popen", side_effect=OSError("fixture")):
            with self.assertRaises(ValueError):
                self.service.launch_analysis()
        self.assertEqual(read_json_local(self.service.last_path)["state"], "FAILED")

    def test_stop_uses_watchdog_request_without_killing_fiji(self):
        session, process, _ = self.launch()
        self.service.stop_analysis()
        self.assertTrue(Path(session["stop_file"]).is_file())
        process.terminate.assert_not_called()
        self.assertEqual(self.service.read_status()["state"], "MONITORING_STOPPED")

    def test_active_session_blocks_package_update_and_duplicate_launch(self):
        self.launch()
        with self.assertRaises(ValueError):
            self.service.launch_analysis()
        with self.assertRaises(ValueError):
            self.service.install_package(self.archive())

    def test_update_and_rollback_preserve_custom_quick_runs(self):
        self.registry.save_paths({"quick_run_folder": str(self.input)})
        original = self.registry.resolve("analysis_engine_root")
        manifest = self.service.install_package(self.archive())
        self.assertEqual(manifest["version"], "209")
        self.assertNotEqual(self.registry.resolve("analysis_engine_root"), original)
        self.assertEqual(self.registry.resolve("quick_run_folder"), str(self.input))
        self.assertIn("matches", self.service.check_package())
        self.service.rollback_package()
        self.assertEqual(self.registry.resolve("analysis_engine_root"), original)

    def test_invalid_update_preserves_engine_and_config(self):
        original = copy.deepcopy(self.registry.config)
        with self.assertRaises(ValueError):
            self.service.install_package(self.archive(broken=True))
        self.assertEqual(self.registry.config, original)

    def test_source_folder_check_finds_new_version_without_executing(self):
        self.service.install_package(self.archive())
        with zipfile.ZipFile(self.base / "unrelated.zip", "w") as bundle:
            bundle.writestr("other.txt", "not a GDL package")
        (self.base / "corrupt.zip").write_bytes(b"not a ZIP")
        archive = self.base / "new-package.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for path in PACKAGE_FIXTURE.rglob("*"):
                if path.is_file():
                    data = path.read_bytes()
                    if path.name == "GDL_User_Defaults.py":
                        data = data.replace(b'APPLICATION_VERSION = "v209"', b'APPLICATION_VERSION = "v210"')
                    bundle.writestr("Package/" + path.relative_to(PACKAGE_FIXTURE).as_posix(), data)
        self.assertIn("v210", self.service.check_package())
        self.assertEqual(self.service.available_update["path"], str(archive))
        self.assertEqual(self.registry.manifest()["version"], "209")

    def test_default_quick_runs_preserved_across_update(self):
        self.service.preserve_quick_runs()
        folder = Path(self.registry.resolve("quick_run_folder"))
        first = sorted(folder.glob("*.json"))[0]
        settings = read_json_local(first)
        settings["quick_run_name"] = "User custom slot"
        write_json(first, settings)
        self.service.install_package(self.archive())
        self.assertEqual(self.registry.resolve("quick_run_folder"), str(folder))
        self.assertEqual(read_json_local(first)["quick_run_name"], "User custom slot")

    def test_zip_traversal_rejected(self):
        archive = self.archive()
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.writestr("Package/../../outside.py", "malicious")
        destination = self.base / "stage"
        with self.assertRaises(ValueError):
            stage_zip(archive, destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.base / "outside.py").exists())

    def test_runtime_artifacts_excluded_and_templates_unchanged(self):
        archive = self.archive()
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.writestr("Package/Defaults and Other Stuff/Fiji Watchdog Log.txt", "old")
        destination = self.base / "stage"
        stage_zip(archive, destination)
        self.assertFalse((destination / "Defaults and Other Stuff/Fiji Watchdog Log.txt").exists())
        for path in (PACKAGE_FIXTURE / "Quick Runs").glob("*.json"):
            self.assertEqual(path.read_bytes(), (destination / "Quick Runs" / path.name).read_bytes())

    def test_legacy_ini_import_does_not_overwrite_valid_hub_paths(self):
        legacy = self.base / "legacy/Defaults and Other Stuff"
        legacy.mkdir(parents=True)
        (legacy / "startup_paths.ini").write_text("FIJI_LAUNCHER=" + str(self.fiji) + "\nJMP_EXECUTABLE=" + str(self.jmp))
        self.assertEqual(self.registry.legacy_candidates(legacy.parent), {})
        self.store.local["paths"].pop("fiji")
        self.assertEqual(self.registry.legacy_candidates(legacy.parent), {"fiji_executable": str(self.fiji)})


def read_json_local(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class LegacyCompatibilityTests(unittest.TestCase):
    @unittest.skipUnless(BASELINE.is_dir(), "Original private GDL baseline is not included in Git")
    def test_all_algorithm_functions_preserved(self):
        changed = {"quick_run_storage_dir", "apply_quick_run_settings_to_fields", "preferred_gdl_work_zone_directory", "find_jmp_exe",
                   "_swift_magn_candidate_paths", "summary_xls_destination_folders", "_summary_destinations_for_report", "_fiji_launcher_score", "_bounded_fiji_root_candidates", "show_settings_dialog", "populate_v193_scale_page", "populate_v209_report_recovery_page", "resolve_beast_parent_script_path", "write_beast_fiji_worker_wrapper"}
        for original in (BASELINE / "GDL_code").glob("*.py"):
            before = ast.parse(original.read_text())
            after = ast.parse((ENGINE / "GDL_code" / original.name).read_text())
            before_functions = {n.name: ast.dump(n) for n in before.body if isinstance(n, ast.FunctionDef)}
            after_functions = {n.name: ast.dump(n) for n in after.body if isinstance(n, ast.FunctionDef)}
            for name, value in before_functions.items():
                if name not in changed:
                    self.assertEqual(value, after_functions.get(name), original.name + ":" + name)

    def test_no_named_user_runtime_paths(self):
        for path in ENGINE.rglob("*.py"):
            self.assertNotRegex(path.read_text(), r"(?i)([a-z]:[/\\]Users[/\\](mkime|vgolf)|users\\\\(mkime|vgolf))", str(path))

    def test_existing_quick_runs_load_with_legacy_loader(self):
        namespace = {"os": os, "json": json, "codecs": codecs, "re": re,
                     "QUICK_RUN_FILE_PATTERN": re.compile(r"^quick run([1-5])-\((.*)\)\.json$", re.I), "IJ": Mock()}
        loader = functions(ENGINE / "GDL_code/01_Core_Imports_Helpers.py", {"load_quick_run_file"}, namespace)["load_quick_run_file"]
        for index, path in enumerate(sorted((ENGINE / "Quick Runs").glob("*.json")), 1):
            result = loader(str(path), index)
            self.assertEqual(result["error"], "")
            self.assertEqual(result["settings"], read_json_local(path)["quick_run_settings"])

    @unittest.skipUnless(BASELINE.is_dir(), "Original private GDL baseline is not included in Git")
    def test_swift_table_profiles_and_units_preserved(self):
        def parse(root):
            names = {"parse_swift_magnification_table", "swift_magn_pixels_per_meter_to_scale", "_swift_magn_log_once"}
            namespace = {"os": os, "struct": struct, "math": math, "re": re, "_SWIFT_MAGN_TABLE_CACHE": {}, "_SWIFT_MAGN_MESSAGE_CACHE": set(), "IJ": Mock()}
            scope = functions(root / "GDL_code/03_User_Interface_Settings.py", names, namespace)
            profiles = scope["parse_swift_magnification_table"](str(root / "Swift Magnification Tables/Imaging.magn"))
            return [{k: v for k, v in p.items() if k != "table_path"} for p in profiles], scope
        before, _ = parse(BASELINE)
        after, scope = parse(ENGINE)
        self.assertTrue(after)
        self.assertEqual(before, after)
        self.assertEqual(scope["swift_magn_pixels_per_meter_to_scale"](1_000_000), (0.001, 1.0))

    @unittest.skipUnless(BASELINE.is_dir(), "Original private GDL baseline is not included in Git")
    def test_watchdog_launch_arguments_preserved(self):
        launcher = "Defaults and Other Stuff/GDL_Analysis_Launcher_v209.py"
        names = {"_build_fiji_command", "_is_modern_fiji_launcher"}
        env = {"os": os, "RUN_SCRIPT_PATH": "fixture.py"}
        before = functions(BASELINE / launcher, names, env)
        after = functions(ENGINE / launcher, names, env)
        for executable in ("C:/Fiji/fiji-windows-x64.exe", "C:/Fiji/ImageJ-win64.exe"):
            self.assertEqual(before["_build_fiji_command"](executable), after["_build_fiji_command"](executable))

    def test_hub_watchdog_session_stop_and_crash_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = {"schema_version": 1, "session_id": "test-session", "fiji_executable": "fixture.exe", "status_file": str(root / "status.json"),
                       "stop_file": str(root / "stop.request"), "watchdog_log": str(root / "log.txt")}
            config = root / "session.json"
            write_json(config, session)
            with patch.dict(os.environ, {"GDL_SESSION_CONFIG": str(config)}):
                scope = runpy.run_path(str(ENGINE / "Defaults and Other Stuff/GDL_Analysis_Launcher_v209.py"), run_name="compatibility_test")
            globals_map = scope["_watchdog_main"].__globals__
            self.assertEqual(scope["_session_id"](1), scope["_session_id"](3))
            self.assertEqual(scope["_status_path_for_session"]("test-session"), session["status_file"])
            monitor = Mock(side_effect=["CRASH", "NORMAL"])
            with patch.dict(globals_map, {"_find_fiji_launcher": lambda: "fixture.exe", "_launch_and_monitor": monitor, "_log": Mock()}), patch("time.sleep"):
                self.assertEqual(scope["_watchdog_main"](), 0)
            self.assertEqual(read_json_local(session["status_file"])["state"], "RESTARTING")
            self.assertEqual(monitor.call_count, 2)
            Path(session["stop_file"]).write_text("stop")
            force_close = Mock()
            with patch.dict(globals_map, {"_force_close_existing_fiji": force_close}):
                self.assertEqual(scope["_launch_and_monitor"]("fixture.exe", 1), "NORMAL")
            force_close.assert_not_called()

    def test_standalone_local_overrides_and_ini_fallback(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"LOCALAPPDATA": temporary}):
            folder = Path(temporary) / "FuelCellProjectHub"
            write_json(folder / "local.json", {"paths": {"fiji": "C:/configured/Fiji/fiji.exe"}})
            write_json(folder / "gdl/config.json", {"paths": {"default_output_folder": "C:/configured/output"}})
            environment = dict(os.environ)
            environment.pop("GDL_SESSION_CONFIG", None)
            with patch.dict(os.environ, environment, clear=True):
                runtime = runpy.run_path(str(ROOT / "analysis/gdl/hub_runtime.py"))
            result = runtime["hub_legacy_overrides"]({"FIJI_LAUNCHER": "legacy.exe", "JMP_EXECUTABLE": "legacy-jmp.exe"})
            self.assertEqual(result["FIJI_LAUNCHER"], "C:/configured/Fiji/fiji.exe")
            self.assertEqual(result["JMP_EXECUTABLE"], "legacy-jmp.exe")

    def test_beast_workers_use_session_runner_and_transport(self):
        scope = functions(ENGINE / "GDL_code/08_Workbook_JMP_Launch_Helpers.py", {"resolve_beast_parent_script_path", "is_current_v193_launcher_path"}, {"os": os})
        runner = str(ENGINE / "RUN IN FIJI.py")
        with patch.dict(os.environ, {"GDL_SESSION_CONFIG": "fixture", "GDL_V193_LAUNCHER": runner}):
            self.assertEqual(scope["resolve_beast_parent_script_path"]({}, "C:/old/analysis"), runner)
        with tempfile.TemporaryDirectory() as temporary:
            wrapper = Path(temporary) / "worker.py"
            scope = functions(ENGINE / "GDL_code/09_BEAST_Workers_Main.py", {"write_beast_fiji_worker_wrapper"}, {"os": os})
            scope["write_beast_fiji_worker_wrapper"](str(wrapper), runner, "config.json", "startup.txt", "error.txt", "heartbeat.txt", 2.0, 1)
            source = wrapper.read_text()
            compile(source, str(wrapper), "exec")
            self.assertIn("hub_apply_session(globals())", source)
            self.assertNotIn("write_watchdog_status", source)


if __name__ == "__main__":
    unittest.main()
