"""Four project destinations and a compact pulse from authoritative records.

apple-design: immediate native feedback, explicit wayfinding, system type,
resizable grouping, static transitions and accessible solid surfaces.
"""
import copy
import json
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextBrowser, QFrame, QComboBox, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QMessageBox, QCheckBox)
from app.edition import DISPLAY_VERSION, CHANNEL
from app.services.organization import CATEGORIES
from app.services.team_workflow import workspace_relative, user_code, period_status, draft_summary, digest_text
from app.services.storage import timestamp
from app.ui.components import ResponsiveCards
from app.ui.flow_layout import FlowLayout
from app.ui.organization import RecordEditor

SUBMENUS = {
    'Experimental': [('Experiments', 'experiment', ''), ('Samples', 'sample', ''), ('Procedures', 'procedure', ''),
        ('Images & Analysis', 'file', ''), ('Experimental Equipment', 'file', 'Equipment'), ('Data & Results', 'file', 'Results')],
    'Research': [('Published Articles', 'research', 'Published_Articles'), ('ASTM Standards & References', 'research', 'ASTM_Standards_and_References'),
        ('Previous Research', 'research', 'Previous_Research'), ('Literature Reviews & Comparisons', 'research', 'Literature_Reviews_and_Comparisons')],
    'Meetings & Goals': [('Meetings', 'meeting', ''), ('Agendas', 'meeting', 'agenda'), ('Meeting Notes & Summaries', 'meeting', 'minutes'),
        ('Goals & Milestones', 'goal', ''), ('Biweekly Deliverables', 'deliverable', ''), ('Tasks & Decisions', 'task', '')],
    'Design & Prototyping': [('CAD Models & Drawings', 'design', 'CAD_and_Drawings'), ('Manufacturing & Laser Files', 'design', 'Manufacturing_and_Laser'),
        ('3D Printing', 'design', '3D_Printing'), ('Design Parameters', 'design', 'Parameters_and_Calculations'), ('Prototypes & Feedback', 'design', 'Prototypes_and_Feedback')],
}


def button(text, action):
    control = QPushButton(text.replace('&', '&&')); control.clicked.connect(action); return control


