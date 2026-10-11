"""Four organization categories with guided metadata and proposal review."""
import json
import threading
from html import escape
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QTextEdit, QDialog, QFormLayout, QDialogButtonBox, QScrollArea, QListWidget, QLayout,
    QAbstractItemView, QMessageBox, QFileDialog, QInputDialog)
from app.services.organization import Organization, CATEGORIES, LIMIT, MEETING_TEMPLATES, FOLDERS
from app.ui.flow_layout import FlowLayout

FIELDS = {
    'sample': ('manufacturer', 'material', 'nominal_thickness', 'units', 'resin_binder_content', 'new_used_state', 'history', 'aliases'),
    'experiment': ('sample_uuids', 'procedure_uuid', 'procedure_revision', 'setup', 'operator_id',
                   'apparatus_settings', 'pressure_compression', 'units', 'run_count', 'results', 'notes'),
    'procedure': ('equipment', 'approval_status', 'instructions', 'change_summary'),
    'research': ('research_section', 'authors', 'publication_year', 'publication_date', 'doi_url',
                 'standard_designation', 'standard_edition', 'access_license_provenance', 'themes', 'relevance',
                 'dimensionality', 'metric', 'definition', 'method', 'sample_basis', 'units',
                 'comparison_reason', 'reviewer_id', 'follow_up', 'aliases'),
    'design': ('design_section', 'material', 'dimensions', 'units', 'tolerance', 'cad_source_uuid',
               'manufacturing_process', 'export_file_uuids', 'prototype_status', 'feedback'),
    'meeting': ('created_at', 'meeting_time', 'location', 'facilitator_id', 'note_taker_id', 'attendees',
                'stage', 'agenda', 'minutes', 'summary', 'decisions', 'blockers', 'next_meeting_date',
                'recording_path', 'transcript_path', 'summary_reviewed_by_id', 'summary_approved'),
    'task': ('owner_id', 'supporting_members', 'due_date', 'acceptance', 'status', 'meeting_uuid',
             'milestone', 'semester', 'deliverable', 'linked_file_uuids', 'decision_reference'),
    'role': ('member_id', 'backup_id', 'notes'),
    'file': ('file_state', 'created_at', 'sequence', 'experiment_uuid', 'sample_uuids', 'procedure_uuid', 'meeting_uuid', 'design_uuid', 'research_uuid',
             'procedure_revision', 'parent_file_uuid', 'processing_run_id', 'document_type',
             'microscope_scale_calibration', 'magnification', 'illumination', 'exposure', 'sample_side_region',
             'operator_id', 'apparatus_settings', 'pressure_compression', 'units', 'run_count', 'notes'),
}
LONG = {'history', 'instructions', 'setup', 'results', 'notes', 'comparison_reason', 'feedback',
        'agenda', 'minutes', 'summary', 'decisions', 'blockers', 'acceptance', 'follow_up'}
PEOPLE = {'owner_id', 'member_id', 'backup_id', 'facilitator_id', 'note_taker_id', 'reviewer_id',
          'operator_id', 'summary_reviewed_by_id'}
LINKS = {'procedure_uuid': 'procedure', 'experiment_uuid': 'experiment', 'meeting_uuid': 'meeting',
         'parent_file_uuid': 'file', 'cad_source_uuid': 'file', 'design_uuid': 'design', 'research_uuid': 'research'}
CHOICES = {'file_state': ('raw', 'poremap', 'overlay', 'outline', 'derived', 'reference'),
    'stage': ('agenda', 'minutes', 'summary'), 'status': ('planned', 'active', 'blocked', 'done'),
    'dimensionality': ('Unverified', '2D', '3D'), 'new_used_state': ('Unverified', 'New', 'Used'),
    'semester': ('Fall 2026', 'Spring 2027 — future planning only'),
    'summary_approved': ('No', 'Yes')}


