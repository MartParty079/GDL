"""Optional Qt directory watching plus periodic authoritative reconciliation."""
import os
from pathlib import Path
from PySide6.QtCore import QObject, QFileSystemWatcher, QTimer, Signal
from app.services.project_storage import EXCLUDED, redirects


class IndexWatcher(QObject):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.schedule)
        self.watcher.fileChanged.connect(self.schedule)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(1500)
        self.debounce.timeout.connect(self.refresh_requested)
        self.periodic = QTimer(self)
        self.periodic.timeout.connect(self.refresh_requested)

    def configure(self, roots, watching=False, automatic=False, minutes=10):
        self.debounce.stop()
        old = self.watcher.directories() + self.watcher.files()
        if old:
            self.watcher.removePaths(old)
        self.periodic.stop()
        if automatic:
            self.periodic.start(max(1, int(minutes)) * 60000)
        if watching:
            paths = []
            # Bounded watches avoid exhausting Windows handles on legacy data.
            # Periodic reconciliation covers deeper folders and missed events.
            for root in roots:
                root = Path(root)
                if not root.is_dir() or redirects(root.lstat()):
                    continue
                paths.append(str(root))
                try:
                    for folder, directories, files in os.walk(root, followlinks=False):
                        directories[:] = [d for d in directories if d not in EXCLUDED and not redirects((Path(folder) / d).lstat())]
                        paths.append(str(folder))
                        if len(paths) >= 512:
                            break
                except OSError:
                    continue
                if len(paths) >= 512:
                    break
            if paths:
                self.watcher.addPaths(list(dict.fromkeys(paths)))
            if not self.periodic.isActive():
                self.periodic.start(max(1, int(minutes)) * 60000)

    def schedule(self, *args):
        self.debounce.start()

    def stop(self):
        self.periodic.stop()
        self.debounce.stop()
