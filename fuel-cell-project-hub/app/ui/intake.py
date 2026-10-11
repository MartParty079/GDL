"""Native batch chooser/drop target with previews and recoverable per-file errors."""
import os
import threading
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView)
from app.services.intake import Intake
from app.services.organization import CATEGORIES
from app.ui.organization import RecordEditor


class IntakeDialog(QDialog):
    def __init__(self, panel, service, workspace=False):
        super().__init__(panel)
        self.panel, self.service = panel, service
        self.queue = Intake(service); self.cancelled = threading.Event(); self.running = False
        self.setWindowTitle('Upload Files · Preview before applying'); self.resize(1080, 690)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        heading = QLabel('Upload Files'); heading.setProperty('kind', 'heading'); layout.addWidget(heading)
        hint = QLabel('Drop files or folders here. Sources stay unchanged. Preview names are provisional; Admin confirms permanent IDs and final filenames. Select a row to adjust links, subtype or description.')
        hint.setWordWrap(True); layout.addWidget(hint)
        from app.ui.flow_layout import FlowLayout
        row = FlowLayout(); layout.addLayout(row)
        self.destination = QComboBox()
        for name in CATEGORIES: self.destination.addItem(name, name)
        self.destination.addItem('Personal Workspace (shared storage)', 'workspace')
        if workspace: self.destination.setCurrentIndex(4)
        row.addWidget(QLabel('Destination for added files')); row.addWidget(self.destination)
        for text, action in (('Choose Files', self.choose), ('Choose Folder', self.folder), ('Edit Selected Context', self.edit)):
            button = QPushButton(text); button.clicked.connect(action); row.addWidget(button)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(('Original filename', 'Proposed filename', 'Destination / links', 'Creator / uploader', 'Status / feedback'))
        from app.ui.workspace_components import prepare_table
        prepare_table(self.table, 'Upload queue; select to inspect complete proposed filename and destination')
        self.destination.setAccessibleName('Destination for added files')
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); layout.addWidget(self.table, 1)
        from PySide6.QtWidgets import QTextBrowser
        self.preview_text = QTextBrowser(); self.preview_text.setMaximumHeight(115); layout.addWidget(self.preview_text)
        self.table.itemSelectionChanged.connect(self.full_preview)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        actions = FlowLayout(); layout.addLayout(actions)
        self.apply_button = QPushButton('Apply / Retry Remaining'); self.apply_button.clicked.connect(self.apply); actions.addWidget(self.apply_button)
        self.cancel_button = QPushButton('Cancel Remaining'); self.cancel_button.clicked.connect(self.cancel); actions.addWidget(self.cancel_button)
        for text, action in (('Open Selected File', self.open_file), ('Open Destination Folder', self.open_folder), ('View Linked Record', self.link), ('Close', self.reject)):
            button = QPushButton(text); button.clicked.connect(action); actions.addWidget(button)
        self.reload()

    def defaults(self):
        choice = self.destination.currentData()
        values = {'workspace_owner_id': self.service.actor['user_id']} if choice == 'workspace' else {'destination_category': choice}
        selected = self.panel.selected()
        if selected and selected['kind'] in ('experiment', 'sample', 'procedure', 'research', 'design', 'meeting', 'deliverable'):
            kind = selected['kind']; values['sample_uuids' if kind == 'sample' else kind + '_uuid'] = [selected['uuid']] if kind == 'sample' else selected['uuid']
            if kind == 'experiment':
                for key in ('sample_uuids', 'procedure_uuid', 'procedure_revision'):
                    if selected['fields'].get(key): values[key] = selected['fields'][key]
            if kind == 'procedure': values['procedure_revision'] = selected['revision']
        return values

    def add(self, paths):
        if self.running: return
        files = []
        for value in paths:
            path = Path(value)
            if path.is_dir():
                for base, dirs, names in os.walk(path, followlinks=False):
                    from app.services.project_storage import redirects
                    dirs[:] = [d for d in dirs if not redirects((Path(base) / d).lstat())]
                    files.extend(Path(base) / name for name in names)
                    if len(files) > 5000:
                        QMessageBox.information(self, 'Choose a smaller batch', 'Import up to 5,000 files per batch. This folder was not added.'); return
            else: files.append(path)
        recordings = [p for p in files if p.suffix.lower() in ('.wav', '.mp3', '.m4a', '.mp4', '.mov', '.avi', '.webm')]
        if recordings:
            if QMessageBox.question(self, 'Permission to store recordings', 'Do participants permit these audio/video files to be stored in team-visible shared storage? Cancel if permission has not been obtained.') != QMessageBox.Yes: return
        defaults = self.defaults()
        if recordings: defaults['recording_consent'] = 'Yes'
        self.queue.add(files, defaults); self.reload()

    def choose(self): self.add(QFileDialog.getOpenFileNames(self, 'Choose resident files')[0])
    def folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose a batch folder; source files are preserved')
        if path: self.add([path])
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.running: event.acceptProposedAction()
    def dropEvent(self, event): self.add([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
    def selected(self):
        index = self.table.currentRow()
        return self.queue.rows[index] if 0 <= index < len(self.queue.rows) else None
    def edit(self):
        row = self.selected()
        if not row or self.running or row['status'] == 'Queued': return
        editor = RecordEditor(self.service, 'file', parent=self, defaults=row['fields']); editor.title.setText(row['title'])
        if editor.exec():
            row['title'], row['fields'] = editor.title.text(), editor.values()
            row['status'] = 'Ready'; row['error'] = ''; self.queue.save(); self.reload()
    def full_preview(self):
        row = self.selected()
        if not row: return
        try:
            preview = self.queue.preview(row)
            self.preview_text.setPlainText('Original: ' + preview['old'] + '\nProposed: ' + preview['proposed']
                + '\nDestination: ' + preview['folder'] + '\nLinks: ' + (preview['links'] or 'None selected')
                + '\nCreator / uploader: ' + preview['creator'] + '\n' + preview['identity'])
        except ValueError as exc: self.preview_text.setPlainText(str(exc))
    def reload(self):
        selected = self.table.currentRow(); self.table.setRowCount(len(self.queue.rows))
        for i, row in enumerate(self.queue.rows):
            try:
                preview = self.queue.preview(row)
                values = (preview['old'], preview['proposed'], preview['folder'] + '\n' + preview['links'], preview['creator'], row['status'] + '\n' + row['error'])
            except ValueError as exc: values = (Path(row['source']).name, 'Preview unavailable', '', '', str(exc))
            for j, value in enumerate(values): self.table.setItem(i, j, QTableWidgetItem(value))
        self.table.resizeRowsToContents()
        if selected >= 0: self.table.selectRow(selected)
        complete = sum(row['status'] == 'Queued' for row in self.queue.rows)
        self.status.setText(f'{len(self.queue.rows)} files · {complete} queued for Admin publication. Errors remain available for correction and retry. Queued files appear after a validated snapshot is published.')
    def apply(self):
        if self.running: return
        self.cancelled.clear(); self.running = True; self.apply_button.setEnabled(False)
        self.status.setText('Copying verified files and queuing changes… Cancel stops before the next file. Current file copy finishes safely.')
        def finish(result):
            self.running = False; self.apply_button.setEnabled(True); self.reload(); self.panel.reload()
        self.panel.window.work(lambda: self.queue.apply(self.cancelled.is_set), finish, lambda _: finish(None))
    def cancel(self):
        if self.running: self.cancelled.set(); self.status.setText('Stopping safely after the current file…'); return
        for row in self.queue.rows:
            if row['status'] != 'Queued': row['status'] = 'Cancelled'
        self.queue.save(); self.reload()
    def reject(self):
        if self.running: self.cancelled.set(); return
        super().reject()
    def registered(self):
        row = self.selected()
        return self.service.state['records'].get(row.get('record_uuid')) if row else None
    def open_file(self):
        row = self.registered()
        if row: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.safe(row['relative_path']))))
        else: QMessageBox.information(self, 'Pending publication', 'Admin must publish the upload before the canonical file can be opened.')
    def open_folder(self):
        row = self.registered()
        if row: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.safe(row['relative_path']).parent)))
    def link(self):
        row = self.selected()
        if row:
            key = next((row['fields'].get(k) for k in ('experiment_uuid', 'design_uuid', 'research_uuid', 'meeting_uuid') if row['fields'].get(k)), None)
            if not key and row['fields'].get('sample_uuids'): key = row['fields']['sample_uuids'][0]
            if key and hasattr(self.panel.window, 'home_panel'): self.panel.window.home_panel.open_record(key)
