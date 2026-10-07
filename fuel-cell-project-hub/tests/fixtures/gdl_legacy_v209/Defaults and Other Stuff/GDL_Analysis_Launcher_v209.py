# YOURE A BETA GDL Analysis v209 persistent Fiji watchdog. ASCII only.
from __future__ import print_function
import os
import sys
import time
import json
import subprocess
import traceback
import glob
import tempfile

SUPPORT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SUPPORT_DIR)
CONFIG_PATH = os.path.join(SUPPORT_DIR, "startup_paths.ini")
DEFAULTS_PATH = os.path.join(SUPPORT_DIR, "GDL_User_Defaults.py")
RUN_SCRIPT_PATH = os.path.join(APP_DIR, "RUN IN FIJI.py")
WATCHDOG_STATUS_PATH = os.path.join(SUPPORT_DIR, "Fiji Watchdog Status.txt")  # legacy cleanup target
WATCHDOG_LOG_PATH = os.path.join(SUPPORT_DIR, "Fiji Watchdog Log.txt")
POLL_SECONDS = 2.0
MISSING_PROCESS_CHECKS = 3
STARTUP_TIMEOUT_SECONDS = 45.0
STARTUP_STABILIZE_SECONDS = 6.0
RESTART_DELAY_SECONDS = 5.0


def _timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(message):
    line = "[" + _timestamp() + "] " + str(message)
    try:
        print(line)
        sys.stdout.flush()
    except Exception:
        pass
    try:
        handle = open(WATCHDOG_LOG_PATH, "a")
        try:
            handle.write(line + "\n")
        finally:
            handle.close()
    except Exception:
        pass


def _startup_config():
    cfg = {}
    try:
        for line in open(CONFIG_PATH, "r"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                cfg[key.strip()] = value.strip()
    except Exception:
        pass
    return cfg


def _load_defaults_namespace():
    ns = {}
    if not os.path.isfile(DEFAULTS_PATH):
        return ns
    try:
        if str(sys.platform).lower().startswith("java"):
            execfile(DEFAULTS_PATH, ns, ns)
        else:
            source = open(DEFAULTS_PATH, "r").read()
            eval(compile(source, DEFAULTS_PATH, "exec"), ns, ns)
    except Exception:
        pass
    return ns


USER_DEFAULTS = _load_defaults_namespace()


def _is_jython():
    try:
        import java
        return True
    except Exception:
        return False


def _show_error(message):
    _log("ERROR: " + str(message).replace("\n", " | "))
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(message), "YOURE A BETA GDL Analysis v209", 0x10)
    except Exception:
        pass


def _find_fiji_launcher():
    cfg = _startup_config()
    override = cfg.get("FIJI_LAUNCHER", "").strip()
    if override and os.path.isfile(override):
        return override

    known_launchers = list(USER_DEFAULTS.get("DEFAULT_FIJI_LAUNCHERS", []))
    current_home = os.path.abspath(os.path.expanduser("~")).lower()
    known_launchers.sort(key=lambda value: 0 if os.path.abspath(os.path.dirname(value)).lower().startswith(current_home) else 1)
    for candidate in known_launchers:
        if os.path.isfile(candidate):
            return candidate

    cfg_roots = cfg.get("EXTRA_USER_ROOTS", "").strip()
    default_roots = str(USER_DEFAULTS.get("DEFAULT_EXTRA_USER_ROOTS", ""))
    extra_roots = [x.strip() for x in (cfg_roots or default_roots).split(";") if x.strip()]
    roots = [os.path.join(os.path.expanduser("~"), "Fiji"), os.path.join(os.path.expanduser("~"), "Fiji.app")]
    for base in extra_roots:
        roots.extend([os.path.join(base, "Fiji"), os.path.join(base, "Fiji.app")])

    names = ["fiji-windows-x64.exe", "fiji.exe", "ImageJ-win64.exe", "ImageJ-win32.exe", "ImageJ.exe", "fiji.bat", "fiji.cmd"]
    for root in roots:
        if not os.path.isdir(root):
            continue
        if not (os.path.isdir(os.path.join(root, "jars")) and os.path.isdir(os.path.join(root, "plugins"))):
            continue
        for name in names:
            path = os.path.join(root, name)
            if os.path.isfile(path):
                return path
    return ""


