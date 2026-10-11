"""Four organization categories with guided metadata and proposal review."""
import json
import copy
import threading
from html import escape
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
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
    'task': ('owner_id', 'supporting_members', 'due_date', 'acceptance', 'status', 'meeting_uuid', 'goal_uuid', 'period_uuid',
             'milestone', 'semester', 'deliverable', 'linked_file_uuids', 'decision_reference', 'blockers'),
    'role': ('member_id', 'backup_id', 'notes'),
    'goal': ('owner_id', 'due_date', 'status', 'output', 'next_step', 'blockers', 'period_uuid', 'active_goal'),
    'period': ('start_date', 'end_date', 'due_at', 'grace_at', 'review_at'),
    'deliverable': ('owner_id', 'period_uuid', 'role_uuid', 'submission_status', 'work_completed',
                    'evidence_uuids', 'in_progress', 'results', 'blockers', 'next_plan', 'support_needed',
                    'notes', 'reviewer_id', 'feedback', 'addendum_to'),
    'file': ('file_state', 'created_at', 'sequence', 'experiment_uuid', 'sample_uuids', 'procedure_uuid', 'meeting_uuid', 'design_uuid', 'research_uuid',
             'procedure_revision', 'parent_file_uuid', 'processing_run_id', 'document_type',
             'microscope_scale_calibration', 'magnification', 'illumination', 'exposure', 'sample_side_region',
             'operator_id', 'apparatus_settings', 'pressure_compression', 'units', 'run_count', 'notes'),
}
FIELDS['file'] += ('recording_consent', 'deliverable_uuid')
FIELDS['meeting'] += ('period_uuid', 'next_priorities', 'recording_consent', 'transcript_status')
FIELDS['experiment'] += ('status', 'active_experiment')
LONG = {'work_completed', 'in_progress', 'next_plan', 'support_needed', 'next_priorities',
        'history', 'instructions', 'setup', 'results', 'notes', 'comparison_reason', 'feedback',
        'agenda', 'minutes', 'summary', 'decisions', 'blockers', 'acceptance', 'follow_up'}
PEOPLE = {'owner_id', 'member_id', 'backup_id', 'facilitator_id', 'note_taker_id', 'reviewer_id',
          'operator_id', 'summary_reviewed_by_id'}
LINKS = {'procedure_uuid': 'procedure', 'experiment_uuid': 'experiment', 'meeting_uuid': 'meeting',
         'parent_file_uuid': 'file', 'cad_source_uuid': 'file', 'design_uuid': 'design', 'research_uuid': 'research'}
LINKS.update(period_uuid='period', goal_uuid='goal', role_uuid='role', addendum_to='deliverable', deliverable_uuid='deliverable')
CHOICES = {'file_state': ('raw', 'poremap', 'overlay', 'outline', 'derived', 'reference'),
    'stage': ('agenda', 'minutes', 'summary'), 'status': ('planned', 'active', 'blocked', 'done'),
    'dimensionality': ('Unverified', '2D', '3D'), 'new_used_state': ('Unverified', 'New', 'Used'),
    'semester': ('Fall 2026', 'Spring 2027 — future planning only'),
    'summary_approved': ('No', 'Yes'), 'active_goal': ('No', 'Yes'), 'active_experiment': ('No', 'Yes'),
    'recording_consent': ('No', 'Yes'), 'transcript_status': ('Not Supplied', 'Uploaded', 'Transcribed', 'Reviewed'),
    'submission_status': ('Draft', 'Submitted', 'Under Review', 'Accepted', 'Changes Requested', 'Resubmitted')}
FIELD_LABELS = {'sample_uuids': 'Linked Samples', 'procedure_uuid': 'Procedure', 'procedure_revision': 'Exact Procedure Revision',
    'parent_file_uuid': 'Original Raw Image', 'processing_run_id': 'Processing Run UUID', 'created_at': 'Original Capture / Record Date',
    'owner_id': 'Accountable Owner', 'period_uuid': 'Reporting Period', 'role_uuid': 'Assigned Coordination Role',
    'evidence_uuids': 'Linked Evidence', 'goal_uuid': 'Goal', 'deliverable_uuid': 'Biweekly Submission',
    'due_at': 'Deadline with Timezone', 'grace_at': 'Optional Grace Deadline', 'review_at': 'Optional Review Date',
    'file_state': 'File Subtype', 'cad_source_uuid': 'Editable CAD Source', 'export_file_uuids': 'Fabrication Export Files',
    'summary_reviewed_by_id': 'Summary Reviewer', 'attendees': 'Actual Attendance (select Present members)',
    'recording_consent': 'Participant Permission to Store Recording', 'addendum_to': 'Accepted Submission for Addendum'}


