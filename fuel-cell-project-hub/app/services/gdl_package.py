"""Validate, stage and adapt legacy GDL ZIPs without executing supplied code."""
import ast
import hashlib
import json
import re
import shutil
import stat
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from app.services.storage import ROOT, read_json, write_json

MANIFEST = ROOT / "analysis/gdl/manifest.json"
SUPPORT = "Defaults and Other Stuff"


def archive_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zip_version(archive):
    with zipfile.ZipFile(archive) as bundle:
        defaults = [i for i in bundle.infolist() if i.filename.endswith("/GDL_User_Defaults.py") or i.filename == "GDL_User_Defaults.py"]
        if len(defaults) != 1 or defaults[0].file_size > 1_000_000:
            raise ValueError("GDL version metadata is missing or unsupported.")
        tree = ast.parse(bundle.read(defaults[0]).decode("utf-8-sig"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "APPLICATION_VERSION" for t in node.targets):
                version = str(ast.literal_eval(node.value)).lstrip("v")
                if version.isdigit():
                    return int(version)
    raise ValueError("No supported GDL version was found.")


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("This GDL package changed an integration boundary. The current engine was preserved; a compatibility review is needed.")
    return source.replace(old, new, 1)


def replace_pattern(source, pattern, replacement):
    source, count = re.subn(pattern, replacement, source, flags=re.M | re.S)
    if count != 1:
        raise ValueError("This GDL package has an unsupported configuration layout. The current engine was preserved.")
    return source


def inspect_engine(root):
    root = Path(root)
    defaults = root / SUPPORT / "GDL_User_Defaults.py"
    if not defaults.is_file() or not (root / "RUN IN FIJI.py").is_file():
        raise ValueError("The GDL engine is incomplete: runner or defaults missing.")
    tree = ast.parse(defaults.read_text(encoding="utf-8-sig"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("APPLICATION_VERSION", "CODE_MODULE_FILES"):
                    values[target.id] = ast.literal_eval(node.value)
    version = str(values.get("APPLICATION_VERSION", "")).lstrip("v")
    modules = values.get("CODE_MODULE_FILES", [])
    if not version.isdigit() or not isinstance(modules, list) or len(modules) != 11 or any(not isinstance(n, str) or Path(n).name != n or not n.endswith(".py") for n in modules):
        raise ValueError("The GDL version/module manifest is unsupported.")
    launchers = list((root / SUPPORT).glob("GDL_Analysis_Launcher_v*.py"))
    if len(launchers) != 1:
        raise ValueError("The package must contain one GDL watchdog launcher.")
    for name in modules:
        if not (root / "GDL_code" / name).is_file():
            raise ValueError("Required GDL module missing: " + name)
    quick = list((root / "Quick Runs").glob("quick run*.json"))
    slots = set()
    for item in quick:
        data = json.loads(item.read_text(encoding="utf-8-sig"))
        if not isinstance(data.get("quick_run_settings"), dict):
            raise ValueError("A bundled Quick Run is invalid.")
        slots.add(int(data.get("quick_run_slot", 0)))
    if slots != {1, 2, 3, 4, 5} or not (root / "Swift Magnification Tables/Imaging.magn").is_file():
        raise ValueError("The package must retain all five Quick Runs and the Swift table.")
    return {"id": "gdl_analysis", "name": "YOURE A BETA GDL Analysis", "version": version,
            "entrypoint": "RUN IN FIJI.py", "launcher": launchers[0].relative_to(root).as_posix(),
            "module_folder": "GDL_code", "quick_run_folder": "Quick Runs", "swift_folder": "Swift Magnification Tables",
            "modules": modules, "requires": ["fiji", "jmp"], "adapter_version": 1}


def adapt_engine(root):
    """Anchor-checked edits; never import/execute the scientific modules."""
    root = Path(root)
    manifest = inspect_engine(root)
    def edit(relative, action):
        path = root / relative
        path.write_text(action(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
    def defaults(source):
        source = replace_pattern(source, r'^DEFAULT_FIJI_LAUNCHERS = \[.*?^DEFAULT_EXTRA_USER_ROOTS = [^\n]*',
            'DEFAULT_FIJI_LAUNCHERS = []\nDEFAULT_EXTRA_USER_ROOTS = ""')
        source = replace_pattern(source, r'^JMP_EXE_DEFAULT = [^\n]*\nALL_REPORTS_FOLDER_MICHELSON = [^\n]*\nALL_REPORTS_FOLDER_VGOLF = [^\n]*',
            'JMP_EXE_DEFAULT = ""\nALL_REPORTS_FOLDER_MICHELSON = ""\nALL_REPORTS_FOLDER_VGOLF = ""')
        return source.replace('"All available All Reports folders"', '"All configured report destinations"')
    edit(SUPPORT + "/GDL_User_Defaults.py", defaults)
    def core(source):
        source = replace_pattern(source, r'(def preferred_gdl_work_zone_directory\(\):\n)    candidates = \[.*?\n    \]',
            '\\1    candidates = [os.environ.get("GDL_INPUT_FOLDER", ""), os.path.expanduser("~")]')
        source = replace_once(source, 'folder = os.path.join(quick_run_app_dir(), QUICK_RUN_FOLDER_NAME)',
            'folder = os.environ.get("GDL_QUICK_RUN_FOLDER", "").strip() or os.path.join(quick_run_app_dir(), QUICK_RUN_FOLDER_NAME)')
        source = replace_once(source, 'def find_jmp_exe(settings):\n',
            'def find_jmp_exe(settings):\n    hub_jmp = os.environ.get("GDL_JMP_EXE_OVERRIDE", "").strip()\n    if hub_jmp and File(hub_jmp).exists():\n        return hub_jmp\n')
        source = replace_once(source, 'def apply_quick_run_settings_to_fields(fields, saved_settings, processing_panel):\n',
            'def apply_quick_run_settings_to_fields(fields, saved_settings, processing_panel):\n    saved_settings = dict(saved_settings)\n    old_destination = saved_settings.get("summary_xls_destination", "")\n    saved_settings["summary_xls_destination"] = {"Michelson/Andrew All Reports folder": "Project Reports folder", "vgolf/OneDrive All Reports folder": "Project Reports folder", "All available All Reports folders": "All configured report destinations", "Auto-detect available All Reports folder": "Project Reports folder", "Word_Report output folder": "Run output folder"}.get(old_destination, old_destination)\n')
        return source
    edit("GDL_code/01_Core_Imports_Helpers.py", core)
    def workbook(source):
        source = replace_once(source, 'def resolve_beast_parent_script_path(settings=None, output_root=None):\n',
            'def resolve_beast_parent_script_path(settings=None, output_root=None):\n    if os.environ.get("GDL_SESSION_CONFIG", ""):\n        hub_parent = os.environ.get("GDL_V193_LAUNCHER", "")\n        if not is_current_v193_launcher_path(hub_parent):\n            raise RuntimeError("The Hub analysis runner is unavailable; restart from Project Hub.")\n        if settings is not None:\n            settings["_beast_parent_script_path"] = hub_parent\n        return hub_parent\n')
        source = replace_pattern(source, r'        if "\\\\users\\\\mkime.*?        if "downloads" in root:', '        if "downloads" in root:')
        source = replace_pattern(source, r'    # Explicit operator roots requested for both workstations\.\n    for root in \[.*?\n    \]:',
            '    # Explicit local roots supplied by Project Hub.\n    for root in os.environ.get("GDL_EXTRA_USER_ROOTS", "").split(";"):')
        source = replace_once(source, '    elif choice == "vgolf/OneDrive All Reports folder":\n        folders = [ALL_REPORTS_FOLDER_VGOLF]\n', '')
        source = source.replace('if File(candidate).exists():', 'if candidate and File(candidate).exists():')
        source = replace_once(source, 'folders = [ALL_REPORTS_FOLDER_MICHELSON]', 'folders = [ALL_REPORTS_FOLDER_MICHELSON] if ALL_REPORTS_FOLDER_MICHELSON else [fallback]')
        return source
    edit("GDL_code/08_Workbook_JMP_Launch_Helpers.py", workbook)
    # Generic display names with legacy JSON mapped in memory, never rewriting templates.
    names = {"Michelson/Andrew All Reports folder": "Project Reports folder", "vgolf/OneDrive All Reports folder": "Project Reports folder",
             "All available All Reports folders": "All configured report destinations", "Auto-detect available All Reports folder": "Project Reports folder",
             "Word_Report output folder": "Run output folder"}
    for relative in ("GDL_code/02_User_Interface_Pages.py", "GDL_code/03_User_Interface_Settings.py", "GDL_code/08_Workbook_JMP_Launch_Helpers.py"):
        def generic(source):
            for old, new in names.items():
                source = source.replace(old, new)
            source = source.replace('"Project Reports folder",\n            "Project Reports folder",\n            "Project Reports folder",', '"Project Reports folder",')
            return source
        edit(relative, generic)
    edit("GDL_code/02_User_Interface_Pages.py", lambda s: replace_once(s,
        'quick_run_app_dir(),\n            "Swift Magnification Tables",',
        'os.environ.get("GDL_SWIFT_FOLDER", "").strip() or os.path.join(quick_run_app_dir(), "Swift Magnification Tables"),'))
    edit("GDL_code/03_User_Interface_Settings.py", lambda s: replace_once(s,
        'add_candidate(os.path.join(app_dir, "Swift Magnification Tables", filename))',
        'add_candidate(os.path.join(os.environ.get("GDL_SWIFT_FOLDER", "").strip() or os.path.join(app_dir, "Swift Magnification Tables"), filename))'))
    def runner(source):
        source = replace_once(source, 'import traceback\n', 'import traceback\n\nexecfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Defaults and Other Stuff", "hub_runtime.py"), globals(), globals())\n')
        source = replace_once(source, 'cfg = startup_dialog(read_config(), str(shared.get("DEFAULT_EXTRA_USER_ROOTS", "")))',
            'cfg = hub_startup_config(read_config()) if HUB_SESSION else startup_dialog(hub_legacy_overrides(read_config()), str(shared.get("DEFAULT_EXTRA_USER_ROOTS", "")))')
        source = replace_once(source, '    apply_overrides(cfg, shared)\n', '    apply_overrides(cfg, shared)\n    hub_apply_session(shared)\n')
        # Do not serialize Hub absolute paths back into the shared legacy INI.
        source = replace_once(source, 'def write_config(cfg):\n', 'def write_config(cfg):\n    if HUB_SESSION:\n        return\n')
        source = replace_once(source, '        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")',
            '        "output_folder": str(globals().get("output_root", "")),\n        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")')
        return source
    edit(manifest["entrypoint"], runner)
    def main(source):
        source = replace_once(source, "        f.write('    execfile(_defaults_path, globals(), globals())\\n')",
            "        f.write('    execfile(_defaults_path, globals(), globals())\\n')\n        f.write('    _hub_runtime = os.path.join(os.path.dirname(_defaults_path), \"hub_runtime.py\")\\n')\n        f.write('    if os.path.isfile(_hub_runtime):\\n')\n        f.write('        execfile(_hub_runtime, globals(), globals())\\n')\n        f.write('        hub_apply_session(globals())\\n')")
        source = replace_once(source, 'input_folder = dc_in.getDirectory()', 'input_folder = hub_input_folder() or dc_in.getDirectory()')
        source = source.replace('output_parent = output_dc.getDirectory()', 'output_parent = hub_output_folder() or output_dc.getDirectory()')
        return source
    edit("GDL_code/09_BEAST_Workers_Main.py", main)
    def watchdog(source):
        source = replace_once(source, 'source = open(DEFAULTS_PATH, "r").read()', 'with open(DEFAULTS_PATH, "r") as defaults_file:\n                source = defaults_file.read()')
        source = replace_once(source, 'CONFIG_PATH = os.path.join(SUPPORT_DIR, "startup_paths.ini")',
            'with open(os.path.join(SUPPORT_DIR, "hub_runtime.py"), "r") as runtime_file:\n    eval(compile(runtime_file.read(), "hub_runtime.py", "exec"), globals(), globals())\nCONFIG_PATH = os.path.join(SUPPORT_DIR, "startup_paths.ini")')
        source = replace_once(source, '    return cfg\n\n\ndef _load_defaults_namespace', '    return hub_legacy_overrides(cfg)\n\n\ndef _load_defaults_namespace')
        source = replace_once(source, 'POLL_SECONDS = 2.0', 'POLL_SECONDS = 2.0\n\nHUB_SESSION = {}\nif os.environ.get("GDL_SESSION_CONFIG", ""):\n    with open(os.environ["GDL_SESSION_CONFIG"], "r") as _hub_file:\n        HUB_SESSION = json.load(_hub_file)\n    WATCHDOG_LOG_PATH = HUB_SESSION["watchdog_log"]\n\ndef _hub_stop():\n    return bool(HUB_SESSION and os.path.isfile(HUB_SESSION["stop_file"]))\n')
        source = replace_once(source, 'def _find_fiji_launcher():\n', 'def _find_fiji_launcher():\n    if HUB_SESSION:\n        return HUB_SESSION["fiji_executable"]\n')
        source = replace_once(source, 'def _status_path_for_session(session_id):\n', 'def _status_path_for_session(session_id):\n    if HUB_SESSION:\n        return HUB_SESSION["status_file"]\n')
        source = replace_once(source, 'def _cleanup_old_watchdog_status_files(keep_path=""):\n', 'def _cleanup_old_watchdog_status_files(keep_path=""):\n    if HUB_SESSION:\n        return\n')
        source = replace_once(source, 'def _session_id(attempt):\n', 'def _session_id(attempt):\n    if HUB_SESSION:\n        return HUB_SESSION["session_id"]\n')
        source = replace_once(source, '    while time.time() < startup_deadline:\n', '    while time.time() < startup_deadline:\n        if _hub_stop():\n            return "NORMAL"\n')
        source = replace_once(source, '    while True:\n        status = _read_status_file', '    while True:\n        if _hub_stop():\n            return "NORMAL"\n        status = _read_status_file')
        source = replace_once(source, '        active_pids = _fiji_process_ids()', '        if HUB_SESSION and state in ["COMPLETED", "CANCELED"]:\n            return "NORMAL"\n        active_pids = _fiji_process_ids()')
        source = replace_once(source, '    while True:\n        result = _launch_and_monitor', '    while True:\n        if _hub_stop():\n            return 0\n        if HUB_SESSION and attempt > 1:\n            _write_status_file(HUB_SESSION["status_file"], HUB_SESSION["session_id"], "RESTARTING", "Restarting Fiji after a crash.")\n        result = _launch_and_monitor')
        source = replace_once(source, '    _force_close_existing_fiji()\n', '    if _hub_stop():\n        return "NORMAL"\n    _force_close_existing_fiji()\n')
        return source
    edit(manifest["launcher"], watchdog)
    shutil.copyfile(ROOT / "analysis/gdl/hub_runtime.py", root / SUPPORT / "hub_runtime.py")
    write_json(root / "hub_manifest.json", manifest)
    return manifest


def stage_zip(archive, destination):
    """ZIP slip, links, duplicate names, bombs and stale runtime files rejected/skipped."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) > 2000 or sum(i.file_size for i in entries) > 100_000_000:
                raise ValueError("The GDL archive exceeds supported package limits.")
            runners = [PurePosixPath(i.filename) for i in entries if PurePosixPath(i.filename).name == "RUN IN FIJI.py"]
            if len(runners) != 1:
                raise ValueError("Choose a complete GDL package containing one RUN IN FIJI.py.")
            prefix = runners[0].parent
            seen = set()
            for item in entries:
                path = PurePosixPath(item.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in item.filename or ":" in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("The package contains an unsafe path or link.")
                if item.is_dir():
                    continue
                try:
                    relative = path.relative_to(prefix)
                except ValueError:
                    continue
                if "__pycache__" in relative.parts or relative.name.startswith("Fiji Watchdog") or relative.suffix in (".pyc", ".tmp"):
                    continue
                if str(relative).casefold() in seen:
                    raise ValueError("The package contains duplicate filenames.")
                seen.add(str(relative).casefold())
                target = destination / Path(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(item))
        manifest = adapt_engine(destination)
        manifest["source_sha256"] = archive_digest(archive)
        write_json(destination / "hub_manifest.json", manifest)
        return manifest
    except Exception:
        # Verified workspace-owned staging path only; never touch active packages.
        shutil.rmtree(destination)
        raise
