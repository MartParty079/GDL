"""Canonical GDL paths; executables reuse the Hub software registry."""
import copy
import os
import shutil
import tempfile
from pathlib import Path

from app.services.storage import ROOT, read_json, write_json
from app.services.software import detect, registry_candidates, valid_executable
from app.services.project_storage import normalized_relative, redirects

FIELDS = {"fiji_executable": "Fiji", "jmp_executable": "JMP", "analysis_engine_root": "Analysis engine",
          "module_folder": "Module folder", "quick_run_folder": "Quick Run folder", "swift_magnification_folder": "Swift table folder",
          "default_input_folder": "Input folder", "default_output_folder": "Output folder", "report_output_folder": "Reports folder",
          "temp_work_folder": "Temporary work folder"}
SHAREABLE = {"quick_run_folder", "swift_magnification_folder", "default_input_folder", "default_output_folder", "report_output_folder"}
FIJI_NAMES = ("fiji-windows-x64.exe", "fiji-windows-arm64.exe", "fiji.exe", "ImageJ-win64.exe", "ImageJ-win32.exe", "ImageJ.exe")
DEFAULTS = {"paths": {}, "input_mode": "Choose at launch", "output_mode": "Project default", "extra_search_roots": [],
            "package_source": "", "installed_engine": "", "previous_engine": ""}


def validate_fiji(value):
    path = Path(value)
    return valid_executable(value) and path.name.lower() in {n.lower() for n in FIJI_NAMES} and any(
        (root / "jars").is_dir() and (root / "plugins").is_dir() for root in (path.parent, path.parent.parent, path.parent.parent.parent))