def _status_path_for_session(session_id):
    safe = "".join([ch if ch.isalnum() or ch in "-_" else "_" for ch in str(session_id)])
    return os.path.join(SUPPORT_DIR, "Fiji Watchdog Status " + safe + ".json")


def _cleanup_old_watchdog_status_files(keep_path=""):
    keep_abs = os.path.abspath(str(keep_path)) if str(keep_path).strip() else ""
    patterns = [
        os.path.join(SUPPORT_DIR, "Fiji Watchdog Status*.json"),
        os.path.join(SUPPORT_DIR, "Fiji Watchdog Status*.tmp"),
        WATCHDOG_STATUS_PATH,
        WATCHDOG_STATUS_PATH + ".*.tmp"
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                if keep_abs and os.path.abspath(path) == keep_abs:
                    continue
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass


def _write_status_file(status_path, session_id, state, message=""):
    payload = {
        "session_id": str(session_id),
        "state": str(state),
        "message": str(message).replace("\r", " ").replace("\n", " "),
        "timestamp": _timestamp()
    }
    temp_path = str(status_path) + ".tmp"
    handle = None
    try:
        handle = open(temp_path, "w")
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    finally:
        if handle is not None:
            handle.close()
    if os.path.isfile(status_path):
        try:
            os.remove(status_path)
        except Exception:
            pass
    os.rename(temp_path, status_path)


def _read_status_file(status_path, session_id):
    try:
        handle = open(status_path, "r")
        try:
            payload = json.load(handle)
        finally:
            handle.close()
        if str(payload.get("session_id", "")) != str(session_id):
            return {"state": "UNKNOWN", "message": "Ignored status from another launch session."}
        return payload
    except Exception as exc:
        return {"state": "STARTING", "message": "Waiting for RUN IN FIJI.py status: " + str(exc)}


def _force_close_existing_fiji():
    """Force-close prior Fiji/ImageJ processes before a clean watchdog launch."""
    if os.name != "nt":
        return
    devnull = open(os.devnull, "wb")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    image_names = [
        "fiji-windows-x64.exe", "fiji.exe", "ImageJ-win64.exe",
        "ImageJ-win32.exe", "ImageJ.exe"
    ]
    try:
        for image_name in image_names:
            try:
                subprocess.call(
                    ["taskkill", "/F", "/T", "/IM", image_name],
                    stdout=devnull, stderr=devnull, creationflags=creationflags
                )
            except Exception:
                pass
        ps_command = (
            "$ErrorActionPreference='SilentlyContinue'; "
            "Get-CimInstance Win32_Process | Where-Object { "
            "($_.Name -match '^(java|javaw)\\.exe$') -and "
            "($_.CommandLine -match '(?i)(Fiji\\.app|[\\\\/]Fiji[\\\\/]|ImageJ)') "
            "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        try:
            subprocess.call(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                stdout=devnull, stderr=devnull, creationflags=creationflags
            )
        except Exception:
            pass
    finally:
        try:
            devnull.close()
        except Exception:
            pass
    time.sleep(1.5)
    _remove_stale_imagej_stub_files()
    time.sleep(0.5)


def _remove_stale_imagej_stub_files():
    """Remove current-user ImageJ RMI stub files after all Fiji processes are closed."""
    if os.name != "nt":
        return []
    username = str(os.environ.get("USERNAME", os.environ.get("USER", ""))).strip()
    temp_roots = []
    for candidate in [os.environ.get("TEMP", ""), os.environ.get("TMP", ""),
                      os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
                      tempfile.gettempdir()]:
        try:
            candidate = os.path.abspath(str(candidate))
            if candidate and os.path.isdir(candidate) and candidate not in temp_roots:
                temp_roots.append(candidate)
        except Exception:
            pass
    removed = []
    patterns = []
    if username:
        patterns.append("ImageJ-" + username + "-*.stub")
    patterns.append("ImageJ--*.stub")
    for temp_root in temp_roots:
        for pattern in patterns:
            for path in glob.glob(os.path.join(temp_root, pattern)):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        removed.append(path)
                except Exception as exc:
                    _log("Could not remove stale ImageJ stub " + str(path) + ": " + str(exc))
    if removed:
        _log("Removed stale ImageJ single-instance stub file(s): " + "; ".join(removed))
    return removed


def _fiji_process_ids():
    """Return currently running Fiji/ImageJ native or identified Java process IDs."""
    if os.name != "nt":
        return set()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    ps_command = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -match '^(fiji-windows-x64|fiji|ImageJ-win64|ImageJ-win32|ImageJ)\\.exe$') -or "
        "(($_.Name -match '^(java|javaw)\\.exe$') -and "
        "($_.CommandLine -match '(?i)(Fiji\\.app|[\\\\/]Fiji[\\\\/]|ImageJ)')) "
        "} | Select-Object -ExpandProperty ProcessId"
    )
    try:
        proc = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags
        )
        stdout_data, _stderr_data = proc.communicate()
        if not isinstance(stdout_data, str):
            stdout_data = stdout_data.decode("utf-8", "ignore")
        result = set()
        for line in stdout_data.splitlines():
            try:
                result.add(int(str(line).strip()))
            except Exception:
                pass
        return result
    except Exception:
        return set()


