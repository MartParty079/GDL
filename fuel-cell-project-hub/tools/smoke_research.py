"""Offscreen personal-profile startup validation. Does not launch external apps."""
import os
import sys
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from app.services.storage import Store, ROOT
from app.ui.window import HubWindow

started = time.monotonic()
app = QApplication([])
with patch('app.ui.window.QTimer.singleShot'):
    window = HubWindow(Store())
assert window.storage_settings.catalog is not None
files = window.files_panel
expected = window.storage_settings.catalog.summary()
assert len(files.rows) == expected['current'], 'Current filter disagrees with the catalog'
window.show_research_files('legacy')
assert len(files.rows) == expected['legacy'], 'Legacy filter disagrees with the catalog'
assert files.table.rowCount() == min(200, expected['legacy'])
assert all(r.get('dataset_status') == 'old_test_data' for r in files.rows)
print('Duplicate classifications:', dict(Counter(r['duplicate_status'] or 'No warning' for r in files.items)), flush=True)
window.show_research_files('')
assert len(files.rows) == expected['current'] + expected['legacy']
for page in ('Dashboard', 'Project', 'Settings', 'Software', 'Activity', 'Bugs'):
    window.show_page(page)
    app.processEvents()
window.resize(1024, 700)
window.show()
window.open_settings(1)
app.processEvents()
folder = ROOT / '.test-state/research-smoke'
folder.mkdir(parents=True, exist_ok=True)
assert window.grab().save(str(folder / 'storage.png'))
window.show_page('Dashboard')
app.processEvents()
assert window.grab().save(str(folder / 'dashboard.png'))
window.show_research_files('legacy')
app.processEvents()
assert window.grab().save(str(folder / 'legacy-files.png'))
window.close()
window.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
app.processEvents()
print(f'Personal research UI smoke passed in {time.monotonic() - started:.1f}s; no external applications launched.')