def detect_dependency(store, key, extra_roots=()):
    item_id = "fiji" if key == "fiji_executable" else "jmp"
    override = store.local["paths"].get(item_id)
    if override:
        return override  # Explicit paths are never silently replaced.
    item = next((i for i in store.manifest if i["id"] == item_id), None)
    if item:
        found = detect(item)
        if found["path"] and (item_id != "fiji" or validate_fiji(found["path"])):
            return found["path"]
    if item_id == "fiji":
        candidates = registry_candidates(FIJI_NAMES)
        candidates += [v for n in FIJI_NAMES if (v := shutil.which(n))]
        roots = [Path.home(), Path.home() / "Documents", Path.home() / "Desktop", Path.home() / "Downloads"]
        roots += [Path(v) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA") if (v := os.environ.get(k))]
        roots += [Path(v) for v in extra_roots]
        for root in roots:
            for pattern in ("Fiji*", "fiji-latest*/Fiji", "*/Fiji.app"):
                try:
                    for installation in list(root.glob(pattern))[:40]:
                        candidates += [str(installation / n) for n in FIJI_NAMES]
                except OSError:
                    continue
        return next((p for p in candidates if validate_fiji(p)), "")
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        base = Path(os.environ.get(env, "C:/Program Files"))
        for company in ("JMP", "SAS"):
            for pattern in ("*/jmp.exe", "*/*/jmp.exe", "*/*/*/jmp.exe"):
                for candidate in sorted((base / company).glob(pattern), reverse=True):
                    if valid_executable(candidate):
                        return str(candidate)
    return ""


class PathRegistry:
    def __init__(self, store):
        self.store = store
        self.config_path = store.local_dir / "gdl/config.json"
        self.config_error = ""
        try:
            self.config = read_json(self.config_path, DEFAULTS)
            if not isinstance(self.config, dict) or not isinstance(self.config.get("paths", {}), dict) or not isinstance(self.config.get("extra_search_roots", []), list):
                raise ValueError("GDL settings are invalid. Restore valid settings; the existing file was preserved.")
            if any(key not in FIELDS or not isinstance(value, str) for key, value in self.config.get("paths", {}).items()) or any(not isinstance(v, str) for v in self.config.get("extra_search_roots", [])):
                raise ValueError("GDL path values must be text.")
            if self.config.get("input_mode", DEFAULTS["input_mode"]) not in ("Choose at launch", "Project Files & Data", "Remember last folder", "Configured folder") or self.config.get("output_mode", DEFAULTS["output_mode"]) not in ("Project default", "Remember last folder", "Custom configured folder", "Ask when analysis starts"):
                raise ValueError("GDL location modes are invalid.")
            if any(not isinstance(self.config.get(k, ""), str) for k in ("installed_engine", "previous_engine", "package_source", "last_input", "last_output")):
                raise ValueError("GDL package locations must be text.")
        except (OSError, ValueError) as exc:
            self.config_error = str(exc)
            self.config = copy.deepcopy(DEFAULTS)
        for k, v in DEFAULTS.items():
            self.config.setdefault(k, copy.deepcopy(v))

    def manifest(self, engine=None):
        path = Path(engine or self.resolve("analysis_engine_root")) / "hub_manifest.json"
        try:
            value = read_json(path, {})
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def resolve(self, key, results=None):
        if key in ("fiji_executable", "jmp_executable"):
            item = "fiji" if key == "fiji_executable" else "jmp"
            return self.store.local["paths"].get(item) or (results or {}).get(item, {}).get("path", "")
        local = self.config["paths"].get(key)
        if local:
            return str(Path(local).expanduser())
        locations = self.store.local.get('project_locations', {})
        if locations.get('enabled'):
            research_defaults = {'default_input_folder': locations['active']['root_path'],
                'default_output_folder': locations['generated'],
                'report_output_folder': str(Path(locations['generated']) / 'reports'),
                'temp_work_folder': str(Path(locations['cache']) / 'gdl-work')}
            if key in research_defaults:
                return research_defaults[key]
        shared = self.store.project.get("gdl_analysis", {}).get("paths", {}).get(key)
        if shared:
            if not self.store.provider or self.store.provider.status() == "Unavailable":
                raise ValueError("Project storage is unavailable. Reconnect OneDrive or choose a local folder.")
            return str(self.store.provider.path(shared))
        engine = self.config.get("installed_engine") or str(ROOT / "analysis/gdl/engine")
        if key == "analysis_engine_root":
            return engine
        manifest = self.manifest(engine)
        defaults = {"module_folder": str(Path(engine) / manifest.get("module_folder", "GDL_code")),
                    "quick_run_folder": str(self.store.local_dir / "gdl/quick_runs") if (self.store.local_dir / "gdl/quick_runs").is_dir() else str(Path(engine) / manifest.get("quick_run_folder", "Quick Runs")),
                    "swift_magnification_folder": str(Path(engine) / manifest.get("swift_folder", "Swift Magnification Tables")),
                    "temp_work_folder": str(self.store.local_dir / "gdl/runtime/work")}
        if key in ("default_input_folder", "default_output_folder", "report_output_folder") and self.store.provider:
            from app.services.storage_settings import FOLDERS
            name = {'default_input_folder': 'Raw Data', 'default_output_folder': 'Processed Data', 'report_output_folder': 'Reports'}[key]
            folder = self.store.project.get('project_folders', {}).get(name, FOLDERS[name])
            return str(self.store.provider.path(folder))
        return defaults.get(key, "")

    def validate(self, key, value, writable=False):
        if not value:
            return {"status": "Needs setup", "message": FIELDS[key] + " is not configured."}
        path = Path(value)
        try:
            if not path.is_absolute():
                raise ValueError("Choose an absolute local path or a folder inside project storage.")
            if key == "fiji_executable":
                if not validate_fiji(value):
                    raise ValueError("Choose a Fiji executable with nearby jars and plugins folders.")
            elif key == "jmp_executable":
                if not valid_executable(value) or path.name.lower() != "jmp.exe":
                    raise ValueError("Choose an existing JMP jmp.exe executable.")
            elif key == "analysis_engine_root":
                manifest = self.manifest(value)
                if manifest.get("adapter_version") != 1 or not (path / manifest.get("entrypoint", "RUN IN FIJI.py")).is_file() or not (path / manifest.get("launcher", "missing")).is_file() or not (path / "Defaults and Other Stuff/hub_runtime.py").is_file():
                    raise ValueError("Choose a Hub-integrated engine or import its ZIP under Analysis. A loose legacy engine needs integration first.")
            elif key == "module_folder":
                modules = self.manifest().get("modules", [])
                missing = [n for n in modules if not (path / n).is_file()]
                if not modules or missing:
                    raise ValueError("Required GDL modules are missing: " + ", ".join(missing))
            elif key == "swift_magnification_folder":
                if not path.is_dir() or not any(path.glob("*.magn")):
                    raise ValueError("Choose a folder containing a Swift .magn table.")
            elif key in ("default_output_folder", "report_output_folder", "temp_work_folder") and not path.exists():
                parent = path
                while not parent.exists():
                    parent = parent.parent
                if not parent.is_dir() or not os.access(parent, os.W_OK):
                    raise PermissionError("The folder cannot be created here.")
                return {"status": "Ready", "message": "Will be created when analysis starts."}
            elif not path.is_dir():
                raise ValueError("Choose an existing folder.")
            if key not in ("fiji_executable", "jmp_executable"):
                if redirects(path.lstat()):
                    raise ValueError("Choose a direct folder rather than a filesystem link.")
            if writable:
                with tempfile.NamedTemporaryFile(dir=path, prefix=".gdl-write-check-", delete=True):
                    pass
            return {"status": "Ready", "message": "Ready"}
        except PermissionError:
            return {"status": "Not writable", "message": "Access denied. Check this folder's permissions."}
        except (OSError, ValueError) as exc:
            return {"status": "Missing" if not path.exists() else "Invalid", "message": str(exc)}

    def all_paths(self, results=None):
        return {key: self.resolve(key, results) for key in FIELDS}

    def save_config(self):
        if self.config_error:
            raise ValueError("GDL configuration could not be read. Restore valid local settings before saving; the existing file was preserved.")
        write_json(self.config_path, self.config)

    def save_paths(self, values, shared=False, input_mode=None, output_mode=None, extra_roots=None):
        if self.config_error:
            raise ValueError("GDL configuration could not be read. Restore valid local settings before saving; the existing file was preserved.")
        config = copy.deepcopy(self.config)
        project = copy.deepcopy(self.store.project)
        paths = copy.deepcopy(project.get("gdl_analysis", {}).get("paths", {}))
        original_shared = copy.deepcopy(paths)
        software = copy.deepcopy(self.store.local["paths"])
        for key, raw in values.items():
            value = raw.strip()
            if value:
                validation = self.validate(key, value)
                if validation["status"] != "Ready":
                    raise ValueError(FIELDS[key] + ": " + validation["message"])
            if key in ("fiji_executable", "jmp_executable"):
                item = "fiji" if key == "fiji_executable" else "jmp"
                if value:
                    software[item] = value
                else:
                    software.pop(item, None)
                continue
            relative = None
            if shared and value and key in SHAREABLE and self.store.provider:
                try:
                    relative = Path(value).resolve().relative_to(self.store.provider.root.resolve()).as_posix()
                    normalized_relative(relative)
                except ValueError:
                    pass
            if relative is not None:
                paths[key] = relative
                config["paths"].pop(key, None)
            elif value:
                config["paths"][key] = value
            else:
                config["paths"].pop(key, None)
                paths.pop(key, None)
        if input_mode:
            config["input_mode"] = input_mode
        if output_mode:
            config["output_mode"] = output_mode
        if extra_roots is not None:
            if any(not Path(p).is_absolute() or not Path(p).is_dir() for p in extra_roots):
                raise ValueError("Extra search roots must be existing absolute folders.")
            config["extra_search_roots"] = list(extra_roots)
        if paths != original_shared:
            project["gdl_analysis"] = {"paths": paths}
        if project != self.store.project:
            self.store.save_project(project, "Shared GDL folder settings changed")
        write_json(self.config_path, config)
        self.config = config
        self.store.local["paths"] = software
        self.store.save_local()
        self.store.record("Analysis", "GDL path settings updated")

    def legacy_ini(self, engine):
        ini = Path(engine) / "Defaults and Other Stuff/startup_paths.ini"
        pairs = {}
        if ini.is_file():
            for line in ini.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    pairs[k.strip()] = v.strip()
        return pairs

    def legacy_roots(self, engine):
        if self.config["extra_search_roots"]:
            return []
        return [p.strip() for p in self.legacy_ini(engine).get("EXTRA_USER_ROOTS", "").split(";") if p.strip() and Path(p.strip()).is_absolute() and Path(p.strip()).is_dir()]

    def legacy_candidates(self, engine):
        pairs = self.legacy_ini(engine)
        mapping = {"FIJI_LAUNCHER": "fiji_executable", "JMP_EXECUTABLE": "jmp_executable", "MODULE_FOLDER": "module_folder", "DEFAULT_OUTPUT_FOLDER": "default_output_folder"}
        candidates = {}
        for old, key in mapping.items():
            value = pairs.get(old, "")
            configured = self.store.local["paths"].get("fiji" if key == "fiji_executable" else "jmp") if key.endswith("executable") else self.config["paths"].get(key)
            configured = configured or self.store.project.get("gdl_analysis", {}).get("paths", {}).get(key)
            if value and not configured and self.validate(key, value)["status"] == "Ready":
                candidates[key] = value
        return candidates