class RecordEditor(QDialog):
    def __init__(self, service, kind, row=None, parent=None, defaults=None):
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
        values = (row or {}).get('fields', defaults or {})
        self.initial_fields = copy.deepcopy(values)
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
                    if key == 'status' and kind == 'goal': choices = ('To Do', 'In Progress', 'Blocked', 'Done')
                    if key == 'status' and kind == 'experiment': choices = ('Ready', 'Running', 'In Use', 'Data Collected', 'Analyzed', 'Reviewed')
                    for item in choices:
                        human = {'raw': 'Raw Image', 'poremap': 'Pore Map', 'overlay': 'Overlay', 'outline': 'Outline',
                                 'derived': 'Other Processed Output', 'reference': 'Reference / Document', 'planned': 'To Do',
                                 'active': 'In Progress', 'blocked': 'Blocked', 'done': 'Done'}.get(item, item.replace('_', ' '))
                        widget.addItem(human, item)
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif key in ('sample_uuids', 'attendees', 'supporting_members', 'evidence_uuids'):
                widget = QListWidget(); widget.setSelectionMode(QAbstractItemView.MultiSelection); widget.setMaximumHeight(110)
                candidates = service.rows(kind='sample') if key == 'sample_uuids' else service.rows() if key == 'evidence_uuids' else service.accounts.users()
                for candidate in candidates:
                    label = candidate.get('display_name') or candidate['id'] + ' · ' + candidate['title']
                    widget.addItem(label); item = widget.item(widget.count() - 1)
                    item.setData(Qt.UserRole, candidate['uuid'] if key in ('sample_uuids', 'evidence_uuids') else candidate['id'])
                    item.setSelected(item.data(Qt.UserRole) in value)
            elif key in LONG:
                widget = QTextEdit(); widget.setPlainText(str(value)); widget.setFixedHeight(125)
                widget.setStyleSheet('QTextEdit { min-height:105px; max-height:105px; }')
            else:
                widget = QLineEdit(', '.join(value) if isinstance(value, list) else str(value))
                if key == 'created_at': widget.setPlaceholderText('YYYY-MM-DD (source creation/capture date; blank = today)')
                if key == 'due_date': widget.setPlaceholderText('YYYY-MM-DD')
                if key in ('start_date', 'end_date'): widget.setPlaceholderText('YYYY-MM-DD; fourteen-day reporting span')
                if key.endswith('_at') and key != 'created_at': widget.setPlaceholderText('YYYY-MM-DDTHH:MM:SS-05:00 (include timezone)')
                if key.endswith('_uuids'): widget.setPlaceholderText('Comma-separated immutable file UUIDs from details')
            if row and key == 'created_at': widget.setEnabled(False)
            self.fields[key] = widget
            form.addRow(FIELD_LABELS.get(key, key.replace('_uuid', '').replace('_id', '').replace('_', ' ').title()), widget)
        self.reason = QLineEdit(); form.addRow('Reason for edit', self.reason)
        if kind == 'meeting':
            views = QComboBox(); views.addItems(('Meeting Details', 'Agenda', 'Live Notes & Attendance', 'Summary & Approval'))
            layout.insertWidget(1, views)
            groups = ({'created_at', 'meeting_time', 'location', 'facilitator_id', 'note_taker_id', 'period_uuid', 'next_meeting_date'},
                      {'agenda', 'period_uuid'}, {'minutes', 'attendees', 'decisions', 'blockers', 'next_priorities', 'recording_path', 'recording_consent', 'transcript_path', 'transcript_status'},
                      {'summary', 'summary_reviewed_by_id', 'summary_approved'})
            def view(index):
                for key, widget in self.fields.items(): form.setRowVisible(widget, key in groups[index] or key == 'stage')
            views.currentIndexChanged.connect(view); views.setCurrentIndex({'agenda': 1, 'minutes': 2, 'summary': 3}.get(values.get('stage', 'agenda'), 1)); view(views.currentIndex())
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        if kind in ('meeting', 'deliverable'):
            from app.services.storage import read_json, write_json
            self.draft_path = service.local / 'drafts' / service.actor['user_id'] / (kind + '-' + ((row or {}).get('uuid') or 'new') + '.json')
            cached = read_json(self.draft_path, {})
            def recover():
                if cached.get('base_revision') != ((row or {}).get('revision', 0)):
                    QMessageBox.information(self, 'Compare recovered draft', 'The shared record changed. Copy relevant text after comparing; no newer notes will be overwritten.\n' + json.dumps(cached, indent=2)); return
                self.title.setText(cached.get('title', ''))
                for key, value in cached.get('fields', {}).items():
                    control = self.fields.get(key)
                    if isinstance(control, QComboBox): control.setCurrentIndex(max(0, control.findData(value)))
                    elif isinstance(control, QTextEdit): control.setPlainText(str(value))
                    elif isinstance(control, QLineEdit): control.setText(', '.join(value) if isinstance(value, list) else str(value))
                    elif isinstance(control, QListWidget):
                        for index in range(control.count()): control.item(index).setSelected(control.item(index).data(Qt.UserRole) in value)
            if cached:
                recover_button = QPushButton('Recover Local Draft'); recover_button.clicked.connect(recover); layout.addWidget(recover_button)
            self.draft_timer = QTimer(self)
            def autosave():
                try:
                    write_json(self.draft_path, {'base_revision': (row or {}).get('revision', 0), 'title': self.title.text(), 'fields': self.values()})
                except (OSError, ValueError): self.error.setText('Local draft could not be saved. Use Save to queue changes or keep the editor open.')
            self.autosave = autosave
            self.draft_timer.timeout.connect(autosave); self.draft_timer.start(5000)
            self.finished.connect(lambda _: self.draft_timer.stop())
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def values(self):
        values = copy.deepcopy(self.initial_fields)
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
            from app.services.team_workflow import validate
            validate(self.service, self.kind, self.values(), self.service.state['records'], self.row)
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
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        vertical = QSplitter(Qt.Vertical); outer.addWidget(vertical)
        self.controls_scroll = QScrollArea(); self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setAccessibleName('Project filters and actions; scroll for additional controls')
        self.controls_scroll.setMinimumHeight(100)
        controls = QWidget(); layout = QVBoxLayout(controls)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.controls_scroll.setWidget(controls); vertical.addWidget(self.controls_scroll)
        heading = QLabel('Project organization'); heading.setProperty('kind', 'heading'); layout.addWidget(heading)
        subtitle = QLabel('Four research categories · permanent identities · traceable revisions · Admin-published shared index')
        subtitle.setWordWrap(True); layout.addWidget(subtitle)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.path = QLabel('Configured root: ' + str(self.service.root)); self.path.setWordWrap(True); layout.addWidget(self.path)
        nav = FlowLayout(); layout.addLayout(nav)
        self.category = QComboBox(); self.category.addItems(CATEGORIES); nav.addWidget(self.category)
        self.subsection = QComboBox(); self.subsection.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.subsection.setMinimumContentsLength(18); nav.addWidget(self.subsection)
        self.kind = QComboBox(); nav.addWidget(self.kind)
        filter_row = FlowLayout(); layout.addLayout(filter_row)
        self.archive_filter = QComboBox(); self.archive_filter.addItems(('Current Records', 'Archived Records', 'All Records')); filter_row.addWidget(self.archive_filter)
        self.workspace_filter = QComboBox(); self.workspace_filter.addItems(('Project & Workspace', 'Canonical Project Only', 'Workspace Only')); filter_row.addWidget(self.workspace_filter)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search IDs, aliases, names, contributors or provenance'); filter_row.addWidget(self.search)
        clear = QPushButton('Clear Filters'); clear.clicked.connect(lambda: (self.search.clear(), self.subsection.setCurrentIndex(0), self.archive_filter.setCurrentIndex(0), self.workspace_filter.setCurrentIndex(0), self.kind.setCurrentIndex(0))); filter_row.addWidget(clear)
        self.actions = FlowLayout(); layout.addLayout(self.actions)
        for title, action in (('New record', self.new), ('Upload file', self.upload), ('Edit metadata', self.edit),
                              ('Open source', self.open), ('Refresh / submit pending', self.sync), ('Pending requests', self.pending),
                              ('Meeting export', self.export), ('Inspect audit', self.audit), ('Resubmit reviewed request', self.resubmit)):
            control = QPushButton(title); control.clicked.connect(action); self.actions.addWidget(control)
        admin = FlowLayout(); layout.addLayout(admin)
        for title, action in (('Preview / initialize', self.setup), ('Publish requests', self.publish),
                              ('Legacy dry run', self.inventory), ('Check missing paths', self.reconcile),
                              ('Restore snapshot', self.rollback), ('Archive / Restore Record', self.archive), ('Link Legacy Images', self.legacy_links)):
            control = QPushButton(title); control.clicked.connect(action); control.setVisible(self.service.accounts.admin_unlocked); admin.addWidget(control)
        self.cancel_button = QPushButton('Stop inventory safely'); self.cancel_button.clicked.connect(self.cancel.set)
        self.cancel_button.setVisible(False); admin.addWidget(self.cancel_button)
        split = QSplitter(); split.setMinimumHeight(180); vertical.addWidget(split)
        vertical.setStretchFactor(0, 0); vertical.setStretchFactor(1, 1); vertical.setSizes([240, 600])
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(('ID / type', 'Description', 'Revision / state', 'Creator', 'Owner / status'))
        from app.ui.workspace_components import prepare_table
        prepare_table(self.table, 'Project records; select to inspect full metadata')
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); split.addWidget(self.table)
        self.table.setColumnWidth(0, 145); self.table.setColumnWidth(2, 120); self.table.setColumnWidth(3, 145); self.table.setColumnWidth(4, 180)
        detail_page = QWidget(); detail_layout = QVBoxLayout(detail_page)
        self.image = QLabel(); self.image.setAlignment(Qt.AlignCenter); self.image.setMaximumHeight(250); self.image.hide(); detail_layout.addWidget(self.image)
        self.image_choice = QComboBox(); self.image_choice.hide(); detail_layout.addWidget(self.image_choice)
        self.image_choice.currentIndexChanged.connect(self.preview_image)
        self.details = QTextEdit(); self.details.setReadOnly(True); detail_layout.addWidget(self.details, 1)
        split.addWidget(detail_page); split.setSizes([820, 360])
        self.table.itemSelectionChanged.connect(self.detail)
        self.category.currentTextChanged.connect(self.change_category)
        self.subsection.currentIndexChanged.connect(self.select_subsection)
        self.kind.currentIndexChanged.connect(self.reload); self.search.textChanged.connect(self.reload)
        self.archive_filter.currentIndexChanged.connect(self.reload); self.workspace_filter.currentIndexChanged.connect(self.reload)
        notice = QLabel(LIMIT + ' Literature comparisons require a recorded reviewer rationale. Automatic transcription is not available; attach a verified transcript manually.')
        notice.setWordWrap(True); layout.addWidget(notice)
        for control, name in ((self.category, 'Project category'), (self.subsection, 'Project subsection'), (self.kind, 'Record type'), (self.search, 'Search project records')):
            control.setAccessibleName(name)
        self.details.setAccessibleName('Selected record details and history')
        self.change_category()
        self.table.setSortingEnabled(True)
        layout.addStretch()

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
            if hasattr(self.window, 'home_panel'): self.window.home_panel.reload()
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
        from app.ui.home import SUBMENUS
        self.subsection.blockSignals(True); self.subsection.clear()
        self.subsection.addItem('All ' + self.category.currentText() + ' records', None)
        for label, kind, section in SUBMENUS[self.category.currentText()]: self.subsection.addItem(label, (kind, section))
        self.subsection.blockSignals(False)
        self.kind.blockSignals(True); self.kind.clear(); self.kind.addItem('All record types', '')
        for kind, (_, category) in KINDS.items():
            if category == self.category.currentText() or kind == 'file': self.kind.addItem(kind.title(), kind)
        self.kind.blockSignals(False); self.reload()

    def select_subsection(self, *_):
        selected = self.subsection.currentData()
        self.search.clear()
        self.kind.setCurrentIndex(max(0, self.kind.findData(selected[0] if selected else '')))
        self.reload()

    def reload(self, *_):
        current = self.selected()
        selected_key = current['uuid'] if current else None
        scroll = self.table.verticalScrollBar().value()
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.rows = self.service.rows(self.category.currentText(), self.kind.currentData(), self.search.text())
        if self.archive_filter.currentIndex() < 2:
            archived = self.archive_filter.currentIndex() == 1
            self.rows = [r for r in self.rows if (r['fields'].get('archived') == 'Yes') == archived]
        if self.workspace_filter.currentIndex():
            workspace = self.workspace_filter.currentIndex() == 2
            self.rows = [r for r in self.rows if r.get('relative_path', '').startswith('_Team_Workspaces/') == workspace]
        selected = self.subsection.currentData()
        if selected and selected[1]:
            section = selected[1]
            self.rows = [r for r in self.rows if section in (r['fields'].get('research_section'), r['fields'].get('design_section'), r['fields'].get('document_type'), r['fields'].get('stage'))
                         or section == 'minutes' and r['fields'].get('stage') == 'summary']
        self.table.setRowCount(len(self.rows))
        self.table.clearSelection(); self.table.setCurrentCell(-1, -1)
        people = {p['id']: p['display_name'] for p in self.service.accounts.registry['users']}
        for number, row in enumerate(self.rows):
            fields = dict(row['fields'])
            if row['kind'] == 'deliverable':
                fields['file_state'] = fields.get('submission_status', 'Draft')
                fields['status'] = fields['file_state']
            values = (row['id'] + ' · ' + row['kind'], row['title'], str(row['revision']) + ' · ' + fields.get('file_state', fields.get('stage', 'record')),
                      row['created_by_display_name'], people.get(fields.get('owner_id'), 'Unassigned') + ' · ' + fields.get('status', ''))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.UserRole, row['uuid']); item.setToolTip(value)
                self.table.setItem(number, column, item)
        self.table.setSortingEnabled(sorting)
        self.table.blockSignals(False)
        self.status.setText(self.service.status)
        self.image.hide()
        self.details.setPlainText('Select a record to inspect metadata, immutable UUIDs and revision history.\n\nFall 2026 priorities: literature/standards, legacy catalog, baseline microscopy, equipment refurbishment, methods and fixture design. Spring 2027 testing remains future work.')

        if selected_key: self.select_record(selected_key)
        self.table.verticalScrollBar().setValue(scroll)

    def select_record(self, key):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == key:
                self.table.selectRow(row); self.detail(); return True
        return False

    def selected(self):
        item = self.table.item(self.table.currentRow(), 0)
        key = item.data(Qt.UserRole) if item else None
        return next((r for r in getattr(self, 'rows', ()) if r['uuid'] == key), None)

    def detail(self):
        row = self.selected()
        if not row: return
        self.image.hide()
        self.image_choice.blockSignals(True); self.image_choice.clear()
        candidates = [row] + [r for r in self.service.rows() if (row['kind'] == 'sample' and row['uuid'] in r['fields'].get('sample_uuids', []))
            or r['fields'].get('parent_file_uuid') == row['uuid'] or row['fields'].get('parent_file_uuid') == r['uuid']]
        for candidate in candidates:
            if Path(candidate.get('relative_path', '')).suffix.lower() in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'):
                self.image_choice.addItem(candidate['id'] + ' · ' + candidate['fields'].get('file_state', 'reference') + ' · ' + candidate['title'], candidate['uuid'])
        self.image_choice.blockSignals(False); self.image_choice.setVisible(self.image_choice.count() > 0)
        self.preview_image()
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
        for name, value in (('Creator', row['created_by_display_name']), ('Identity verification', row.get('created_by_verification', 'Historical app attribution')), ('Revision', row['revision']), ('Created', row['created_at'][:10]),
                            ('Original filename', row.get('original_filename', '')), ('Source path', row.get('relative_path', ''))):
            if value != '': body += '<p><b>' + name + ':</b> ' + escape(str(value)) + '</p>'
        body += '<h3>Metadata</h3>'
        for key, value in row['fields'].items():
            if key not in ('upload_uuid', 'checksum') and value not in ('', [], None):
                body += '<p><b>' + escape(key.replace('_', ' ').title()) + ':</b><br>' + escape(display(value)).replace('\n', '<br>') + '</p>'
        body += '<h3>Linked records</h3>' + ''.join('<p>' + escape(r['id'] + ' · ' + r['title']) + '</p>' for r in linked)
        body += '<h3>Provenance</h3><p>' + str(len(history)) + ' audited changes. Inspect audit for prior/new values and immutable UUIDs.</p>'
        self.details.setHtml(body)

    def preview_image(self, *_):
        self.image.hide()
        row = self.service.state['records'].get(self.image_choice.currentData(), {})
        if not row.get('relative_path'): return
        from app.services.project_storage import PLACEHOLDER_FLAGS
        source = self.service.safe(row['relative_path'])
        if source.is_file() and not getattr(source.stat(), 'st_file_attributes', 0) & PLACEHOLDER_FLAGS:
            reader = QImageReader(str(source))
            if reader.canRead():
                reader.setScaledSize(reader.size().scaled(360, 240, Qt.KeepAspectRatio))
                self.image.setPixmap(QPixmap.fromImage(reader.read())); self.image.show()

    def legacy_links(self):
        dialog = QDialog(self); dialog.setWindowTitle('Review Legacy Image Associations'); dialog.resize(650, 450); form = QFormLayout(dialog)
        sample, raw = QComboBox(), QComboBox()
        derivatives = QListWidget(); derivatives.setSelectionMode(QAbstractItemView.MultiSelection)
        for row in self.service.rows(kind='sample'): sample.addItem(row['id'] + ' · ' + row['title'], row['uuid'])
        for row in self.service.rows():
            if not row.get('legacy'): continue
            state = row['fields'].get('file_state')
            if state in ('raw', 'reference'): raw.addItem(row['id'] + ' · ' + row['title'], row['uuid'])
            if state in ('poremap', 'overlay', 'outline'):
                derivatives.addItem(row['id'] + ' · ' + row['title']); derivatives.item(derivatives.count()-1).setData(Qt.UserRole, row['uuid'])
        reason = QLineEdit(); form.addRow('Published sample', sample); form.addRow('Legacy raw image', raw); form.addRow('Matching derivative images', derivatives); form.addRow('Association evidence / reason', reason)
        form.addRow(QLabel('Original files and Unknown creators are preserved. Processing conditions remain unverified.'))
        controls = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        def save():
            sample_key, raw_key = sample.currentData(), raw.currentData()
            derived_keys, evidence = [item.data(Qt.UserRole) for item in derivatives.selectedItems()], reason.text()
            self.run(lambda: self.service.link_legacy_images(sample_key, raw_key, derived_keys, evidence)); dialog.accept()
        controls.accepted.connect(save)
        controls.rejected.connect(dialog.reject); form.addRow(controls); dialog.exec()

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
        from app.ui.intake import IntakeDialog
        IntakeDialog(self, self.service).exec()

    def open(self):
        row = self.selected()
        if row and row.get('relative_path'):
            def action():
                target = self.service.safe(row['relative_path'])
                if not target.exists(): raise ValueError('Source is missing or not synchronized. It has not been marked deleted.')
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
            self.attempt(action)

    def archive(self):
        row = self.selected()
        if not row or row['kind'] == 'role': return
        archived = row['fields'].get('archived') == 'Yes'
        reason, ok = QInputDialog.getText(self, 'Restore record' if archived else 'Archive record', 'Reason (no files will be deleted or moved):')
        if not ok or not reason.strip(): return
        values = dict(row['fields'], archived='No' if archived else 'Yes')
        self.attempt(lambda: self.service.submit(row['kind'], row['title'], values, row['uuid'], reason))
        self.reload()

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
        configured = self.window.store.local.get('organization_root') or self.window.store.local.get('project_locations', {}).get('shared_storage')
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
