"""Hub-side session, watchdog and package lifecycle; no analysis algorithms."""
import hashlib
import os
import subprocess
import sys
import shutil
import uuid
import zipfile
from pathlib import Path

from app.services.storage import read_json, write_json, timestamp
from app.services.path_registry import PathRegistry, FIELDS
from app.services.gdl_package import stage_zip, zip_version, archive_digest

STATES = {"STARTING": "Starting Fiji…", "RUNNING": "Running analysis…", "COMPLETED": "Completed",
          "CANCELED": "Canceled", "FAILED": "Analysis failed", "RESTARTING": "Restarting Fiji…",
          "LAUNCH_FAILED": "Analysis failed", "MONITORING_STOPPED": "Monitoring stopped"}
TERMINAL = {"COMPLETED", "CANCELED", "FAILED", "LAUNCH_FAILED", "MONITORING_STOPPED"}


class GDLAnalysisService:
    def __init__(self, store):
        self.store = store
        self.registry = PathRegistry(store)
        install_id = store.local.setdefault('install_id', str(uuid.uuid4()))
        self.directory = store.project_data('analysis/gdl/' + install_id) if store.shared_index else store.local_dir / "gdl"
        self.last_path = self.directory / "last_session.json"
        try:
            self.session = read_json(self.last_path, {})
            if not isinstance(self.session, dict):
                raise ValueError("GDL session metadata must be an object.")
        except (OSError, ValueError) as exc:
            self.session = {"state": "FAILED", "message": "Previous session metadata could not be read. View local logs before starting a new session.", "details": str(exc)}
        self.process = None
        self.available_update = None

    def preserve_quick_runs(self):
        paths = self.registry.config["paths"]
        shared = self.store.project.get("gdl_analysis", {}).get("paths", {})
        destination = self.directory / "quick_runs"
        if "quick_run_folder" not in paths and "quick_run_folder" not in shared and not destination.exists():
            source = Path(self.registry.resolve("quick_run_folder"))
            destination.mkdir(parents=True)
            for file in source.glob("quick run*.json"):
                shutil.copyfile(file, destination / file.name)

    def active(self):
        if self.process is not None:
            return self.process.poll() is None
        # Read-only Windows liveness check allows app restart without duplicate launches.
        if not self.session.get("pid") or self.session.get("state") == "MONITORING_STOPPED":
            return False
        if os.name != "nt":
            return False
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        handle = kernel.OpenProcess(0x1000, False, int(self.session["pid"]))
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle(handle)

    def validate_paths(self, results=None):
        rows = {}
        for key in FIELDS:
            try:
                value = self.registry.resolve(key, results)
                rows[key] = {"path": value, **self.registry.validate(key, value)}
            except (OSError, ValueError) as exc:
                rows[key] = {"path": "", "status": "Needs setup", "message": str(exc)}
        return rows

    def build_session_config(self, results=None, input_folder=None, output_folder=None):
        if self.registry.config_error:
            raise ValueError("GDL configuration could not be read. Restore valid local settings before launching.")
        paths = self.registry.all_paths(results)
        config = self.registry.config
        mode = config["input_mode"]
        if input_folder is None:
            input_folder = config.get("last_input", "") if mode == "Remember last folder" else paths["default_input_folder"] if mode in ("Configured folder", "Project Files & Data") else ""
        if mode != "Choose at launch" and not input_folder:
            raise ValueError("Choose or configure an input folder before launching GDL analysis.")
        mode = config["output_mode"]
        if output_folder is None:
            output_folder = config.get("last_output", "") if mode == "Remember last folder" else paths["default_output_folder"] if mode in ("Project default", "Custom configured folder") else ""
        if not output_folder:
            raise ValueError("Choose an output folder before launching GDL analysis.")
        paths["default_output_folder"] = str(output_folder)
        paths["default_input_folder"] = str(input_folder or "")
        for key in FIELDS:
            if key == "default_input_folder" and not input_folder:
                continue  # Existing Fiji chooser remains available for full UI.
            if key == "report_output_folder" and not paths[key]:
                paths[key] = str(output_folder)
            result = self.registry.validate(key, paths[key])
            if result["status"] != "Ready":
                raise ValueError(FIELDS[key] + ": " + result["message"])
        session_id = "GDL-" + uuid.uuid4().hex
        runtime = self.directory / "runtime" / session_id
        logs = self.directory / "logs"
        return {"schema_version": 1, "session_id": session_id, "engine_version": self.registry.manifest()["version"],
                "started": timestamp(), "state": "STARTING", "launched_by_project_hub": True,
                "fiji_executable": paths["fiji_executable"], "jmp_executable": paths["jmp_executable"],
                "analysis_engine_root": paths["analysis_engine_root"], "module_folder": paths["module_folder"],
                "quick_run_folder": paths["quick_run_folder"], "swift_magnification_folder": paths["swift_magnification_folder"],
                "input_folder": paths["default_input_folder"], "output_folder": paths["default_output_folder"],
                "report_output_folder": paths["report_output_folder"], "temp_work_folder": paths["temp_work_folder"],
                "project_root": str(self.store.provider.root) if self.store.provider else "",
                "extra_search_roots": list(config["extra_search_roots"]), "quick_run": "",
                "status_file": str(runtime / "watchdog_status.json"), "stop_file": str(runtime / "stop.request"),
                "watchdog_log": str(logs / (session_id + "-watchdog.txt")), "launcher_log": str(logs / (session_id + "-launcher.txt"))}

    def launch_analysis(self, results=None, input_folder=None, output_folder=None):
        if self.active():
            raise ValueError("A GDL watchdog is already active. Finish that session before starting another.")
        self.preserve_quick_runs()
        session = self.build_session_config(results, input_folder, output_folder)
        if self.store.shared_index:
            base = self.store.shared_index.root
            if any(not Path(session[key]).resolve().is_relative_to(base) for key in ('input_folder','output_folder','report_output_folder')):
                raise ValueError('Research input and generated results must remain inside the configured shared project.')
            if not Path(session['temp_work_folder']).resolve().is_relative_to(base) and not Path(session['temp_work_folder']).resolve().is_relative_to(self.store.local_dir / 'cache'):
                raise ValueError('Use shared storage or disposable local cache for temporary analysis work.')
        elif self.store.sandbox_required:
            base=self.store.local_dir.resolve()
            if any(not Path(session[key]).resolve().is_relative_to(base) for key in ('input_folder','output_folder','report_output_folder','temp_work_folder')):
                raise ValueError('Beta analysis input and output must remain inside its isolated research sandbox.')
        for key in ("output_folder", "report_output_folder", "temp_work_folder"):
            Path(session[key]).mkdir(parents=True, exist_ok=True)
            field = {"output_folder": "default_output_folder", "report_output_folder": "report_output_folder", "temp_work_folder": "temp_work_folder"}[key]
            check = self.registry.validate(field, session[key], writable=True)
            if check["status"] != "Ready":
                raise ValueError(FIELDS[field] + ": " + check["message"])
        Path(session["status_file"]).parent.mkdir(parents=True, exist_ok=True)
        Path(session["launcher_log"]).parent.mkdir(parents=True, exist_ok=True)
        path = self.directory / "sessions" / (session["session_id"] + ".json")
        write_json(path, session)
        environment = os.environ.copy()
        environment["GDL_SESSION_CONFIG"] = str(path)
        executable = Path(sys.executable)
        if executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        manifest = self.registry.manifest(session["analysis_engine_root"])
        command = [str(executable), str(Path(session["analysis_engine_root"]) / manifest["launcher"])]
        self.session = session
        try:
            with open(session["launcher_log"], "ab") as log:
                self.process = subprocess.Popen(command, cwd=session["analysis_engine_root"], env=environment,
                    stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            session["pid"] = self.process.pid
            self.registry.config.update(last_input=session["input_folder"], last_output=session["output_folder"])
            self.registry.save_config()
            self.store.record("Analysis", "GDL v" + session["engine_version"] + " session started")
        except OSError as exc:
            session.update(state="FAILED", message="The GDL watchdog could not start. Review the log and configured engine.", details=str(exc))
            write_json(self.last_path, session)
            raise ValueError(session["message"]) from exc
        write_json(self.last_path, session)
        return session

    def read_status(self):
        if not self.session:
            return {"state": "IDLE", "message": "No analysis session yet."}
        result = dict(self.session)
        try:
            status = read_json(Path(self.session["status_file"]), {})
            if status.get("session_id") == self.session["session_id"] and status.get("state") in STATES:
                result.update(state=status["state"], message=status.get("message", ""))
                if status["state"] in ("FAILED", "LAUNCH_FAILED"):
                    result["details"] = status.get("message", "")
                    result["message"] = "The analysis engine reported a failure. View the session log, check the configured paths, then retry."
                output = status.get("output_folder")
                if output:
                    # Accept only outputs within the selected parent, never arbitrary status paths.
                    selected = Path(self.session["output_folder"]).resolve()
                    actual = Path(output).resolve()
                    if actual.is_relative_to(selected):
                        result["actual_output"] = str(actual)
        except (OSError, ValueError, TypeError):
            result["message"] = "Waiting for a readable watchdog status. View the log if this persists."
        if self.session.get("state") == "MONITORING_STOPPED":
            result["state"] = "MONITORING_STOPPED"
            result["message"] = "Watchdog relaunching is disabled. Cancel any ongoing work inside Fiji; Fiji stays open."
        elif not self.active() and result["state"] not in TERMINAL:
            result.update(state="FAILED", message="The watchdog exited before analysis completed. Review the log, then retry.")
        if result["state"] == "COMPLETED":
            output = Path(result.get("actual_output") or result["output_folder"])
            reports = []
            for pattern in ("Word_Report/*.docx", "Word_Report/*/*.docx"):
                for report in list(output.glob(pattern))[:100]:
                    if report.resolve().is_relative_to(output.resolve()):
                        reports.append(str(report))
            result["reports"] = reports
        if any(self.session.get(k) != result.get(k) for k in ("state", "message", "actual_output", "details", "reports")):
            self.session = result
            write_json(self.last_path, result)
        return result

    def stop_analysis(self):
        """Disable watchdog restarts; never blindly kill Fiji or its workers."""
        if self.active():
            Path(self.session["stop_file"]).write_text("Stop watchdog relaunching; cancel processing in Fiji.\n", encoding="utf-8")
            self.session["state"] = "MONITORING_STOPPED"
            write_json(self.last_path, self.session)

    def resolve_output(self):
        return self.session.get("actual_output") or self.session.get("output_folder") or self.registry.resolve("default_output_folder")

    def open_logs(self):
        folder = self.directory / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def install_package(self, archive):
        if self.registry.config_error:
            raise ValueError("Restore valid local GDL settings before installing an engine update.")
        if self.active():
            raise ValueError("Finish the active watchdog session before updating the engine.")
        old_engine = self.registry.resolve("analysis_engine_root")
        destination = self.directory / "packages" / uuid.uuid4().hex
        manifest = stage_zip(archive, destination)
        self.preserve_quick_runs()
        previous = dict(self.registry.config)
        try:
            config = dict(previous)
            config["paths"] = dict(config["paths"])
            config["paths"].pop("analysis_engine_root", None)
            config.update(installed_engine=str(destination), previous_engine=old_engine, package_source=str(Path(archive).resolve()),
                          source_sha256=manifest["source_sha256"])
            write_json(self.registry.config_path, config)
            self.registry.config = config
        except Exception:
            self.registry.config = previous
            raise
        self.store.record("Analysis", "GDL engine updated to v" + manifest["version"])
        return manifest

    def rollback_package(self):
        if self.active():
            raise ValueError("Finish the active watchdog session before rolling back.")
        previous = self.registry.config.get("previous_engine")
        if not previous or self.registry.validate("analysis_engine_root", previous)["status"] != "Ready":
            raise ValueError("No valid previous engine is available.")
        current = self.registry.resolve("analysis_engine_root")
        self.registry.config["paths"].pop("analysis_engine_root", None)
        self.registry.config.update(installed_engine=previous, previous_engine=current)
        self.registry.save_config()
        self.store.record("Analysis", "GDL engine rollback applied")

    def check_package(self):
        self.available_update = None
        source = self.registry.config.get("package_source")
        if not source:
            return "Choose an update ZIP to register a package source."
        path = Path(source)
        if not path.is_file():
            if not path.parent.is_dir():
                return "The saved package source is unavailable. Browse to the latest ZIP."
        current = int(self.registry.manifest().get("version", 0))
        candidates = []
        for candidate in list(path.parent.glob("*.zip"))[:80]:
            try:
                version = zip_version(candidate)
                if version > current:
                    candidates.append((version, candidate))
            except (OSError, ValueError, SyntaxError, zipfile.BadZipFile):
                continue
        if candidates:
            version, candidate = max(candidates, key=lambda pair: pair[0])
            self.available_update = {"version": str(version), "path": str(candidate)}
            return "GDL v" + str(version) + " is available in the saved source folder. Install it here after reviewing the package."
        if not path.is_file():
            return "No newer GDL ZIP found. The original ZIP is unavailable; browse to another package if needed."
        digest = archive_digest(path)
        return "The saved ZIP changed. Import it to review and activate the update." if digest != self.registry.config.get("source_sha256") else "The installed engine matches the saved ZIP."
