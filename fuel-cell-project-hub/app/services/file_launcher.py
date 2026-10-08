"""Explicit OS file actions. Argument lists only; indexed scripts open in an editor."""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = {".py", ".m", ".js", ".ts", ".sh", ".bat", ".cmd", ".ps1", ".vbs"}
BLOCKED = {
    ".exe",
    ".com",
    ".scr",
    ".msi",
    ".lnk",
    ".url",
    ".hta",
    ".reg",
    ".cpl",
    ".jar",
    ".appref-ms",
    ".application",
    ".chm",
}


def checked_path(path, folder=False):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("Choose an absolute file path.")
    if not (path.is_dir() if folder else path.is_file()):
        raise ValueError(
            "File currently unavailable locally. Reconnect its source or locate the file."
        )
    return path


def open_file(path, editor=None):
    path = checked_path(path)
    if path.suffix.lower() in BLOCKED:
        raise ValueError(
            "Open the containing folder to inspect this executable or shortcut."
        )
    if path.suffix.lower() in SCRIPTS:
        if editor:
            executable = checked_path(editor)
            return subprocess.Popen([str(executable), str(path)])
        if sys.platform == "win32":
            return subprocess.Popen(["notepad.exe", str(path)])
        raise ValueError("Configure a code editor in Settings before opening scripts.")
    if sys.platform == "win32":
        return os.startfile(str(path))
    return subprocess.Popen(
        ["open" if sys.platform == "darwin" else "xdg-open", str(path)]
    )


def open_folder(path):
    path = checked_path(path, folder=True)
    if sys.platform == "win32":
        return os.startfile(str(path))
    return subprocess.Popen(
        ["open" if sys.platform == "darwin" else "xdg-open", str(path)]
    )


def show_in_folder(path):
    path = Path(path)
    checked_path(path.parent, folder=True)
    if sys.platform == "win32" and path.is_file():
        return subprocess.Popen(["explorer.exe", "/select,", str(path)])
    return open_folder(path.parent)
