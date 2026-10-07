# Project Hub compatibility boundary. Python 2/Jython and Python 3 compatible.
# No processing, measurement, report or worker algorithms live here.
import os
import json

HUB_SESSION = {}
_hub_path = os.environ.get("GDL_SESSION_CONFIG", "").strip()
if _hub_path:
    with open(_hub_path, "r") as _hub_handle:
        HUB_SESSION = json.load(_hub_handle)
    if HUB_SESSION.get("schema_version") != 1 or not HUB_SESSION.get("session_id"):
        raise RuntimeError("Unsupported Hub session configuration")


def hub_startup_config(legacy):
    cfg = dict(legacy)
    cfg.update({"FIJI_LAUNCHER": HUB_SESSION.get("fiji_executable", ""),
                "JMP_EXECUTABLE": HUB_SESSION.get("jmp_executable", ""),
                "MODULE_FOLDER": HUB_SESSION.get("module_folder", ""),
                "DEFAULT_OUTPUT_FOLDER": HUB_SESSION.get("output_folder", ""),
                "EXTRA_USER_ROOTS": ";".join(HUB_SESSION.get("extra_search_roots", [])),
                "SHOW_PATH_DIALOG": "false"})
    return cfg


def hub_legacy_overrides(legacy):
    """Standalone fallback: local Hub overrides, then legacy INI, then detection."""
    cfg = dict(legacy)
    base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FuelCellProjectHub")
    try:
        with open(os.path.join(base, "local.json"), "r") as handle:
            software = json.load(handle).get("paths", {})
        for name, key in (("fiji", "FIJI_LAUNCHER"), ("jmp", "JMP_EXECUTABLE")):
            if software.get(name):
                cfg[key] = software[name]
    except (IOError, ValueError, AttributeError):
        pass
    try:
        with open(os.path.join(base, "gdl", "config.json"), "r") as handle:
            local = json.load(handle)
        paths = local.get("paths", {})
        for name, key in (("module_folder", "MODULE_FOLDER"), ("default_output_folder", "DEFAULT_OUTPUT_FOLDER")):
            if paths.get(name):
                cfg[key] = paths[name]
        if local.get("extra_search_roots"):
            cfg["EXTRA_USER_ROOTS"] = ";".join(local["extra_search_roots"])
        for name, key in (("quick_run_folder", "GDL_QUICK_RUN_FOLDER"), ("swift_magnification_folder", "GDL_SWIFT_FOLDER"),
                          ("default_input_folder", "GDL_INPUT_FOLDER"), ("report_output_folder", "GDL_REPORT_FOLDER")):
            if paths.get(name):
                os.environ[key] = str(paths[name])
        personal_quick = os.path.join(base, "gdl", "quick_runs")
        if not paths.get("quick_run_folder") and os.path.isdir(personal_quick):
            os.environ["GDL_QUICK_RUN_FOLDER"] = personal_quick
    except (IOError, ValueError, AttributeError, TypeError):
        pass
    return cfg


def hub_apply_session(shared):
    if not HUB_SESSION:
        reports = os.environ.get("GDL_REPORT_FOLDER", "")
        if reports:
            shared["ALL_REPORTS_FOLDER_MICHELSON"] = reports
            shared["ALL_REPORTS_FOLDER_VGOLF"] = reports
        return
    for key, variable in (("input_folder", "GDL_INPUT_FOLDER"), ("quick_run_folder", "GDL_QUICK_RUN_FOLDER"),
                          ("swift_magnification_folder", "GDL_SWIFT_FOLDER")):
        os.environ[variable] = str(HUB_SESSION.get(key, ""))
    reports = str(HUB_SESSION.get("report_output_folder", ""))
    shared["ALL_REPORTS_FOLDER_MICHELSON"] = reports
    shared["ALL_REPORTS_FOLDER_VGOLF"] = reports
    shared["DEFAULTS"]["jmp_exe"] = str(HUB_SESSION.get("jmp_executable", ""))
    shared["DEFAULTS"]["beast_fiji_executable"] = str(HUB_SESSION.get("fiji_executable", ""))
    # Java workers inherit the session; they retain their existing worker config.
    work = HUB_SESSION.get("temp_work_folder", "")
    if work:
        os.environ["TEMP"] = str(work)
        os.environ["TMP"] = str(work)
        try:
            from java.lang import System
            System.setProperty("java.io.tmpdir", str(work))
        except ImportError:
            pass


def hub_input_folder():
    return str(HUB_SESSION.get("input_folder", ""))


def hub_output_folder():
    return str(HUB_SESSION.get("output_folder", ""))
