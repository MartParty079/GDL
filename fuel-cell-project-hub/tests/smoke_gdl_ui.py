"""GDL screens at normal/laptop size; launch and update tested without Fiji."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_gdl_ui import GDLUITests
from app.services.storage import ROOT
from PySide6.QtCore import QCoreApplication, QEvent

GDLUITests.setUpClass()
case = GDLUITests()
case.setUp()
try:
    window = case.window
    window.banner.set_message("Local GDL integration fixture · external launches are simulated.", "info")
    window.open_workspace("Analysis")
    window.gdl_panel.validate()
    case.drain()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    case.app.processEvents()
    assert "ready" in window.gdl_panel.dependencies.text()
    assert window.grab().save(str(ROOT / "docs/gdl-analysis-preview.png"))
    window.resize(1024, 700)
    case.app.processEvents()
    assert window.grab().save(str(ROOT / "docs/gdl-laptop-preview.png"))
    window.resize(1280, 850)
    window.open_analysis_settings()
    case.drain()
    assert window.grab().save(str(ROOT / "docs/gdl-settings-preview.png"))
    window.show_page("Dashboard")
    window.resize(1024, 700)
    case.app.processEvents()
    assert window.width() == 1024
    case.test_full_adapter_flow_from_button_without_real_fiji()
    print("GDL smoke passed: editable settings, dependency validation, Analysis navigation, laptop layout, simulated launch/status/stop.")
finally:
    case.tearDown()
