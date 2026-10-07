# YOURE A BETA GDL Analysis v209 - run directly inside Fiji. ASCII only.
from __future__ import print_function
import os
import time
import json
import traceback

execfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "Defaults and Other Stuff", "hub_runtime.py"), globals(), globals())

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPORT_DIR = os.path.join(APP_DIR, "Defaults and Other Stuff")
CONFIG_PATH = os.path.join(SUPPORT_DIR, "startup_paths.ini")
DEFAULTS_PATH = os.path.join(SUPPORT_DIR, "GDL_User_Defaults.py")
DEFAULT_CODE_DIR = os.path.join(APP_DIR, "GDL_code")
MODULES = ['01_Core_Imports_Helpers.py', '02_User_Interface_Pages.py', '03_User_Interface_Settings.py', '04_Image_Processing_Sweeps.py', '05_Reports_Manual_Tools_Pore_Maps.py', '06A_Large_Pore_Repair.py', '06B_Fiber_Fixer.py', '06_Threshold_Analysis_JMP.py', '07_Run_Engine_Exports.py', '08_Workbook_JMP_Launch_Helpers.py', '09_BEAST_Workers_Main.py']

def read_config():
    cfg = {}
    try:
        for line in open(CONFIG_PATH, "r"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            cfg[key.strip()] = value.strip()
    except Exception:
        pass
    return cfg

def write_config(cfg):
    if HUB_SESSION:
        return
    keys = ["FIJI_LAUNCHER", "JMP_EXECUTABLE", "MODULE_FOLDER", "DEFAULT_OUTPUT_FOLDER", "EXTRA_USER_ROOTS", "SHOW_PATH_DIALOG"]
    f = open(CONFIG_PATH, "w")
    try:
        f.write("# YOURE A BETA GDL Analysis v209 startup path overrides\n")
        f.write("# Leave a value blank to use the bundled defaults and automatic detection.\n")
        for key in keys:
            f.write(key + "=" + str(cfg.get(key, "")) + "\n")
    finally:
        f.close()

def startup_dialog(cfg, default_extra_roots):
    if str(cfg.get("SHOW_PATH_DIALOG", "true")).lower() not in ("true", "1", "yes", "on"):
        return cfg
    from ij.gui import GenericDialog
    gd = GenericDialog("YOURE A BETA GDL Analysis v209 - Startup Paths")
    gd.addMessage("Paths are optional. Blank values use the bundled defaults and automatic detection.")
    gd.addStringField("Fiji launcher", cfg.get("FIJI_LAUNCHER", ""), 65)
    gd.addStringField("JMP executable", cfg.get("JMP_EXECUTABLE", ""), 65)
    gd.addStringField("Code folder", cfg.get("MODULE_FOLDER", DEFAULT_CODE_DIR), 65)
    gd.addStringField("Default output folder", cfg.get("DEFAULT_OUTPUT_FOLDER", ""), 65)
    gd.addStringField("Extra user roots (semicolon separated)", cfg.get("EXTRA_USER_ROOTS", default_extra_roots), 65)
    gd.addCheckbox("Show this path dialog at startup", True)
    gd.showDialog()
    if gd.wasCanceled():
        raise SystemExit
    cfg["FIJI_LAUNCHER"] = gd.getNextString().strip()
    cfg["JMP_EXECUTABLE"] = gd.getNextString().strip()
    cfg["MODULE_FOLDER"] = gd.getNextString().strip()
    cfg["DEFAULT_OUTPUT_FOLDER"] = gd.getNextString().strip()
    cfg["EXTRA_USER_ROOTS"] = gd.getNextString().strip()
    cfg["SHOW_PATH_DIALOG"] = "true" if gd.getNextBoolean() else "false"
    write_config(cfg)
    return cfg

def apply_overrides(cfg, shared):
    jmp = cfg.get("JMP_EXECUTABLE", "").strip()
    if jmp:
        shared["JMP_EXE_DEFAULT"] = jmp
        try: shared["DEFAULTS"]["jmp_exe"] = jmp
        except Exception: pass
    output = cfg.get("DEFAULT_OUTPUT_FOLDER", "").strip()
    if output and os.path.isdir(output):
        try:
            from ij.io import OpenDialog, DirectoryChooser
            OpenDialog.setDefaultDirectory(output)
            try: DirectoryChooser.setDefaultDirectory(output)
            except Exception: pass
        except Exception: pass
    os.environ["GDL_EXTRA_USER_ROOTS"] = cfg.get("EXTRA_USER_ROOTS", "")
    os.environ["GDL_FIJI_LAUNCHER_OVERRIDE"] = cfg.get("FIJI_LAUNCHER", "")
    os.environ["GDL_JMP_EXE_OVERRIDE"] = jmp
    os.environ["GDL_V193_LAUNCHER"] = os.path.abspath(__file__)

def show_startup_error(message):
    try:
        from ij import IJ
        IJ.error("YOURE A BETA GDL Analysis v209 - Startup Error", message)
    except Exception:
        try:
            from javax.swing import JOptionPane
            JOptionPane.showMessageDialog(None, message, "YOURE A BETA GDL Analysis v209 - Startup Error", JOptionPane.ERROR_MESSAGE)
        except Exception:
            print(message)

def write_watchdog_status(state, message=""):
    status_path = os.environ.get("GDL_V193_WATCHDOG_STATUS", "").strip()
    session_id = os.environ.get("GDL_V193_WATCHDOG_SESSION", "").strip()
    if status_path == "" or session_id == "":
        return
    payload = {
        "session_id": session_id,
        "state": str(state),
        "message": str(message).replace("\r", " ").replace("\n", " "),
        "output_folder": str(globals().get("output_root", "")),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    temp_path = status_path + "." + session_id + ".tmp"
    writer = None
    try:
        writer = open(temp_path, "w")
        json.dump(payload, writer, indent=2, sort_keys=True)
        writer.write("\n")
    finally:
        if writer is not None:
            writer.close()
    if os.path.isfile(status_path):
        try:
            os.remove(status_path)
        except Exception:
            pass
    os.rename(temp_path, status_path)

def run_code_modules(shared, code_dir, module_names):
    for name in module_names:
        path = os.path.join(code_dir, name)
        if not os.path.isfile(path):
            message = "Missing GDL code module:\n" + path
            show_startup_error(message)
            raise RuntimeError(message)
        try:
            execfile(path, shared, shared)
        except SystemExit:
            try:
                _finalizer = shared.get("emergency_finalize_report_from_shared", None)
                if _finalizer is not None:
                    _finalizer(shared, "SystemExit / user cancellation")
            except Exception:
                pass
            return "CANCELED"
    return "COMPLETED"


write_watchdog_status("STARTING", "RUN IN FIJI.py started.")
try:
    if not os.path.isfile(DEFAULTS_PATH):
        message = "Missing user defaults file:\n" + DEFAULTS_PATH + "\n\nKeep the Defaults and Other Stuff folder beside RUN IN FIJI.py."
        show_startup_error(message)
        raise RuntimeError(message)

    shared = globals()
    execfile(DEFAULTS_PATH, shared, shared)
    DEFAULT_CODE_DIR = os.path.join(APP_DIR, str(shared.get("DEFAULT_CODE_FOLDER", "GDL_code")))
    MODULES = list(shared.get("CODE_MODULE_FILES", MODULES))
    cfg = hub_startup_config(read_config()) if HUB_SESSION else startup_dialog(hub_legacy_overrides(read_config()), str(shared.get("DEFAULT_EXTRA_USER_ROOTS", "")))
    code_dir = cfg.get("MODULE_FOLDER", "").strip() or DEFAULT_CODE_DIR
    if not os.path.isdir(code_dir):
        message = "Missing GDL code folder:\n" + code_dir + "\n\nKeep RUN IN FIJI.py, GDL_code, and Defaults and Other Stuff together."
        show_startup_error(message)
        raise RuntimeError(message)

    shared["GDL_APP_DIR"] = APP_DIR
    shared["GDL_SUPPORT_DIR"] = SUPPORT_DIR
    shared["GDL_APP_LAUNCHER_PATH"] = os.path.abspath(__file__)
    shared["GDL_MODULE_DIR_OVERRIDE"] = code_dir
    apply_overrides(cfg, shared)
    hub_apply_session(shared)
    write_watchdog_status("RUNNING", "GDL code modules are running.")
    final_state = run_code_modules(shared, code_dir, MODULES)
    if final_state == "CANCELED":
        write_watchdog_status("CANCELED", "The user canceled or closed the GDL setup/run.")
    else:
        write_watchdog_status("COMPLETED", "The GDL script completed normally.")
except SystemExit:
    try:
        _finalizer = shared.get("emergency_finalize_report_from_shared", None)
        if _finalizer is not None:
            _finalizer(shared, "SystemExit / user cancellation")
    except Exception:
        pass
    write_watchdog_status("CANCELED", "The GDL script exited by user cancellation.")
    raise
except BaseException as run_error:
    try:
        error_text = str(run_error)
    except Exception:
        error_text = "Unknown script failure"
    try:
        _finalizer = shared.get("emergency_finalize_report_from_shared", None)
        if _finalizer is not None:
            _finalizer(shared, error_text)
    except Exception:
        pass
    write_watchdog_status("FAILED", error_text)
    try:
        show_startup_error("The GDL script failed:\n" + error_text + "\n\nThe watchdog console will report the failure.")
    except Exception:
        pass
    try:
        print(traceback.format_exc())
    except Exception:
        pass
    raise
