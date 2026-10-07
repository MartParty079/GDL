"""One resolver for source-tree and PyInstaller-bundled resources."""
import sys
from pathlib import Path


def resource_root():
    if getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def resource_path(relative):
    return resource_root() / relative


RESOURCE_ROOT = resource_root()
