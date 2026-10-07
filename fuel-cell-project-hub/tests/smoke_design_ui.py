"""Render loading, empty, error, settings and minimum laptop states."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_design_ux import DesignUXTests
from app.services.storage import ROOT
from PySide6.QtCore import QCoreApplication, QEvent

DesignUXTests.setUpClass()
case = DesignUXTests()
case.setUp()
window = case.window

def snapshot(name):
    case.app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    case.app.processEvents()
    assert window.grab().save(str(ROOT / "docs" / name))

try:
    window.banner.set_message("Your local workspace is ready. Connect shared storage when you're ready.", "info")
    window.scanning = True
    window.render_dashboard()
    window.show_page("Dashboard")
    snapshot("dashboard-loading-preview.png")
    window.scanning = False
    window.results = {item["id"]: {"status": "Missing", "path": "", "source": ""} for item in case.store.manifest}
    window.render_dashboard()
    window.resize(1024, 700)
    snapshot("dashboard-laptop-preview.png")
    window.resize(1280, 850)
    window.open_workspace("Files & Data")
    snapshot("files-empty-preview.png")
    window.guard(lambda: (_ for _ in ()).throw(PermissionError("[WinError 5] Access is denied: C:/private/file")))
    assert window.global_error.details.isHidden()
    assert "WinError" not in window.global_error.message.text()
    snapshot("error-preview.png")
    window.global_error.hide()
    window.open_settings(0)
    snapshot("settings-preview.png")
    print("Design state smoke test passed.")
finally:
    window.scanning = False
    case.tearDown()
