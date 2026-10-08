"""Explicit mapping of an existing shared project; no automatic initialization."""
import os
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox


def connect_shared_project(store, parent=None, select=False):
    drive = os.environ.get('OneDriveCommercial') or os.environ.get('OneDrive')
    candidates = [store.local.get('shared_root')]
    if drive:
        candidates.append(str(Path(drive) / 'GDL research - General'))
    candidates.append(str(Path.home() / 'OneDrive - tarleton.edu (NTNET)' / 'GDL research - General'))
    for root in ([] if select else dict.fromkeys(p for p in candidates if p)):
        try:
            store.attach_shared(root)
            return True
        except (OSError, ValueError):
            pass
    while True:
        root = QFileDialog.getExistingDirectory(parent, 'Locate your synchronized GDL research - General project',
                                               next((p for p in candidates if p), str(Path.home())))
        if not root:
            return False
        try:
            store.attach_shared(root)
            return True
        except (OSError, ValueError):
            from app.services.storage import read_json
            pinned = read_json(store.config_dir / 'shared_project_public.json', {}).get('project_id')
            if not pinned and not (Path(root) / '.project_hub/identity.json').exists() and not store.local.get('shared_project_id'):
                answer = QMessageBox.question(parent, 'Project owner setup',
                    'This folder has no Hub identity. Only the project owner should initialize it. '
                    'Register this device as the sole indexing authority? Existing research files will stay in place. '
                    'This does not grant administrator access to a backend.',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer == QMessageBox.Yes:
                    from app.services.shared_index import SharedIndex
                    try:
                        SharedIndex.enroll(store, root, confirmed=True)
                        store.attach_shared(root)
                        return True
                    except (OSError, ValueError):
                        pass
            QMessageBox.information(parent, 'Shared project unavailable',
                'Choose a synchronized copy of the configured project. Its identity may be unavailable or conflicting. '
                'Ask the project owner to check setup and synchronization. No research files were changed.')