def _is_modern_fiji_launcher(launcher):
    try:
        launcher_path = os.path.abspath(str(launcher))
        root = os.path.dirname(launcher_path)
        name = os.path.basename(launcher_path).lower()
        if name in ["fiji.bat", "fiji.cmd", "fiji.exe", "fiji"]:
            return True
        if name.startswith("fiji-windows-") and name.endswith(".exe"):
            return True
        if name.startswith("fiji-linux-") or name.startswith("fiji-macos-"):
            return True
        return (os.path.isfile(os.path.join(root, "config", "jaunch", "fiji.toml")) or
                os.path.isfile(os.path.join(root, "config", "fiji.toml")))
    except Exception:
        return False


def _build_fiji_command(launcher):
    args = ["--no-python"]
    if _is_modern_fiji_launcher(launcher):
        args.append("--forbid-single-instance")
        args.append("--allow-multiple")
    else:
        args.append("-port0")
    args.extend(["--no-splash", "--run", RUN_SCRIPT_PATH])
    if launcher.lower().endswith((".bat", ".cmd")):
        return ["cmd.exe", "/d", "/s", "/c", "call", launcher] + args
    return [launcher] + args


def _session_id(attempt):
    return str(int(time.time() * 1000)) + "-" + str(os.getpid()) + "-" + str(attempt)


