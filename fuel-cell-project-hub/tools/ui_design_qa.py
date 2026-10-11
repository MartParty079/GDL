"""Development-only stress picker for the actual native application.

All writes stay in a new ignored fixture profile. No production snapshot is read.
Run with --capture for evidence, or without it to use the live dataset toggle.
"""
import argparse
import copy
import json
import platform
import sys
import time
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import Qt, QEvent, QCoreApplication
from PySide6.QtWidgets import QApplication, QToolBar, QComboBox, QLabel, QPushButton
from app.edition import CHANNEL, APP_NAME
from app.ui.window import HubWindow
from app.ui.local_accounts import attach_account_ui
from app.ui.intake import IntakeDialog
from tools.ui_design_fixture import create_fixture

STATES = ('Demo data', 'Worst case', 'Empty', 'One', '1,000 rows', 'Offline snapshot', 'Old metadata')
LONG_TITLE = ('Optical calibration and repeatability review — carbon paper surface imaging, '
              'fixture alignment, uncertainty budget and cross-laboratory comparison; '
              'revisions after advisor review — Aleksandra Wiśniewska-Kowalczyk / 李明 / µm')
LONG_FILE = '2026-10-11_IMG_E0042_S0017_surface-imaging_repeatability_reference-calibration_illumination-45deg_overlay-reviewed_003'


