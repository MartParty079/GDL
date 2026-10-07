"""Conservative detection. Never install or execute a discovered file during scanning."""
import os
import shutil
import subprocess
import webbrowser
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class LaunchType(str, Enum):
    EXE = "exe"
    URI = "uri"
    URL = "url"


def launch_type(item):
    """Entries created before launch types were introduced remain executables."""
    try:
        return LaunchType(item.get("launch_type", "exe"))
    except ValueError as exc:
        raise ValueError(f"Unsupported launch type: {item.get('launch_type')}") from exc


def launch_target(item, kind):
    target = item.get("launch_target", "").strip()
    if not target:
        raise ValueError(f"No launch target configured for {item['name']}.")
    parsed = urlparse(target)
    if kind == LaunchType.URL:
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError("Web launchers require a complete http/https address.")
    elif kind == LaunchType.URI:
        if not parsed.scheme or parsed.scheme in ("file", "javascript", "data", "vbscript", "shell", "http", "https") or len(parsed.scheme) == 1:
            raise ValueError("URI launchers require an application protocol such as msteams://.")
    return target


def valid_executable(value):
    path = Path(value)
    return path.is_file() and path.suffix.lower() == ".exe" and "windowsapps" not in str(path).lower()


def registry_candidates(executables):
    if os.name != "nt":
        return []
    import winreg
    results = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for name in executables:
                try:
                    with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}",
                                        0, winreg.KEY_READ | view) as key:
                        results.append(winreg.QueryValueEx(key, "")[0].strip('"'))
                except OSError:
                    pass
    return results


def detect(item, configured=None):
    try:
        kind = launch_type(item)
        if kind != LaunchType.EXE:
            target = launch_target(item, kind)
            return {"path": "", "target": target, "source": "Web" if kind == LaunchType.URL else "Windows URI Protocol · test launch to verify",
                    "status": "Ready" if kind == LaunchType.URL else "Needs test"}
    except ValueError as exc:
        return {"path": "", "source": str(exc), "status": "Missing"}
    if configured:
        if valid_executable(configured):
            return {"path": str(Path(configured).resolve()), "source": "Configured", "status": "Ready"}
        return {"path": configured, "source": "Configured path is unavailable", "status": "Missing"}
    candidates = registry_candidates(item["executables"])
    candidates.extend(p for name in item["executables"] if (p := shutil.which(name)))
    roots = [Path(os.environ[key]) for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA") if os.environ.get(key)]
    roots.extend([Path.home() / "Desktop", Path.home() / "Downloads"])
    for root in roots:
        for pattern in item.get("patterns", []):
            try:
                candidates.extend(str(p) for p in sorted(root.glob(pattern), reverse=True))
            except OSError:
                pass
    for candidate in candidates:
        if valid_executable(candidate):
            return {"path": str(Path(candidate).resolve()), "source": "Detected", "status": "Ready"}
    return {"path": "", "source": "Locate the application or use the installation guide", "status": "Missing"}


def open_resource(value):
    if not value:
        raise ValueError("Set this link or folder in Settings first.")
    parsed = urlparse(value)
    if parsed.scheme in ("https", "http"):
        if not parsed.netloc:
            raise ValueError("Enter a complete web address.")
        if not webbrowser.open(value):
            raise ValueError("No browser could open this address.")
    elif Path(value).is_dir() or (Path(value).is_file() and Path(value).suffix.lower() in (".docx", ".xlsx", ".pdf", ".txt", ".md")):
        os.startfile(str(Path(value).resolve()))
    else:
        raise ValueError("Use an http/https link, an existing folder, or a project document.")


def launch(item, result=None, project_folder=""):
    kind = launch_type(item)
    if kind == LaunchType.URI:
        os.startfile(launch_target(item, kind))
        return
    if kind == LaunchType.URL:
        if not webbrowser.open(launch_target(item, kind)):
            raise ValueError("No browser could open this address.")
        return
    result = result or {}
    executable = result.get("path", "")
    if not executable or not valid_executable(executable):
        raise ValueError("The executable is unavailable. Re-scan or locate it first.")
    cwd = project_folder if project_folder and Path(project_folder).is_dir() else str(Path.home())
    if item["id"] == "python":
        subprocess.Popen([executable], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        return
    if item["id"] == "git":
        # No shell interpolation; a normal terminal keeps command-line tools usable.
        environment = os.environ.copy()
        environment["PATH"] = str(Path(executable).parent) + os.pathsep + environment.get("PATH", "")
        subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/K"], cwd=cwd, env=environment,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        return
    subprocess.Popen([executable], cwd=cwd)
