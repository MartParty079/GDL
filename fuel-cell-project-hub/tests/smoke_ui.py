"""Run directly from the project root: python tests/smoke_ui.py."""
import os
import copy
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from app.services.storage import Store, ROOT
from app.ui.window import HubWindow

with tempfile.TemporaryDirectory() as temporary:
    app = QApplication([])
    test_root = Path(temporary) / "project"
    (test_root / "config").mkdir(parents=True)
    for name in ("project_defaults.json", "software_manifest.json"):
        shutil.copyfile(ROOT / "config" / name, test_root / "config" / name)
    store = Store(test_root, Path(temporary) / "local")
    window = HubWindow(store)
    window.show()
    deadline = time.monotonic() + 30
    app.processEvents()
    while window.scanning or window.workers:
        app.processEvents()
        if time.monotonic() > deadline:
            raise TimeoutError("Software scan did not complete")
        time.sleep(0.01)
    assert len(window.results) == len(store.manifest)
    for name in window.pages:
        window.show_page(name)
        app.processEvents()
        assert window.tabs.tabText(window.tabs.currentIndex()) == name
    store.add_bug("Smoke test", "Temporary report", {"page": "Bugs"}, "test")
    updated = copy.deepcopy(store.project)
    updated["goal"] = "Temporary verification goal"
    store.save_project(updated)
    assert len(store.history()) == 1
    store.save_project(store.history()[0]["previous"], "Smoke restore")
    assert store.project["goal"] == ""
    window.refresh_project()
    window.render_bugs()
    window.render_activity()
    window.show_page("Dashboard")
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    output = ROOT / "docs" / "dashboard-preview.png"
    assert window.grab().save(str(output))
    window.close()
    app.processEvents()
    print("UI smoke passed: startup, scan, all six pages, settings revision/restore, local bug report; screenshot:", output)