class RecordEditor(QDialog):
    def __init__(self, service, kind, row=None, parent=None):
        super().__init__(parent)
        self.service, self.kind, self.row = service, kind, row
        self.setWindowTitle(('Edit ' if row else 'New ') + kind.title() + ' · Pending Admin publication')
        self.resize(720, 700)
        layout = QVBoxLayout(self)
        hint = QLabel('Creator comes from your selected profile. IDs and date-first filenames are allocated when Admin publishes. Changes require a reason.')
        hint.setWordWrap(True); layout.addWidget(hint)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        page = QWidget(); form = QFormLayout(page); form.setSizeConstraint(QLayout.SetMinimumSize); scroll.setWidget(page); layout.addWidget(scroll)
        self.title = QLineEdit((row or {}).get('title', '')); form.addRow('Short description', self.title)
        if kind == 'role': self.title.setReadOnly(True)
        self.fields = {}
        values = (row or {}).get('fields', {})
        for key in FIELDS[kind]:
            value = (row['created_at'] if row and key == 'created_at' else values.get(key, MEETING_TEMPLATES.get(key, '') if kind == 'meeting' else ''))
            if key in PEOPLE or key in LINKS or key in CHOICES or key.endswith('_section'):
                widget = QComboBox()
                if key in PEOPLE:
                    widget.addItem('Unassigned', '')
                    for user in service.accounts.users():
                        widget.addItem(user['display_name'], user['id'])
                elif key in LINKS:
                    widget.addItem('None', '')
                    for linked in service.rows(kind=LINKS[key]):
                        widget.addItem(linked['id'] + ' · ' + linked['title'], linked['uuid'])
                else:
                    choices = CHOICES.get(key) or tuple(p.split('/')[1] for p in FOLDERS if p.startswith('02_Research' if key == 'research_section' else '04_Design'))
                    for item in choices:
                        widget.addItem(item, item)
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif key in ('sample_uuids', 'attendees', 'supporting_members'):
                widget = QListWidget(); widget.setSelectionMode(QAbstractItemView.MultiSelection); widget.setMaximumHeight(110)
                candidates = service.accounts.users() if key != 'sample_uuids' else service.rows(kind='sample')
                for candidate in candidates:
                    label = candidate.get('display_name') or candidate['id'] + ' · ' + candidate['title']
                    widget.addItem(label); item = widget.item(widget.count() - 1)
                    item.setData(Qt.UserRole, candidate['id'] if key != 'sample_uuids' else candidate['uuid'])
                    item.setSelected(item.data(Qt.UserRole) in value)
            elif key in LONG:
                widget = QTextEdit(); widget.setPlainText(str(value)); widget.setFixedHeight(125)
                widget.setStyleSheet('QTextEdit { min-height:105px; max-height:105px; }')
            else:
                widget = QLineEdit(', '.join(value) if isinstance(value, list) else str(value))
                if key == 'created_at': widget.setPlaceholderText('YYYY-MM-DD (source creation/capture date; blank = today)')
                if key == 'due_date': widget.setPlaceholderText('YYYY-MM-DD')
                if key.endswith('_uuids'): widget.setPlaceholderText('Comma-separated immutable file UUIDs from details')
            if row and key == 'created_at': widget.setEnabled(False)
            self.fields[key] = widget
            form.addRow(key.replace('_', ' ').title(), widget)
        self.reason = QLineEdit(); form.addRow('Reason for edit', self.reason)
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def values(self):
        values = dict((self.row or {}).get('fields', {}))
        for key, widget in self.fields.items():
            value = (widget.currentData() if isinstance(widget, QComboBox) else
                     [i.data(Qt.UserRole) for i in widget.selectedItems()] if isinstance(widget, QListWidget) else
                     widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text().strip())
            if key in ('aliases',) or key.endswith('_uuids') and not isinstance(value, list):
                value = [v.strip() for v in value.split(',') if v.strip()]
            if key in ('procedure_revision', 'sequence', 'run_count') and value:
                value = int(value)
            if value != '': values[key] = value
            else: values.pop(key, None)
        return values

    def validate(self):
        try:
            if not self.title.text().strip(): raise ValueError('Enter a short description.')
            if self.row and not self.reason.text().strip(): raise ValueError('Enter the reason for your correction.')
            self.service._validate_fields(self.kind, self.values(), self.service.state['records'])
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc))


class OrganizationPanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.service = Organization(window.store)
        self.cancel = threading.Event()
        self.working = False
        layout = QVBoxLayout(self)
        heading = QLabel('Project organization'); heading.setStyleSheet('font-size:24px;font-weight:600'); layout.addWidget(heading)
        subtitle = QLabel('Four research categories · permanent identities · traceable revisions · Admin-published shared index')
        subtitle.setWordWrap(True); layout.addWidget(subtitle)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.path = QLabel('Configured root: ' + str(self.service.root)); self.path.setWordWrap(True); layout.addWidget(self.path)
        nav = QHBoxLayout(); layout.addLayout(nav)
        self.category = QComboBox(); self.category.addItems(CATEGORIES); nav.addWidget(self.category)
        self.kind = QComboBox(); nav.addWidget(self.kind)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search IDs, aliases, names, contributors or provenance'); nav.addWidget(self.search, 1)
        self.actions = FlowLayout(); layout.addLayout(self.actions)
        for title, action in (('New record', self.new), ('Upload file', self.upload), ('Edit metadata', self.edit),
                              ('Open source', self.open), ('Refresh / submit pending', self.sync), ('Pending requests', self.pending),
                              ('Meeting export', self.export), ('Inspect audit', self.audit), ('Resubmit reviewed request', self.resubmit)):
            control = QPushButton(title); control.clicked.connect(action); self.actions.addWidget(control)
        admin = FlowLayout(); layout.addLayout(admin)
        for title, action in (('Preview / initialize', self.setup), ('Publish requests', self.publish),
                              ('Legacy dry run', self.inventory), ('Check missing paths', self.reconcile),
                              ('Restore snapshot', self.rollback)):
            control = QPushButton(title); control.clicked.connect(action); control.setVisible(self.service.accounts.admin_unlocked); admin.addWidget(control)
        self.cancel_button = QPushButton('Stop inventory safely'); self.cancel_button.clicked.connect(self.cancel.set)
        self.cancel_button.setVisible(False); admin.addWidget(self.cancel_button)
        split = QSplitter(); layout.addWidget(split, 1)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(('ID / type', 'Description', 'Revision / state', 'Creator', 'Owner / status'))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); split.addWidget(self.table)
        self.table.setColumnWidth(0, 145); self.table.setColumnWidth(2, 120); self.table.setColumnWidth(3, 145); self.table.setColumnWidth(4, 180)
        detail_page = QWidget(); detail_layout = QVBoxLayout(detail_page)
        self.image = QLabel(); self.image.setAlignment(Qt.AlignCenter); self.image.setMaximumHeight(250); self.image.hide(); detail_layout.addWidget(self.image)
        self.details = QTextEdit(); self.details.setReadOnly(True); detail_layout.addWidget(self.details, 1)
        split.addWidget(detail_page); split.setSizes([820, 360])
        self.table.itemSelectionChanged.connect(self.detail)
        self.category.currentTextChanged.connect(self.change_category)
        self.kind.currentIndexChanged.connect(self.reload); self.search.textChanged.connect(self.reload)
        notice = QLabel(LIMIT + ' Literature comparisons require a recorded reviewer rationale. Automatic transcription is not available; attach a verified transcript manually.')
        notice.setWordWrap(True); layout.addWidget(notice)
        self.change_category()

    def run(self, action, done=None):
        if self.working: return
        self.working = True
        for control in self.findChildren(QWidget):
            if isinstance(control, (QPushButton, QComboBox, QLineEdit)) and control is not self.cancel_button: control.setEnabled(False)
        def finish(result):
            self.working = False
            for control in self.findChildren(QWidget):
                if isinstance(control, (QPushButton, QComboBox, QLineEdit)): control.setEnabled(True)
            self.cancel_button.setVisible(False); self.reload()
            if done: done(result)
        def fail(message):
            finish(None); QMessageBox.information(self, 'Organization unavailable', 'Operation incomplete. Pending changes and original files were preserved.\n' + str(message))
        self.window.work(action, finish, fail)

    def attempt(self, action):
        try: return action()
        except (ValueError, OSError) as exc:
            QMessageBox.information(self, 'Project organization', str(exc) if isinstance(exc, ValueError) else 'Storage unavailable. Existing files and queued changes were preserved.')

    def change_category(self, *_):
        from app.services.organization import KINDS
        self.kind.blockSignals(True); self.kind.clear(); self.kind.addItem('All record types', '')
        for kind, (_, category) in KINDS.items():
            if category == self.category.currentText() or kind == 'file': self.kind.addItem(kind.title(), kind)
        self.kind.blockSignals(False); self.reload()

    def reload(self, *_):
        self.rows = self.service.rows(self.category.currentText(), self.kind.currentData(), self.search.text())
        self.table.setRowCount(len(self.rows))
        self.table.clearSelection(); self.table.setCurrentCell(-1, -1)
        people = {p['id']: p['display_name'] for p in self.service.accounts.registry['users']}
        for number, row in enumerate(self.rows):
            fields = row['fields']
            values = (row['id'] + ' · ' + row['kind'], row['title'], str(row['revision']) + ' · ' + fields.get('file_state', fields.get('stage', 'record')),
                      row['created_by_display_name'], people.get(fields.get('owner_id'), 'Unassigned') + ' · ' + fields.get('status', ''))
            for column, value in enumerate(values): self.table.setItem(number, column, QTableWidgetItem(value))
        self.status.setText(self.service.status)
        self.image.hide()
        self.details.setPlainText('Select a record to inspect metadata, immutable UUIDs and revision history.\n\nFall 2026 priorities: literature/standards, legacy catalog, baseline microscopy, equipment refurbishment, methods and fixture design. Spring 2027 testing remains future work.')

    def selected(self):
        index = self.table.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def detail(self):
        row = self.selected()
        if not row: return
        self.image.hide()
        if row['kind'] == 'file' and row.get('relative_path'):
            from app.services.project_storage import PLACEHOLDER_FLAGS
            source = self.service.safe(row['relative_path'])
            if source.is_file() and not getattr(source.stat(), 'st_file_attributes', 0) & PLACEHOLDER_FLAGS:
                reader = QImageReader(str(source))
                if reader.canRead():
                    reader.setScaledSize(reader.size().scaled(360, 240, Qt.KeepAspectRatio))
                    self.image.setPixmap(QPixmap.fromImage(reader.read())); self.image.show()
        linked = [r for r in self.service.rows() if row['uuid'] in json.dumps(r['fields'])]
        history = [r for r in self.service.state['audit'] if r.get('record_uuid') == row['uuid']]
        people = {p['id']: p['display_name'] for p in self.service.accounts.registry['users']}
        def display(value):
            if isinstance(value, list): return ', '.join(display(v) for v in value) or 'Unassigned'
            if isinstance(value, dict): return json.dumps(value, ensure_ascii=False)
            reference = self.service.state['records'].get(str(value))
            return reference['id'] + ' · ' + reference['title'] if reference else people.get(str(value), str(value))
        body = '<h2>' + escape(row['id'] + ' · ' + row['title']) + '</h2>'
        if row['kind'] == 'research':
            body += '<p><b>' + ('Reviewer-marked comparable' if row['fields'].get('comparable') else 'Excluded from direct comparison') + '</b><br>' + escape(row['fields'].get('comparability_warning', LIMIT)) + '</p>'
        for name, value in (('Creator', row['created_by_display_name']), ('Revision', row['revision']), ('Created', row['created_at'][:10]),
                            ('Original filename', row.get('original_filename', '')), ('Source path', row.get('relative_path', ''))):
            if value != '': body += '<p><b>' + name + ':</b> ' + escape(str(value)) + '</p>'
        body += '<h3>Metadata</h3>'
        for key, value in row['fields'].items():
            if key not in ('upload_uuid', 'checksum') and value not in ('', [], None):
                body += '<p><b>' + escape(key.replace('_', ' ').title()) + ':</b><br>' + escape(display(value)).replace('\n', '<br>') + '</p>'
        body += '<h3>Linked records</h3>' + ''.join('<p>' + escape(r['id'] + ' · ' + r['title']) + '</p>' for r in linked)
        body += '<h3>Provenance</h3><p>' + str(len(history)) + ' audited changes. Inspect audit for prior/new values and immutable UUIDs.</p>'
        self.details.setHtml(body)

    def new(self):
        choices = [self.kind.itemData(i) for i in range(1, self.kind.count()) if self.kind.itemData(i) not in ('role', 'file')]
        choice, ok = QInputDialog.getItem(self, 'New record', 'Record type', choices, 0, False)
        if not ok: return
        editor = RecordEditor(self.service, choice, parent=self)
        if editor.exec(): self.attempt(lambda: self.service.submit(choice, editor.title.text(), editor.values())); self.reload()

    def edit(self):
        row = self.selected()
        if not row: return
        editor = RecordEditor(self.service, row['kind'], row, self)
        if editor.exec(): self.attempt(lambda: self.service.submit(row['kind'], editor.title.text(), editor.values(), row['uuid'], editor.reason.text())); self.reload()

    def upload(self):
        source, _ = QFileDialog.getOpenFileName(self, 'Select resident file to copy; source remains unchanged')
        if not source: return
        editor = RecordEditor(self.service, 'file', parent=self); editor.title.setText(Path(source).stem)
        if editor.exec():
            values, title = editor.values(), editor.title.text()
            self.run(lambda: self.service.upload(source, title, values))

    def open(self):
        row = self.selected()
        if row and row.get('relative_path'):
            def action():
                target = self.service.safe(row['relative_path'])
                if not target.exists(): raise ValueError('Source is missing or not synchronized. It has not been marked deleted.')
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
            self.attempt(action)

    def text_dialog(self, title, text):
        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.resize(800, 600)
        layout = QVBoxLayout(dialog); view = QTextEdit(); view.setReadOnly(True); view.setPlainText(text); layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons); dialog.exec()

    def setup(self):
        preview = self.attempt(self.service.preview)
        if preview is None: return
        if QMessageBox.question(self, 'Preview additive structure', json.dumps(preview, indent=2) + '\nCreate missing folders and enroll this Admin device? Existing files will stay in place.') == QMessageBox.Yes:
            self.run(self.service.initialize)

    def publish(self): self.run(self.service.consume)
    def sync(self):
        configured = self.window.store.local.get('project_locations', {}).get('shared_storage')
        if configured and Path(configured).resolve() != self.service.root:
            self.service = Organization(self.window.store)
            self.path.setText('Configured root: ' + str(self.service.root))
        self.run(lambda: (self.service.flush(), self.service.refresh()))
    def pending(self): self.attempt(lambda: self.text_dialog('Pending / accepted / conflicting proposals', json.dumps(self.service.pending(), indent=2)))
    def audit(self):
        row = self.selected()
        if row: self.text_dialog('Record metadata and append-only audit', json.dumps({'record': row, 'history': [r for r in self.service.state['audit'] if r.get('record_uuid') == row['uuid']]}, indent=2, ensure_ascii=False))
    def resubmit(self):
        requests = [r for r in self.service.pending() if r.get('receipt', {}).get('status') == 'conflict']
        if not requests:
            QMessageBox.information(self, 'Resubmit request', 'No conflicting requests are available. Offline requests retry automatically.'); return
        choices = [r['title'] + ' · ' + r['request_uuid'] for r in requests]
        choice, ok = QInputDialog.getItem(self, 'Reviewed request retry', 'Inspect Pending requests and current audit before choosing:', choices, 0, False)
        if not ok: return
        reason, ok = QInputDialog.getText(self, 'Reason for retry', 'Explain why this correction should apply to the current published revision:')
        if ok:
            request = requests[choices.index(choice)]
            self.run(lambda: self.service.resubmit(request['request_uuid'], reason))
    def reconcile(self): self.run(self.service.reconcile, lambda value: self.text_dialog('Availability; no automatic deletions', json.dumps(value, indent=2)) if value is not None else None)

    def inventory(self):
        self.cancel.clear()
        def reviewed(report):
            if report is None: return
            summary = {'files': len(report['files']), 'complete': report['complete'], 'legacy_aliases': report.get('aliases_found', []),
                       'sample_candidates': sum('sample' in p.casefold() for p in report['files']), 'moves': [], 'deletions': []}
            if QMessageBox.question(self, 'Legacy inventory preview', json.dumps(summary, indent=2) + '\nRegister these records with Unknown creators and original paths?') == QMessageBox.Yes:
                self.run(lambda: self.service.import_inventory(report))
        self.run(lambda: self.service.inventory(self.cancel.is_set), reviewed)
        self.cancel_button.setVisible(True); self.cancel_button.setEnabled(True)

    def rollback(self):
        revision, ok = QInputDialog.getInt(self, 'Restore snapshot as a new version', 'Known-good revision', 1, 1)
        if ok and QMessageBox.question(self, 'Confirm snapshot restore', 'Retain audit, IDs and files; restore metadata as a new publication?') == QMessageBox.Yes:
            self.run(lambda: self.service.rollback(revision))

    def export(self):
        row = self.selected()
        if not row or row['kind'] != 'meeting':
            QMessageBox.information(self, 'Meeting export', 'Select a published meeting first.'); return
        stage, ok = QInputDialog.getItem(self, 'Meeting export', 'Editable template / finalized text', list(MEETING_TEMPLATES), 0, False)
        if ok:
            from app.services.organization_export import export_meeting
            self.run(lambda: export_meeting(self.service, row['uuid'], stage), lambda path: self.text_dialog('Meeting PDF staged for Admin publication', 'Preview: ' + str(path) + '\nThe verified PDF will be published into this MTG folder with its file metadata.') if path else None)