class HomePanel(QScrollArea):
    def __init__(self, window):
        super().__init__(window)
        self.window = window; self.panel = window.organization_panel
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        page = QWidget(); self.body = QVBoxLayout(page); self.body.setSpacing(16); self.setWidget(page)
        self.title = QLabel('Project Home'); self.title.setStyleSheet('font-size:28px;font-weight:600'); self.body.addWidget(self.title)
        self.stage = QLabel(CHANNEL.title() + ' · ' + DISPLAY_VERSION + ' · Local team identity'); self.body.addWidget(self.stage)
        self.notifications = QLabel(); self.notifications.setWordWrap(True); self.body.addWidget(self.notifications)
        utility = FlowLayout(); self.body.addLayout(utility)
        for text, action in (('Settings', self.settings), ('My Workspace', self.workspace), ('Notifications / Activity', self.activity),
                             ('Account / PIN', self.account), ('Refresh Index', self.sync)):
            utility.addWidget(button(text, action))
        if self.service.accounts.admin_unlocked: utility.addWidget(button('Administration', self.administration))
        navigation = FlowLayout(); self.body.addLayout(navigation)
        self.category_buttons = []
        for category in CATEGORIES:
            control = button(category, lambda checked=False, c=category: self.navigate(c))
            control.setObjectName('primary-category'); control.setMinimumSize(230, 70)
            control.setStyleSheet('QPushButton { font-size:17px;font-weight:600;padding:18px; }')
            self.category_buttons.append(control); navigation.addWidget(control)
        self.cards = {}
        for name in ('Current Goal', 'Progress and Near-Term Plan', 'Next Meeting & Agenda', 'Schedule & Biweekly Due', 'Active Procedure & Parameters', 'Project Repository'):
            card = QFrame(); card.setObjectName('card'); layout = QVBoxLayout(card)
            label = QLabel(name); label.setStyleSheet('font-size:17px;font-weight:600'); layout.addWidget(label)
            view = QTextBrowser(); view.setOpenLinks(False); view.anchorClicked.connect(lambda url: self.open_record(url.toString()))
            view.setFixedHeight(105); view.setFrameShape(QFrame.NoFrame)
            layout.addWidget(view); self.cards[name] = (card, view)
        pulse = ResponsiveCards([c[0] for c in self.cards.values()])
        actions_title = QLabel('Quick Start'); actions_title.setStyleSheet('font-size:19px;font-weight:600'); self.body.addWidget(actions_title)
        quick = FlowLayout(); self.body.addLayout(quick)
        for text, kind in (('New Experiment', 'experiment'), ('Register Sample', 'sample'), ('New / Revise Procedure', 'procedure'),
                           ('Add Research Reference', 'research'), ('New Design', 'design'), ('New Meeting', 'meeting'),
                           ('Submit Biweekly Deliverable', 'deliverable')):
            quick.addWidget(button(text, lambda checked=False, k=kind: self.create(k)))
        quick.addWidget(button('Upload Files', self.panel.upload))
        quick.addWidget(button('New Goal', lambda: self.create('goal')))
        quick.addWidget(button('New Task', lambda: self.create('task')))
        quick.addWidget(button('Generate Draft Meeting Summary', self.summary))
        quick.addWidget(button('Two-Week Team Digest', self.digest))
        if self.service.accounts.admin_unlocked: quick.addWidget(button('Configure Two-Week Periods', self.periods))
        self.body.addWidget(pulse)
        self.recent = QComboBox(); self.recent.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        recent_row = QHBoxLayout(); recent_row.addWidget(QLabel('Quick Open')); recent_row.addWidget(self.recent, 1)
        recent_row.addWidget(button('Open Record', lambda: self.open_record(self.recent.currentData()))); self.body.addLayout(recent_row)
        activity_heading = QLabel('Recent Activity'); activity_heading.setStyleSheet('font-size:19px;font-weight:600'); self.body.addWidget(activity_heading)
        filters = FlowLayout(); self.body.addLayout(filters)
        self.person = QComboBox(); self.person.addItem('Every contributor', '')
        for p in self.service.accounts.users(): self.person.addItem(p['display_name'], p['id'])
        self.area = QComboBox(); self.area.addItem('Every work area', ''); self.area.addItems(CATEGORIES)
        self.action = QComboBox(); self.action.addItems(('Every action', 'Upload', 'Update', 'Request'))
        self.file_type = QLineEdit(); self.file_type.setPlaceholderText('File extension, e.g. .pdf')
        self.after = QLineEdit(); self.after.setPlaceholderText('Since YYYY-MM-DD')
        for control in (self.person, self.area, self.action, self.file_type, self.after): filters.addWidget(control)
        filters.addWidget(button('Apply Filters', self.activity_rows)); filters.addWidget(button('Clear Filters', self.clear_filters))
        self.events = QTextBrowser(); self.events.setMaximumHeight(185); self.events.setOpenLinks(False)
        self.events.anchorClicked.connect(lambda url: self.open_record(url.toString())); self.body.addWidget(self.events)
        tools = QLabel('Tools & Resources'); tools.setStyleSheet('font-size:19px;font-weight:600'); self.body.addWidget(tools)
        toolrow = FlowLayout(); self.body.addLayout(toolrow)
        self.tools = QComboBox(); self.tools.setMinimumWidth(320); toolrow.addWidget(self.tools)
        toolrow.addWidget(button('Open Selected', self.open_tool)); toolrow.addWidget(button('Configure Resource', self.resource))
        toolrow.addWidget(button('Software Paths & Status', lambda: window.show_page('Software')))
        self.body.addStretch(); self.reload()

    @property
    def service(self): return self.panel.service

    def link(self, record):
        return '<a href="' + record['uuid'] + '">' + escape(record['id'] + ' · ' + record['title']) + '</a>'

    def reload(self):
        s = self.service; today = date.today().isoformat()
        self.stage.setText(CHANNEL.title() + ' · ' + DISPLAY_VERSION + ' · ' + user_code(s, s.actor['user_id']) + ' · ' + s.actor['display_name'])
        people = {p['id']: p['display_name'] for p in s.accounts.registry['users']}
        goals = [r for r in s.rows(kind='goal') if r['fields'].get('active_goal') == 'Yes' and r['fields'].get('status') != 'Done']
        goals.sort(key=lambda r: r['updated_at'], reverse=True)
        goal = goals[0] if goals else None
        self.cards['Current Goal'][1].setHtml(self.link(goal) + '<br>' + escape(goal['fields'].get('output', '')) + '<br>Owner: '
            + escape(people.get(goal['fields'].get('owner_id'), 'Unassigned')) + ' · due ' + escape(goal['fields']['due_date'])
            + '<br>Next: ' + escape(goal['fields'].get('next_step', '')) if goal else 'No active goal set. Create a goal and mark it active.')
        tasks = [r for r in s.rows(kind='task') if r['fields'].get('status') != 'done']
        tasks.sort(key=lambda r: r['fields'].get('due_date', '9999'))
        self.cards['Progress and Near-Term Plan'][1].setHtml('<br>'.join(self.link(r) + ' · ' + escape({'planned': 'To Do', 'active': 'In Progress', 'blocked': 'Blocked', 'done': 'Done'}.get(r['fields'].get('status', 'planned'), 'To Do'))
            + ' · ' + escape(people.get(r['fields'].get('owner_id'), 'Unassigned')) + ' · due ' + escape(r['fields'].get('due_date', ''))
            + (' · Overdue' if r['fields'].get('due_date', '9999') < today else '') + '<br>' + escape(r['fields'].get('blockers', '')) for r in tasks[:4]) or 'No open actions. Add an owned task with a deadline and deliverable.')
        meetings = sorted(s.rows(kind='meeting'), key=lambda r: r['created_at'])
        upcoming = [r for r in meetings if r['created_at'][:10] >= today]
        meeting = upcoming[0] if upcoming else None
        approved = [r for r in meetings if r['fields'].get('summary_approved') == 'Yes']
        meeting_text = self.link(meeting) + '<br>' + escape(meeting['created_at'][:10] + ' ' + meeting['fields'].get('meeting_time', '')) + '<br>' + escape(meeting['fields'].get('agenda', '')[:260]) if meeting else 'No upcoming meeting scheduled.'
        if approved: meeting_text += '<br>Latest approved summary: ' + self.link(approved[-1])
        self.cards['Next Meeting & Agenda'][1].setHtml(meeting_text)
        periods = sorted(s.rows(kind='period'), key=lambda r: r['fields']['start_date'])
        current = next((p for p in periods if p['fields']['start_date'] <= today <= p['fields']['end_date']), None)
        if not current: current = next((p for p in periods if p['fields']['end_date'] >= today), None)
        if not current and periods: current = periods[-1]
        notifications = []
        if self.window.store.local.get('task_reminders', True):
            mine = [t for t in tasks if t['fields'].get('owner_id') == s.actor['user_id']]
            if mine: notifications.append(str(len(mine)) + ' assigned open action(s)')
        if self.window.store.local.get('meeting_reminders', True) and meeting:
            notifications.append('Next meeting ' + meeting['created_at'][:10])
        if current and self.window.store.local.get('deliverable_reminders', True):
            notifications.append(current['id'] + ': ' + period_status(s, current, s.actor['user_id']))
        self.notifications.setText(' · '.join(notifications)); self.notifications.setVisible(bool(notifications))
        schedule = [self.link(r) + ' · ' + escape(r['created_at'][:10]) for r in upcoming[:2]]
        if current:
            schedule += [self.link(current) + '<br>Due ' + escape(current['fields']['due_at']) + '<br>' + escape(period_status(s, current, s.actor['user_id']))]
        schedule += [self.link(r) + ' · due ' + escape(r['fields']['due_date']) for r in s.rows(kind='goal') if r['fields'].get('status') != 'Done'][:2]
        self.cards['Schedule & Biweekly Due'][1].setHtml('<br>'.join(schedule) or 'Admin has not configured reporting deadlines. No submission is overdue without a configured period.')
        active = [r for r in s.rows(kind='experiment') if r['fields'].get('active_experiment') == 'Yes']
        experiment = max(active, key=lambda r: r['updated_at']) if active else None
        procedure = s.state['records'].get(experiment['fields'].get('procedure_uuid')) if experiment else None
        self.cards['Active Procedure & Parameters'][1].setHtml((self.link(procedure).replace(procedure['uuid'] + '"', procedure['uuid'] + '@' + str(experiment['fields']['procedure_revision']) + '"') + ' · locked revision ' + str(experiment['fields']['procedure_revision']) + '<br>Experiment: ' + self.link(experiment)
            + '<br>' + escape(experiment['fields'].get('apparatus_settings', '')) + '<br>' + escape(experiment['fields'].get('units', '')))
            if procedure else 'Choose an active experiment with an exact published procedure revision. No measurements inferred.')
        self.cards['Project Repository'][1].setPlainText(str(s.root) + '\n' + s.status + '\nBeta/Development storage is an isolated sandbox.')
        root_button = self.cards['Project Repository'][0].findChild(QPushButton)
        if not root_button: self.cards['Project Repository'][0].layout().addWidget(button('Open Folder', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.root)))))
        recent_keys = self.window.store.local.get('organization_recent', [])
        self.recent.clear()
        for key in recent_keys:
            record = s.state['records'].get(key)
            if record: self.recent.addItem(record['id'] + ' · ' + record['title'], key)
        if not self.recent.count(): self.recent.addItem('Open a sample, procedure, experiment or meeting to keep a shortcut', '')
        self.tools.clear()
        for item in self.window.store.manifest:
            result = self.window.results.get(item['id'], {})
            self.tools.addItem(item['name'] + ' · ' + result.get('status', 'Not checked'), ('software', item['id']))
        for i, resource in sorted(enumerate(self.window.store.local.get('organization_resources', [])), key=lambda pair: not pair[1].get('favorite')):
            available = resource['target'].startswith(('https://', 'http://')) or Path(resource['target']).is_file()
            self.tools.addItem(('★ ' if resource.get('favorite') else '') + resource['name'] + ' · ' + resource['category'] + (' · Configured' if available else ' · Missing'), ('resource', i))
        self.activity_rows()

    def navigate(self, category):
        self.panel.category.setCurrentText(category); self.window.tabs.setCurrentWidget(self.panel)

    def open_record(self, key):
        if key and '@' in key:
            key, revision = key.split('@', 1)
            records = [a['new'] for a in self.service.state['audit'] if a.get('record_uuid') == key and a.get('new', {}).get('revision') == int(revision)]
            if not records: QMessageBox.information(self, 'Revision unavailable', 'The chosen historical revision has not synchronized. The experiment reference remains unchanged.'); return
            record = records[-1]
            dialog = QDialog(self); dialog.setWindowTitle(record['id'] + ' · Locked Procedure Revision ' + revision); dialog.resize(750, 550)
            layout = QVBoxLayout(dialog); view = QTextBrowser(); view.setPlainText(record['title'] + '\n\n' + record['fields'].get('instructions', '') + '\n\n' + json.dumps(record['fields'], indent=2)); layout.addWidget(view)
            layout.addWidget(button('Open Exact Revision File', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.safe(record['relative_path']))))))
            dialog.exec(); return
        record = self.service.state['records'].get(key)
        if not record: return
        self.navigate(record['category']); self.panel.subsection.setCurrentIndex(0)
        self.panel.kind.setCurrentIndex(0); self.panel.search.setText(record['id']); self.panel.reload()
        for i, row in enumerate(self.panel.rows):
            if row['uuid'] == key: self.panel.table.selectRow(i); break
        recent = self.window.store.local.setdefault('organization_recent', [])
        self.window.store.local['organization_recent'] = ([key] + [k for k in recent if k != key])[:12]; self.window.store.save_local()

    def create(self, kind):
        defaults = {'owner_id': self.service.actor['user_id']} if kind in ('task', 'goal', 'deliverable') else {}
        selected = self.panel.selected()
        if selected and kind == 'experiment' and selected['kind'] == 'sample': defaults['sample_uuids'] = [selected['uuid']]
        if kind == 'deliverable':
            today = date.today().isoformat()
            period = next((p for p in self.service.rows(kind='period') if p['fields']['start_date'] <= today <= p['fields']['end_date']), None)
            if period: defaults['period_uuid'] = period['uuid']
        existing = None
        if kind == 'procedure' and self.service.rows(kind='procedure'):
            from PySide6.QtWidgets import QInputDialog
            choices = ['Create New Procedure'] + [p['id'] + ' · ' + p['title'] for p in self.service.rows(kind='procedure')]
            choice, ok = QInputDialog.getItem(self, 'New / Revise Procedure', 'Procedure', choices, 0, False)
            if not ok: return
            if choice != choices[0]: existing = self.service.rows(kind='procedure')[choices.index(choice) - 1]
        editor = RecordEditor(self.service, kind, existing, parent=self, defaults=defaults)
        if editor.exec():
            self.panel.attempt(lambda: self.service.submit(kind, editor.title.text(), editor.values(), existing['uuid'] if existing else None, editor.reason.text())); self.reload()

    def workspace(self):
        dialog = QDialog(self); dialog.setWindowTitle('Personal Workspace (shared storage)'); dialog.resize(850, 560)
        layout = QVBoxLayout(dialog)
        path = self.service.safe(workspace_relative(self.service, self.service.actor['user_id']))
        hint = QLabel('This folder is visible to people with access to the shared library. App PINs do not restrict OneDrive file access.\n' + str(path)); hint.setWordWrap(True); layout.addWidget(hint)
        choices = QComboBox(); layout.addWidget(choices)
        for r in self.service.rows():
            if r['fields'].get('workspace_owner_id') == self.service.actor['user_id'] or r['kind'] == 'deliverable' and r['fields'].get('owner_id') == self.service.actor['user_id']:
                choices.addItem(r['id'] + ' · ' + r['title'], r['uuid'])
        layout.addWidget(button('Open My Folder', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))) if path.exists() else QMessageBox.information(dialog, 'Setup required', 'Ask Admin to initialize shared workspaces. No folder was silently created.')))
        from app.ui.intake import IntakeDialog
        layout.addWidget(button('Upload Workspace Drafts', lambda: IntakeDialog(self.panel, self.service, workspace=True).exec()))
        layout.addWidget(button('View Selected Record', lambda: self.open_record(choices.currentData())))
        destination = QComboBox(); destination.addItems(CATEGORIES); layout.addWidget(QLabel('Publish selected file into project category')); layout.addWidget(destination)
        def publish():
            record = self.service.state['records'].get(choices.currentData())
            if not record or record['kind'] != 'file' or not record['fields'].get('workspace_owner_id'): return
            fields = copy.deepcopy(record['fields']); fields.pop('workspace_owner_id', None)
            fields.update(destination_category=destination.currentText(), publish_workspace='Yes')
            editor = RecordEditor(self.service, 'file', parent=dialog, defaults=fields); editor.title.setText(record['title'])
            if not editor.exec(): return
            if QMessageBox.question(dialog, 'Publish workspace draft', 'After Admin publication, move this verified draft to the selected project folder? Original creator and file UUID remain unchanged.') != QMessageBox.Yes: return
            self.panel.attempt(lambda: self.service.submit('file', editor.title.text(), editor.values(), record['uuid'], 'Confirmed publication from shared workspace'))
        layout.addWidget(button('Publish / Move into Project', publish)); layout.addStretch(); dialog.exec()

    def summary(self):
        meetings = self.service.rows(kind='meeting')
        if not meetings: QMessageBox.information(self, 'New meeting first', 'Create and publish a meeting before generating a draft.'); return
        dialog = QDialog(self); dialog.setWindowTitle('Generate Draft Summary'); layout = QVBoxLayout(dialog)
        choice = QComboBox()
        for r in meetings: choice.addItem(r['id'] + ' · ' + r['title'], r['uuid'])
        layout.addWidget(choice)
        def generate():
            r = self.service.state['records'][choice.currentData()]; f = copy.deepcopy(r['fields'])
            f.update(summary=draft_summary(self.service, r), summary_approved='No', stage='summary')
            self.panel.attempt(lambda: self.service.submit('meeting', r['title'], f, r['uuid'], 'Template draft generated from entered notes; original minutes retained')); dialog.accept()
        layout.addWidget(button('Generate Template Draft', generate)); dialog.exec()

    def digest(self):
        periods = self.service.rows(kind='period')
        if not periods: QMessageBox.information(self, 'No reporting periods', 'Admin must configure a reporting period first.'); return
        dialog = QDialog(self); dialog.setWindowTitle('Biweekly Team Digest'); dialog.resize(800, 650); layout = QVBoxLayout(dialog)
        choice = QComboBox()
        for p in periods: choice.addItem(p['id'] + ' · ' + p['title'], p['uuid'])
        layout.addWidget(choice); view = QTextBrowser(); layout.addWidget(view)
        def update(): view.setPlainText(digest_text(self.service, self.service.state['records'][choice.currentData()]))
        choice.currentIndexChanged.connect(update); update()
        def export():
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(dialog, 'Export reviewed digest', 'biweekly-digest.txt', 'Text (*.txt)')
            if path: Path(path).write_text(view.toPlainText(), encoding='utf-8')
        layout.addWidget(button('Export Digest', export)); dialog.exec()

    def periods(self):
        dialog = QDialog(self); dialog.setWindowTitle('Configure Biweekly Reporting'); form = QFormLayout(dialog)
        anchor, count, due = QLineEdit(), QLineEdit('1'), QLineEdit()
        anchor.setPlaceholderText('YYYY-MM-DD'); due.setPlaceholderText('YYYY-MM-DDTHH:MM:SS-05:00')
        form.addRow('Semester anchor / first period start', anchor); form.addRow('Number of fourteen-day periods', count)
        form.addRow('First deadline with timezone', due)
        hint = QLabel('Each later deadline advances fourteen days. No default cutoff is assumed. Adjust individual grace/review dates in the period record.'); hint.setWordWrap(True); form.addRow(hint)
        error = QLabel(); form.addRow(error)
        def save():
            from app.services.team_workflow import configure_periods
            try:
                configure_periods(self.service, anchor.text().strip(), int(count.text()), due.text().strip()); self.reload(); dialog.accept()
            except (ValueError, OSError) as exc: error.setText(str(exc) if isinstance(exc, ValueError) else 'Storage unavailable; queued requests remain recoverable.')
        controls = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); controls.accepted.connect(save); controls.rejected.connect(dialog.reject); form.addRow(controls); dialog.exec()

    def activity_rows(self):
        rows = []
        person, category = self.person.currentData(), self.area.currentText() if self.area.currentIndex() else ''
        action, extension, after = self.action.currentText(), self.file_type.text().strip().lower(), self.after.text().strip()
        for audit in reversed(self.service.state['audit']):
            row = audit.get('new')
            if not row or person and audit['actor']['user_id'] != person or category and row['category'] != category: continue
            kind = 'Upload' if row['kind'] == 'file' and not audit.get('prior') else 'Update'
            if action not in ('Every action', kind): continue
            if extension and not row.get('relative_path', '').lower().endswith(extension): continue
            if after and audit['timestamp'][:10] < after: continue
            rows.append(escape(audit['timestamp'][:16] + ' · ' + audit['actor']['display_name'] + ' · ' + kind) + ' · ' + self.link(row))
        if action in ('Every action', 'Request'):
            for pending in self.service.pending():
                if pending.get('receipt', {}).get('status') == 'accepted': continue
                if person and pending['actor']['user_id'] != person: continue
                from app.services.organization import KINDS
                if category and KINDS.get(pending['kind'], ('', ''))[1] != category: continue
                if after and pending['created_at'][:10] < after: continue
                if extension and pending.get('fields', {}).get('extension') != extension: continue
                rows.append(escape(pending['actor']['display_name'] + ' · Request · ' + pending['title'] + ' · ' + pending.get('receipt', {}).get('status', 'pending')))
        self.events.setHtml('<br>'.join(rows[:30]) or 'No matching recorded activity. Counts do not measure contribution quality.')

    def clear_filters(self):
        self.person.setCurrentIndex(0); self.area.setCurrentIndex(0); self.action.setCurrentIndex(0); self.file_type.clear(); self.after.clear(); self.activity_rows()
    def sync(self): self.panel.sync()
    def activity(self): self.window.tabs.setCurrentWidget(self.window.local_activity_panel)
    def administration(self):
        self.window.tabs.setCurrentWidget(self.window.local_activity_panel)
    def account(self):
        control = self.window.findChild(QPushButton, 'current-user')
        if control: control.showMenu()
    def settings(self):
        dialog = QDialog(self); dialog.setWindowTitle('My Settings'); dialog.resize(730, 450); layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Per-user configuration · production and Beta remain separate'))
        root = QLineEdit(str(self.service.root)); layout.addWidget(QLabel('Locally synced project root (Beta: profile sandbox only)')); layout.addWidget(root)
        def relink():
            from app.services.organization import Organization
            try:
                candidate = Organization(self.window.store, root.text())
                if not candidate.refresh(): raise ValueError('Choose an existing root with a validated same-edition shared snapshot. Admin initializes new roots separately.')
                from app.services.storage import read_json
                current = read_json(self.service.control / 'identity.json', {})
                target = read_json(candidate.control / 'identity.json', {})
                if current.get('project_uuid') != target.get('project_uuid'): raise ValueError('This folder belongs to another project. Select the synchronized copy of this project.')
                profiles = candidate.root / 'AppData' / CHANNEL / 'Users' / 'profiles.json'
                registry = read_json(profiles, {})
                if registry.get('channel') != CHANNEL or {p['id'] for p in registry.get('users', [])} != {p['id'] for p in self.service.accounts.registry['users']}:
                    raise ValueError('Wait for the same team profiles to synchronize before relinking.')
                with self.service.accounts.lock:
                    self.window.store.local['organization_root'] = str(candidate.root)
                    self.window.store.save_local(); self.service.accounts.shared = profiles.parent.parent
                self.panel.service = candidate; self.panel.path.setText('Configured root: ' + str(candidate.root)); self.panel.reload(); self.reload(); dialog.accept()
            except (ValueError, OSError) as exc:
                self.window.store.organization_service = self.service
                QMessageBox.information(dialog, 'Root not changed', str(exc) if isinstance(exc, ValueError) else 'Folder unavailable; current mapping retained.')
        layout.addWidget(button('Validate / Relink Root', relink))
        diagnostics = QLabel(self.service.status + '\nLast published: ' + self.service.state.get('published_at', 'Not initialized')); diagnostics.setWordWrap(True); layout.addWidget(diagnostics)
        for key, title in (('meeting_reminders', 'Show meeting reminders'), ('task_reminders', 'Show assigned task reminders'), ('deliverable_reminders', 'Show biweekly deadline reminders')):
            check = QCheckBox(title); check.setChecked(self.window.store.local.get(key, True))
            check.toggled.connect(lambda value, k=key: (self.window.store.local.update({k: value}), self.window.store.save_local())); layout.addWidget(check)
        layout.addWidget(button('Account / PIN', self.account)); layout.addWidget(button('Configure Software Paths', lambda: self.window.show_page('Software')))
        if self.service.accounts.admin_unlocked: layout.addWidget(button('Advanced Storage Settings', lambda: self.window.open_settings(1)))
        layout.addStretch(); dialog.exec()

    def open_tool(self):
        selected = self.tools.currentData()
        if not selected: return
        if selected[0] == 'software':
            item = next(i for i in self.window.store.manifest if i['id'] == selected[1]); self.window.launch_item(item)
        else:
            from app.services.software import open_resource
            resource = self.window.store.local['organization_resources'][selected[1]]
            def launch():
                target = resource['target']
                if target.startswith(('https://', 'http://')): open_resource(target)
                elif Path(target).is_file():
                    import os
                    os.startfile(str(Path(target).resolve()))
                else: raise ValueError('Resource unavailable. Update its path before retrying.')
            self.window.guard(launch)
    def resource(self):
        dialog = QDialog(self); dialog.setWindowTitle('Configure Tool / Resource'); form = QFormLayout(dialog)
        values = self.window.store.local.setdefault('organization_resources', [])
        pick = QComboBox(); pick.addItem('Add new resource', -1)
        for i, resource in enumerate(values): pick.addItem(resource['name'], i)
        form.addRow('Resource', pick)
        name, target, category = QLineEdit(), QLineEdit(), QLineEdit(); favorite = QCheckBox('Favorite')
        for label, control in (('Name', name), ('Executable path or https URL', target), ('Category', category), ('Quick access', favorite)): form.addRow(label, control)
        def populate():
            index = pick.currentData(); value = values[index] if index >= 0 else {}
            name.setText(value.get('name', '')); target.setText(value.get('target', '')); category.setText(value.get('category', 'Project Resources')); favorite.setChecked(value.get('favorite', False))
        pick.currentIndexChanged.connect(populate); populate()
        error = QLabel(); form.addRow(error)
        def save():
            if not name.text().strip() or not category.text().strip(): error.setText('Enter a name and category.'); return
            value = target.text().strip()
            if not value.startswith(('https://', 'http://')) and not Path(value).is_file(): error.setText('Choose an existing local executable/file or an https URL.'); return
            record = dict(name=name.text().strip(), category=category.text().strip(), target=value, favorite=favorite.isChecked())
            if pick.currentData() >= 0: values[pick.currentData()] = record
            else: values.append(record)
            self.window.store.save_local(); self.reload(); dialog.accept()
        controls = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); controls.accepted.connect(save); controls.rejected.connect(dialog.reject); form.addRow(controls); dialog.exec()
