"""Streaming discovery. OneDrive name-surrogate redirects are never followed."""
import os
from pathlib import Path
from app.services.project_storage import EXCLUDED, redirects, IndexCancelled


def discover(root, cancel=None):
    root = Path(root)
    def walk(folder):
        if cancel and cancel():
            raise IndexCancelled('Index cancelled; completed batches and previous references are preserved.')
        try:
            if redirects(folder.lstat()):
                raise OSError('Filesystem redirect skipped')
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name in EXCLUDED:
                        continue
                    if cancel and cancel():
                        raise IndexCancelled('Index cancelled; completed batches are preserved.')
                    path = Path(entry.path)
                    try:
                        info = path.lstat()
                        if redirects(info):
                            yield path, None, 'Filesystem redirect skipped'
                        elif entry.is_dir(follow_symlinks=False):
                            yield path, info, 'directory'
                            yield from walk(path)
                        elif entry.is_file(follow_symlinks=False):
                            yield path, info, ''
                    except OSError:
                        yield path, None, 'File currently unavailable locally'
        except OSError:
            yield folder, None, 'Folder disconnected or inaccessible; previous index preserved'
    yield from walk(root)
