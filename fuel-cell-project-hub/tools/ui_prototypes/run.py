"""Native Home design picker. Isolated fixtures only; never a shipping entrypoint.

Run: .venv/Scripts/python.exe -m tools.ui_prototypes.run --skills-archive <zip>
Use --capture <ignored QA directory> for repeatable screenshots and smoke evidence.
"""
import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from unittest.mock import patch
if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from PySide6.QtCore import QObject, Slot, QUrl, Qt, QEvent, QCoreApplication, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QApplication, QLabel, QHBoxLayout, QLineEdit, QTextEdit,
    QComboBox, QAbstractSpinBox, QPushButton, QMessageBox, QFileDialog)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
from PySide6.QtWebChannel import QWebChannel
from app.ui.window import HubWindow
from app.ui.local_accounts import attach_account_ui
from app.services.storage import write_json
from .fixture import create_fixture
from .picker import build_picker, NAMES
from .quiet import QuietWorkspace
from .sidebar import StructuredSidebar
from .compact import CommandCenter

CLASSES = (QuietWorkspace, StructuredSidebar, CommandCenter)


class LocalOnly(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, request):
        if request.requestUrl().scheme() not in ('file', 'qrc', 'data', 'about'):
            request.block(True)


class PickerPage(QWebEnginePage):
    def __init__(self, profile, parent):
        super().__init__(profile, parent); self.errors = []

    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(message)


class Bridge(QObject):
    def __init__(self, window, output):
        super().__init__(window); self.window = window; self.output = output; self.current = None; self.serial = 0

    @Slot(int)
    def choose(self, index):
        if not 0 <= index < len(CLASSES): return
        old = self.window.home_panel; at = self.window.tabs.indexOf(old)
        self.window.tabs.removeTab(at); old.hide(); old.deleteLater()
        self.window.home_panel = CLASSES[index](self.window)
        self.window.tabs.insertTab(at, self.window.home_panel, 'Home')
        self.window.tabs.setCurrentWidget(self.window.home_panel)
        self.current = index
        self.serial += 1
        write_json(self.output / 'picker-state.json', {'variant': index + 1, 'name': NAMES[index]})


class Keys(QObject):
    def __init__(self, view): super().__init__(view); self.view = view

    def eventFilter(self, target, event):
        if event.type() != QEvent.KeyPress or event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier): return False
        focus = QApplication.focusWidget()
        inputs = (QLineEdit, QTextEdit, QComboBox, QAbstractSpinBox)
        if isinstance(target, inputs) or isinstance(focus, inputs): return False
        if focus and (focus is self.view or self.view.isAncestorOf(focus)): return False
        key = event.key()
        if Qt.Key_1 <= key <= Qt.Key_3: code = f'setActive({key - Qt.Key_1})'
        elif key == Qt.Key_Right: code = 'setActive((current + 1) % variants.length)'
        elif key == Qt.Key_Left: code = 'setActive((current - 1 + variants.length) % variants.length)'
        elif key == Qt.Key_R: code = 'mount(current)'
        else: return False
        self.view.page().runJavaScript(code); return True


def pump(app, predicate=lambda: True, seconds=20, settle=.12):
    deadline = time.monotonic() + seconds
    while True:
        app.processEvents(); time.sleep(.01)
        if predicate():
            until = time.monotonic() + settle
            while time.monotonic() < until: app.processEvents(); time.sleep(.01)
            return
        if time.monotonic() > deadline: raise TimeoutError('Prototype did not become ready.')


def prepare(app, archive, output, role):
    store, accounts, records = create_fixture(output, role)
    with patch('app.ui.window.QTimer.singleShot'): window = HubWindow(store)
    attach_account_ui(window, accounts, window.close)
    window.session_presence.stop(); window.account_timer.stop()
    window.setWindowTitle('Capstone Hub — Home Design Picker — DEVELOPMENT ONLY')
    window.setMinimumSize(900, 650); window.tabs.tabBar().hide()
    outer = window.centralWidget().layout(); outer.setContentsMargins(12, 8, 12, 4); outer.setSpacing(4)
    old_top = outer.takeAt(0).layout()
    preserved = window.findChild(QPushButton, 'current-user')
    def hide_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().hide()
            elif item.layout(): hide_layout(item.layout())
    hide_layout(old_top)
    top = QHBoxLayout(); top.addWidget(QLabel('CAPSTONE HUB  /  HOME STUDIES'))
    top.addStretch(); top.addWidget(preserved); preserved.show()
    home = QPushButton('Home'); home.clicked.connect(lambda: (window.home_panel.reload(), window.tabs.setCurrentWidget(window.home_panel)))
    top.addWidget(home); outer.insertLayout(0, top)
    window.banner.setText('DEVELOPMENT ONLY · Representative local fixture · Select a layout before integration')
    window.launch_item = lambda item: QMessageBox.information(window, 'Prototype launcher check',
        item['name'] + ': external app launches are disabled in the isolated Home picker. Configure paths in Software.')
    window.picker = QWebEngineView(window); window.picker.setFixedHeight(82)
    window.picker_profile = QWebEngineProfile(window)  # unnamed => memory-only/off-the-record
    window.interceptor = LocalOnly(window.picker_profile); window.picker_profile.setUrlRequestInterceptor(window.interceptor)
    page = PickerPage(window.picker_profile, window.picker); page.setBackgroundColor(QColor('#F5F6F8'))
    window.picker.setPage(page)
    channel = QWebChannel(page); bridge = Bridge(window, output); channel.registerObject('pickerBridge', bridge); page.setWebChannel(channel)
    window.picker_bridge = bridge; window.picker_channel = channel
    html = build_picker(archive, output / 'picker.html')
    url = QUrl.fromLocalFile(str(html.resolve())); url.setQuery('v=1'); window.picker.load(url)
    outer.addWidget(window.picker)
    window.picker_keys = Keys(window.picker); app.installEventFilter(window.picker_keys)
    window.resize(1366, 768); window.show()
    pump(app, lambda: bridge.current is not None)
    return window, accounts, records


