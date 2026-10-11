"""Owner-selected Structured Sidebar composition using existing Home handlers."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QFrame, QTextBrowser, QComboBox, QLineEdit,
    QTabWidget, QPushButton, QMessageBox, QSizePolicy)
from app.ui.components import button
from app.ui.flow_layout import FlowLayout
from app.services.organization import CATEGORIES

CARD_NAMES = ('Current Goal', 'Progress and Near-Term Plan', 'Next Meeting & Agenda',
              'Schedule & Biweekly Due', 'Active Procedure & Parameters', 'Project Repository')
QUICK = (('New Experiment', 'experiment'), ('Register Sample', 'sample'),
         ('Procedure', 'procedure'), ('Research Reference', 'research'),
         ('New Design', 'design'), ('New Meeting', 'meeting'),
         ('Biweekly Submission', 'deliverable'))


def heading(text, kind='section'):
    value = QLabel(text); value.setProperty('kind', {'heading': 'heading', 'section': 'section', 'muted': 'muted'}[kind]); value.setWordWrap(True)
    return value


class HomeLayoutMixin:
    """Only composition differs. Methods and authoritative records are unchanged."""
    def build_home(self):
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget(); self.body = QVBoxLayout(page)
        self.body.setContentsMargins(16, 12, 16, 16); self.body.setSpacing(12)
        self.setWidget(page)
        self.title = heading('Project Home', 'heading')
        self.stage = heading('', 'muted'); self.notifications = heading('', 'muted')
        self.cards = {}
        for name in CARD_NAMES:
            frame = QFrame(); frame.setObjectName('card')
            layout = QVBoxLayout(frame); layout.setContentsMargins(12, 10, 12, 10); layout.setSpacing(5)
            layout.setAlignment(Qt.AlignTop)
            layout.addWidget(heading(name))
            from app.ui.workspace_components import ContextBrowser
            view = ContextBrowser(); view.setOpenLinks(False); view.setFrameShape(QFrame.NoFrame)
            view.setMinimumWidth(0)
            view.anchorClicked.connect(lambda url: self.open_record(url.toString()))
            layout.addWidget(view); self.cards[name] = frame, view
        self.category_buttons = []
        for name in CATEGORIES:
            control = button(name, lambda checked=False, c=name: self.navigate(c))
            control.setObjectName('primary-category'); control.setAccessibleName(name)
            control.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.category_buttons.append(control)
        self.build_details()
        self.header()
        self.body.addWidget(self.notifications)
        self.body.addWidget(heading('Quick Start'))
        self.body.addLayout(self.quick())
        self.body.addWidget(heading('Current priority & upcoming work'))
        from app.ui.workspace_components import ContextGrid
        self.body.addWidget(ContextGrid([self.cards[name][0] for name in (CARD_NAMES[0], CARD_NAMES[4], CARD_NAMES[3])], 3))
        self.body.addWidget(ContextGrid([self.cards[name][0] for name in (CARD_NAMES[2], CARD_NAMES[1])], 2))
        self.body.addWidget(self.cards[CARD_NAMES[5]][0])
        self.finish()

    def header(self):
        row = QHBoxLayout(); row.addWidget(self.title); row.addStretch()
        row.addWidget(heading('Canonical project records', 'muted'))
        self.body.addLayout(row); self.body.addWidget(self.stage)

    def quick(self, compact=False):
        layout = FlowLayout(spacing=8)
        if compact:
            self.command = QComboBox(); self.command.setAccessibleName('Quick Start operation')
            for text, kind in QUICK: self.command.addItem(text, kind)
            self.command.addItem('Upload Files', 'upload')
            layout.addWidget(self.command)
            layout.addWidget(button('Run Selected', lambda: self.panel.upload() if self.command.currentData() == 'upload' else self.create(self.command.currentData())))
            for text, kind in QUICK[:2] + QUICK[-1:]:
                layout.addWidget(button(text, lambda checked=False, k=kind: self.create(k)))
        else:
            for text, kind in QUICK:
                layout.addWidget(button(text, lambda checked=False, k=kind: self.create(k)))
        layout.addWidget(button('Upload Files', self.panel.upload))
        return layout

    def build_details(self):
        """Keep less-frequent Home tools together without obscuring the primary actions."""
        self.detail_tabs = QTabWidget(); self.detail_tabs.setAccessibleName('Additional Home tools')
        activity = QWidget(); layout = QVBoxLayout(activity); layout.setContentsMargins(8, 4, 8, 4)
        filters = FlowLayout(spacing=8)
        self.person = QComboBox(); self.person.addItem('Every contributor', '')
        for person in self.service.accounts.users(): self.person.addItem(person['display_name'], person['id'])
        self.area = QComboBox(); self.area.addItem('Every work area', ''); self.area.addItems(CATEGORIES)
        self.action = QComboBox(); self.action.addItems(('Every action', 'Upload', 'Update', 'Request'))
        self.file_type = QLineEdit(); self.file_type.setPlaceholderText('Extension')
        self.after = QLineEdit(); self.after.setPlaceholderText('Since YYYY-MM-DD')
        for control, name in ((self.person, 'Contributor filter'), (self.area, 'Work area filter'),
            (self.action, 'Action filter'), (self.file_type, 'File extension filter'), (self.after, 'Activity start date')):
            control.setAccessibleName(name); control.setMaximumWidth(180); filters.addWidget(control)
        filters.addWidget(button('Apply', self.activity_rows)); filters.addWidget(button('Clear', self.clear_filters))
        layout.addLayout(filters)
        self.events = QTextBrowser(); self.events.setOpenLinks(False); self.events.setMinimumHeight(90)
        self.events.anchorClicked.connect(lambda url: self.open_record(url.toString())); layout.addWidget(self.events)
        self.detail_tabs.addTab(activity, 'Recent Activity')
        resources = QWidget(); layout = QVBoxLayout(resources)
        self.recent = QComboBox(); self.recent.setAccessibleName('Recent record')
        row = QHBoxLayout(); row.addWidget(self.recent, 1)
        row.addWidget(button('Open Record', lambda: self.open_record(self.recent.currentData()))); layout.addLayout(row)
        self.tools = QComboBox(); self.tools.setAccessibleName('Configured tool or resource')
        row = QHBoxLayout(); row.addWidget(self.tools, 1); row.addWidget(button('Open Selected', self.open_tool)); layout.addLayout(row)
        row = FlowLayout(spacing=8); row.addWidget(button('Configure Resource', self.resource))
        row.addWidget(button('Software Paths & Status', lambda: self.window.show_page('Software')))
        row.addWidget(button('New Goal', lambda: self.create('goal'))); row.addWidget(button('New Task', lambda: self.create('task')))
        row.addWidget(button('Draft Meeting Summary', self.summary)); row.addWidget(button('Two-Week Digest', self.digest))
        if self.service.accounts.admin_unlocked: row.addWidget(button('Configure Periods', self.periods))
        layout.addLayout(row); self.detail_tabs.addTab(resources, 'Recent Work & Tools')
        self.detail_tabs.setMinimumHeight(185)

    def finish(self):
        self.body.addWidget(self.detail_tabs); self.body.addStretch(); self.reload()
        self.stage.setWordWrap(True)