def _launch_and_monitor(launcher, attempt):
    _force_close_existing_fiji()
    _remove_stale_imagej_stub_files()
    session_id = _session_id(attempt)
    status_path = _status_path_for_session(session_id)
    _cleanup_old_watchdog_status_files(status_path)
    _write_status_file(status_path, session_id, "STARTING", "Watchdog is starting Fiji.")

    env = os.environ.copy()
    env["GDL_V193_LAUNCHER"] = RUN_SCRIPT_PATH
    env["GDL_V193_WATCHDOG_STATUS"] = status_path
    env["GDL_V193_WATCHDOG_SESSION"] = session_id
    cmd = _build_fiji_command(launcher)

    _log("Launching Fiji attempt " + str(attempt) + ".")
    _log("Fiji command: " + " ".join(['\"' + item + '\"' if ' ' in str(item) else str(item) for item in cmd]))
    try:
        process = subprocess.Popen(cmd, cwd=os.path.dirname(launcher), env=env)
    except Exception as exc:
        _write_status_file(status_path, session_id, "LAUNCH_FAILED", str(exc))
        _log("FIJI LAUNCH FAILED: " + str(exc))
        return "CRASH"

    tracked_pids = set([int(process.pid)])
    discovered_fiji = set()
    startup_deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    last_new_pid_time = time.time()

    while time.time() < startup_deadline:
        current_fiji = _fiji_process_ids()
        new_pids = current_fiji.difference(discovered_fiji)
        if len(new_pids) > 0:
            discovered_fiji.update(new_pids)
            tracked_pids.update(new_pids)
            last_new_pid_time = time.time()
        if len(discovered_fiji) > 0 and time.time() - last_new_pid_time >= STARTUP_STABILIZE_SECONDS:
            break
        return_code = process.poll()
        if return_code is not None and return_code != 0 and len(current_fiji) == 0:
            _log("Fiji launcher exited during startup with code " + str(return_code) + ".")
            return "CRASH"
        time.sleep(1.0)

    current_fiji = _fiji_process_ids()
    discovered_fiji.update(current_fiji)
    tracked_pids.update(current_fiji)
    if len(discovered_fiji) == 0:
        _log("No Fiji/ImageJ process was detected after launch within " + str(int(STARTUP_TIMEOUT_SECONDS)) + " seconds.")
        try:
            process.terminate()
        except Exception:
            pass
        return "CRASH"

    tracked_fiji_pids = set(discovered_fiji)
    _log("Fiji watchdog is active. Tracked Fiji/ImageJ process IDs: " + ", ".join([str(pid) for pid in sorted(tracked_fiji_pids)]))
    _log("The command prompt will remain open. Press Ctrl+C here to stop the watchdog.")

    missing_checks = 0
    last_reported_state = ""
    while True:
        status = _read_status_file(status_path, session_id)
        state = str(status.get("state", "UNKNOWN")).upper()
        if state != last_reported_state:
            _log("Fiji script state: " + state + (" - " + str(status.get("message", "")) if str(status.get("message", "")) else ""))
            last_reported_state = state

        active_pids = _fiji_process_ids()
        tracked_alive = tracked_fiji_pids.intersection(active_pids)
        if len(tracked_alive) > 0:
            missing_checks = 0
        else:
            missing_checks += 1

        if missing_checks >= MISSING_PROCESS_CHECKS:
            exit_code = process.poll()
            exit_note = "unknown" if exit_code is None else str(exit_code)
            if state in ["COMPLETED", "CANCELED"]:
                _log("Fiji closed after script state " + state + ". Exit code: " + exit_note + ". No automatic rerun is needed.")
                return "NORMAL"
            _log("============================================================")
            _log("FIJI CRASH DETECTED. The run did not reach COMPLETED/CANCELED.")
            _log("Last script state: " + state + "; launcher exit code: " + exit_note + ".")
            _log("Fiji will be relaunched and RUN IN FIJI.py will be rerun automatically.")
            _log("============================================================")
            return "CRASH"

        time.sleep(POLL_SECONDS)


def _watchdog_main():
    launcher = _find_fiji_launcher()
    if not launcher:
        _show_error(
            "Fiji could not be found. Edit DEFAULT_FIJI_LAUNCHERS in "
            "Defaults and Other Stuff\\GDL_User_Defaults.py or set FIJI_LAUNCHER "
            "in Defaults and Other Stuff\\startup_paths.ini."
        )
        return 2
    if not os.path.isfile(RUN_SCRIPT_PATH):
        _show_error("Missing RUN IN FIJI.py:\n" + RUN_SCRIPT_PATH)
        return 3

    _log("YOURE A BETA v209 persistent Fiji watchdog started.")
    _log("Existing Fiji/ImageJ processes will be force-closed before each launch.")
    attempt = 1
    while True:
        result = _launch_and_monitor(launcher, attempt)
        if result == "NORMAL":
            return 0
        _log("Restarting Fiji in " + str(int(RESTART_DELAY_SECONDS)) + " seconds. Automatic rerun attempt " + str(attempt + 1) + ".")
        time.sleep(RESTART_DELAY_SECONDS)
        attempt += 1


def _run_inside_fiji():
    if not os.path.isfile(RUN_SCRIPT_PATH):
        raise RuntimeError("Missing RUN IN FIJI.py: " + RUN_SCRIPT_PATH)
    shared = globals()
    shared["GDL_APP_DIR"] = APP_DIR
    shared["GDL_SUPPORT_DIR"] = SUPPORT_DIR
    shared["GDL_APP_LAUNCHER_PATH"] = RUN_SCRIPT_PATH
    execfile(RUN_SCRIPT_PATH, shared, shared)


if __name__ == "__main__":
    try:
        if _is_jython():
            _run_inside_fiji()
        else:
            sys.exit(_watchdog_main())
    except KeyboardInterrupt:
        _log("Watchdog stopped by Ctrl+C. Fiji will not be relaunched by this console.")
        sys.exit(130)
    except Exception as exc:
        _log("WATCHDOG ERROR: " + str(exc))
        _log(traceback.format_exc())
        sys.exit(5)