def capture(app, window, output, records):
    from PySide6.QtTest import QTest
    (output / 'evidence.json').unlink(missing_ok=True)
    evidence = dict(fixture_only=True, production_code_changed=False, records=records, variants=[], console_errors=[],
                    environment=platform.platform(), python=platform.python_version())
    for index, name in enumerate(NAMES):
        serial = window.picker_bridge.serial; start = time.perf_counter()
        window.picker.page().runJavaScript(f'setActive({index})')
        pump(app, lambda: window.picker_bridge.current == index and window.picker_bridge.serial > serial)
        home = window.home_panel
        assert len(home.category_buttons) == 4
        assert not hasattr(window, 'admin_workspace') or window.account_service.admin_unlocked
        for width, height in ((1366, 768), (1920, 1080)):
            window.resize(width, height); pump(app, settle=.25)
            filename = name.lower().replace(' ', '-') + f'-{width}.png'
            window.grab().save(str(output / filename))
            assert home.horizontalScrollBar().maximum() == 0
        for category, control in zip(('Experimental', 'Research', 'Meetings & Goals', 'Design & Prototyping'), home.category_buttons):
            control.click(); assert window.organization_panel.category.currentText() == category
            window.tabs.setCurrentWidget(home)
        opened = []
        def dismiss():
            dialog = QApplication.activeModalWidget()
            if dialog: opened.append(dialog.windowTitle()); dialog.reject()
        for kind in ('experiment', 'sample', 'deliverable'):
            QTimer.singleShot(50, dismiss); home.create(kind)
        assert len(opened) == 3
        QTimer.singleShot(50, dismiss); home.panel.upload()
        assert len(opened) == 4
        home.file_type.setText('.tif'); home.activity_rows(); home.clear_filters()
        if hasattr(home, 'work_table'):
            home.work_filter.setText('scale calibration')
            assert sum(not home.work_table.isRowHidden(i) for i in range(home.work_table.rowCount())) == 1
            home.work_filter.clear()
        evidence['variants'].append(dict(name=name, four_categories=True, category_routes=True,
             real_forms_opened=opened, horizontal_scroll=False, sizes=['1366x768', '1920x1080'],
             capture_and_smoke_seconds=round(time.perf_counter() - start, 3)))
    # Native keyboard forwarding obeys the same input/modifier exclusions as HTML.
    window.home_panel.setFocus(); QTest.keyClick(window.home_panel, Qt.Key_1)
    pump(app, lambda: window.picker_bridge.current == 0)
    home = window.home_panel; home.after.setFocus(); QTest.keyClicks(home.after, '2')
    assert home.after.text() == '2' and window.picker_bridge.current == 0, (home.after.text(), window.picker_bridge.current)
    home.after.clear(); home.setFocus(); QTest.keyClick(home, Qt.Key_Right)
    pump(app, lambda: window.picker_bridge.current == 1)
    result = []
    window.picker.page().runJavaScript("JSON.stringify({active:document.querySelectorAll('[data-active]').length, current:document.querySelectorAll('[aria-current=true]').length, query:location.search})", result.append)
    pump(app, lambda: bool(result))
    assert json.loads(result[0]) == dict(active=1, current=1, query='?v=2'), result
    serial = window.picker_bridge.serial; window.picker.reload()
    pump(app, lambda: window.picker_bridge.serial > serial)
    assert window.picker_bridge.current == 1
    evidence.update(keyboard_picker=True, typing_does_not_switch=True, selection_persists_on_reload=True,
                    single_aria_current=True, command_filter=True)
    evidence['console_errors'] = window.picker.page().errors
    assert not evidence['console_errors'], evidence['console_errors']
    write_json(output / 'evidence.json', evidence)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-archive', type=Path, default=Path.home() / 'Downloads/skills-main.zip')
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--role', choices=('member', 'admin'), default='member')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = (args.capture or root / '.test-state/ui-home-picker').resolve()
    if not output.is_relative_to((root / '.test-state').resolve()):
        parser.error('Prototype state and output must remain inside the ignored .test-state directory.')
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window, accounts, records = prepare(app, args.skills_archive, output, args.role)
    original_save = QFileDialog.getSaveFileName
    def safe_save(*a, **kw):
        result = original_save(*a, **kw)
        if result[0] and not Path(result[0]).resolve().is_relative_to(output):
            QMessageBox.information(window, 'Prototype output', 'Save prototype exports inside its isolated QA directory.'); return '', ''
        return result
    try:
        with patch.object(QFileDialog, 'getSaveFileName', safe_save):
            if args.capture: capture(app, window, output, records)
            else: app.exec()
    finally:
        pump(app, lambda: not (window.meetings_panel.busy() or window.weekly_panel.tasks.busy() or window.workers))
        app.removeEventFilter(window.picker_keys)
        window.signing_out = True; window.close()
        window.picker.setPage(QWebEnginePage(window.picker))
        accounts.close(); window.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.shutdown()


if __name__ == '__main__': main()