class StressPicker:
    def __init__(self, base):
        self.store, self.accounts, self.keys = create_fixture(base)
        with patch('app.ui.window.QTimer.singleShot'):
            self.window = HubWindow(self.store)
        attach_account_ui(self.window, self.accounts, lambda: None)
        self.window.setWindowTitle(APP_NAME + ' — DEVELOPMENT QA FIXTURE')
        self.window.account_timer.stop(); self.window.session_presence.stop()
        self.panel = self.window.organization_panel; self.service = self.panel.service
        self.baseline = copy.deepcopy(self.service.state)
        self.profile = copy.deepcopy(self.accounts.profile)
        self.status = self.service.status
        self.toolbar = QToolBar('Development QA dataset toggle', self.window)
        self.toolbar.setMovable(False); self.toolbar.addWidget(QLabel('DEV FIXTURE ONLY  '))
        self.toggle = QComboBox(); self.toggle.addItems(STATES)
        self.toggle.setAccessibleName('Stress test dataset'); self.toolbar.addWidget(self.toggle)
        self.window.addToolBar(Qt.BottomToolBarArea, self.toolbar)
        self.toggle.currentTextChanged.connect(self.select)
        self.results = []

    def select(self, name):
        start = time.perf_counter()
        self.service.state = copy.deepcopy(self.baseline)
        self.accounts.profile.update(self.profile)
        self.service.status = self.status
        records = self.service.state['records']
        if name in ('Worst case', 'Old metadata'):
            for kind in ('meeting', 'goal', 'procedure', 'sample'):
                row = next(r for r in records.values() if r['kind'] == kind)
                row['title'] = LONG_TITLE if kind != 'sample' else 'Holy GDL — 1344 Pascal / μCT reference / 李明'
            goal = records[self.keys['goal']]
            goal['fields']['next_step'] = LONG_TITLE
            goal['fields']['output'] = 'Compare 0.190 mm reference and 45° illumination; evidence requires review.'
            records[self.keys['meeting']]['fields']['agenda'] = LONG_TITLE + '\n' + LONG_TITLE
            self.accounts.profile['display_name'] = 'Aleksandra Wiśniewska-Kowalczyk — Research Documentation Coordinator'
            if name == 'Old metadata':
                records[self.keys['goal']]['fields'].pop('due_date', None)
                records[self.keys['period']]['fields'].pop('due_at', None)
                records[self.keys['experiment']]['fields'].pop('procedure_revision', None)
        elif name == 'Empty': records.clear()
        elif name == 'One':
            one = records[self.keys['task']]; records.clear(); records[one['uuid']] = one
        elif name == '1,000 rows':
            sample = copy.deepcopy(records[self.keys['sample']]); records.clear()
            for n in range(1000):
                row = copy.deepcopy(sample); row.update(uuid=str(uuid4()), id=f'S{n+1:04}', title=f'Carbon paper repeatability coupon {n+1:04} — batch optical reference')
                records[row['uuid']] = row
        elif name == 'Offline snapshot':
            self.service.status = 'Offline/possibly stale · last-known-good snapshot · local changes preserved'
        self.window.findChild(QPushButton, 'current-user').setText(self.accounts.profile['display_name'] + ' · MEMBER')
        error = None
        try:
            self.panel.reload(); self.window.home_panel.reload()
        except Exception as exc: error = type(exc).__name__ + ': ' + str(exc)
        QApplication.processEvents()
        self.results.append(dict(state=name, reload_ms=round((time.perf_counter()-start)*1000, 1), error=error))
        return error

    def settle(self):
        end = time.monotonic() + 30
        while self.window.workers or self.window.weekly_panel.tasks.busy() or self.window.meetings_panel.busy():
            QApplication.processEvents(); time.sleep(.01)
            if time.monotonic() > end: raise RuntimeError('Fixture workers did not settle')

    def capture(self, output):
        output.mkdir(parents=True, exist_ok=True)
        screenshots = []
        def shot(name):
            QApplication.processEvents(); path = output / (name + '.png')
            self.window.grab().save(str(path)); screenshots.append(path.name)
        for state in STATES:
            self.toggle.setCurrentText(state); self.select(state)
            for width, height in ((1366, 768), (1920, 1080)):
                self.window.resize(width, height); self.window.workspace_rail.go_home()
                shot(state.replace(' ', '-').replace(',', '') + f'-{width}')
            if state == 'Offline snapshot':
                shot('offline-health-visible')
            if state == '1,000 rows':
                self.window.home_panel.navigate('Experimental'); shot('1000-records')
        self.toggle.setCurrentText('Worst case'); self.select('Worst case')
        for appearance, scale in (('dark', 100), ('light', 200)):
            self.store.local.update(appearance=appearance, text_scale=scale)
            self.window.apply_theme(); self.window.home_panel.reload()
            self.window.resize(1366, 768); self.window.workspace_rail.go_home()
            shot(f'worst-{appearance}-{scale}')
            self.window.home_panel.navigate('Experimental'); shot(f'records-{appearance}-{scale}')
            if scale == 200:
                self.panel.controls_scroll.verticalScrollBar().setValue(self.panel.controls_scroll.verticalScrollBar().maximum())
                shot('records-light-200-actions')
        # Component container test independent of the desktop's 1024px minimum.
        self.store.local.update(appearance='light', text_scale=100); self.window.apply_theme()
        from app.ui.workspace_components import ContextBrowser
        context = ContextBrowser(); context.resize(320, 200); context.setPlainText(LONG_TITLE); context.show()
        QApplication.processEvents(); context.grab().save(str(output / 'context-320.png')); context.close(); context.deleteLater()
        # Resident placeholder bytes exercise preview only, never open external software.
        intake = IntakeDialog(self.panel, self.service)
        paths = []
        for suffix in ('.tif', '.png', '.pdf', '.docx', '.sldprt', '.stl', '.3mf'):
            file = self.store.local_dir / (LONG_FILE + suffix); file.write_bytes(b'Development preview fixture'); paths.append(file)
        intake.queue.add(paths); intake.reload(); intake.show(); intake.table.selectRow(0)
        QApplication.processEvents(); intake.grab().save(str(output / 'intake-long-files.png'))
        intake.close(); intake.deleteLater()
        self.settle()
        (output / 'evidence.json').write_text(json.dumps(dict(fixture_only=True, channel=CHANNEL,
            environment=dict(os=platform.platform(), python=platform.python_version()), results=self.results,
            screenshots=screenshots, installer_tested=False), indent=2), encoding='utf-8')
        self.accounts.close(); self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    if CHANNEL == 'stable' or getattr(sys, 'frozen', False): raise SystemExit('Development source QA only')
    base = ROOT / '.test-state/ui-sidebar-stress'; base.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    picker = StressPicker(base); picker.window.show(); picker.settle()
    if args.capture: picker.capture(base); app.shutdown()
    else:
        try: app.exec()
        finally: picker.accounts.close()

if __name__ == '__main__': main()
