"""Acceptance flow + screenshots using isolated temporary project data."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QCoreApplication, QEvent
from app.services.storage import ROOT
from test_storage_ui import StorageUITests

StorageUITests.setUpClass()
case = StorageUITests("test_setup_wizard_and_acceptance_search_workflow")
case.setUp()
try:
    case.test_setup_wizard_and_acceptance_search_workflow()
    window = case.window
    window.show_page("Settings")
    window.settings_tabs.setCurrentIndex(1)
    case.app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    case.app.processEvents()
    assert window.grab().save(str(ROOT / "docs/storage-preview.png"))
    window.show_page("Project")
    window.project_tabs.setCurrentIndex(1)
    case.app.processEvents()
    assert window.grab().save(str(ROOT / "docs/files-preview.png"))
    print("Storage UI smoke passed: wizard, marker, local root, missing folders, background indexing, S-001 search, Video filter, open actions, portable relative path.")
finally:
    case.tearDown()
