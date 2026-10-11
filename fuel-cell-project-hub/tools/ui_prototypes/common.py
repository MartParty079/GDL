"""Native prototype components; reuse all existing Home workflow handlers."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QFrame, QTextBrowser, QComboBox, QLineEdit,
    QTabWidget, QPushButton, QMessageBox, QSizePolicy)
from app.ui.home import HomePanel, button
from app.ui.flow_layout import FlowLayout
from app.services.organization import CATEGORIES

TOKENS = dict(spacing=(4, 8, 12, 16, 24, 32), font=(12, 13, 14, 18, 24),
              radius=(6, 10), background='#F5F6F8', surface='#FFFFFF',
              text='#17212F', muted='#526174', border='#D5DCE5',
              accent='#0067C0', motion_ms=0)

# Prototype-local tokens. No changes to the app's stylesheet or appearance settings.
STYLE = '''
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #17212F; }
QPushButton { padding: 7px 12px; min-height: 18px; border-radius: 6px; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid #0067C0; }
QPushButton:pressed { background: #D8EAFA; }
QPushButton[primary="true"] { background: #0067C0; color: white; }
QFrame#card { background: white; border: 1px solid #D5DCE5; border-radius: 10px; }
QLabel[proto="heading"] { font-size: 24px; font-weight: 600; }
QLabel[proto="section"] { font-size: 14px; font-weight: 600; }
QLabel[proto="muted"] { font-size: 12px; color: #526174; }
QPushButton#primary-category { padding: 9px 14px; font-weight: 600; }
QTextBrowser { background: white; border: none; selection-background-color: #D8EAFA; }
'''

CARD_NAMES = ('Current Goal', 'Progress and Near-Term Plan', 'Next Meeting & Agenda',
              'Schedule & Biweekly Due', 'Active Procedure & Parameters', 'Project Repository')
QUICK = (('New Experiment', 'experiment'), ('Register Sample', 'sample'),
         ('Procedure', 'procedure'), ('Research Reference', 'research'),
         ('New Design', 'design'), ('New Meeting', 'meeting'),
         ('Biweekly Submission', 'deliverable'))


def heading(text, kind='section'):
    value = QLabel(text); value.setProperty('proto', kind); value.setWordWrap(True)
    return value


def wrapper(layout):
    widget = QWidget(); widget.setLayout(layout); return widget


class PrototypeHome(HomePanel):
    """Only composition differs. Methods and authoritative records are unchanged."""
    def __init__(self, window):
        QScrollArea.__init__(self, window)
        self.window, self.panel = window, window.organization_panel
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(STYLE)
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
            view = QTextBrowser(); view.setOpenLinks(False); view.setFrameShape(QFrame.NoFrame)
            view.document().setDefaultStyleSheet('a { color: #0067C0; text-decoration: none; }')
            view.setMinimumWidth(0); view.setFixedHeight(94)
            view.anchorClicked.connect(lambda url: self.open_record(url.toString()))
            layout.addWidget(view); self.cards[name] = frame, view
        self.category_buttons = []
        for name in CATEGORIES:
            control = button(name, lambda checked=False, c=name: self.navigate(c))
            control.setObjectName('primary-category'); control.setAccessibleName(name)
            control.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.category_buttons.append(control)
        self.build_details()

    def header(self):
        row = QHBoxLayout(); row.addWidget(self.title); row.addStretch()
        row.addWidget(heading('Isolated preview · no production writes', 'muted'))
        self.body.addLayout(row); self.body.addWidget(self.stage)

    def utilities(self, vertical=False):
        layout = QVBoxLayout() if vertical else FlowLayout(spacing=8)
        for text, handler in (('My Workspace', self.workspace), ('Settings', self.settings),
                              ('Activity', self.activity), ('Account / PIN', self.account),
                              ('Refresh Index', self.sync)):
            layout.addWidget(button(text, handler))
        if self.service.accounts.admin_unlocked:
            layout.addWidget(button('Administration', self.administration))
        return layout

    def categories(self, vertical=False):
        layout = QVBoxLayout() if vertical else FlowLayout(spacing=8)
        for control in self.category_buttons: layout.addWidget(control)
        return layout

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

    def grid(self, names, columns=3):
        grid = QGridLayout(); grid.setSpacing(12)
        for i, name in enumerate(names): grid.addWidget(self.cards[name][0], i // columns, i % columns)
        for i in range(columns): grid.setColumnStretch(i, 1)
        return grid

    def build_details(self):
        """Complete less-frequent Home tools in tabs, not removed from variants."""
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
        row = QHBoxLayout(); row.addWidget(self.tools, 1); row.addWidget(button('Check Selected Launcher', self.open_tool)); layout.addLayout(row)
        row = FlowLayout(spacing=8); row.addWidget(button('Configure Resource', self.resource))
        row.addWidget(button('Software Paths & Status', lambda: self.window.show_page('Software')))
        row.addWidget(button('New Goal', lambda: self.create('goal'))); row.addWidget(button('New Task', lambda: self.create('task')))
        row.addWidget(button('Draft Meeting Summary', self.summary)); row.addWidget(button('Two-Week Digest', self.digest))
        if self.service.accounts.admin_unlocked: row.addWidget(button('Configure Periods', self.periods))
        layout.addLayout(row); self.detail_tabs.addTab(resources, 'Recent Work & Tools')
        self.detail_tabs.setMinimumHeight(185)

    def open_tool(self):
        # Exploration validates availability without starting scientific/external apps.
        selected = self.tools.currentData()
        if not selected: return
        caption = self.tools.currentText()
        QMessageBox.information(self, 'Prototype launcher check', caption +
            '\nConfigure paths through Software Paths & Status. External launches are disabled in this isolated design picker.')

    def finish(self):
        self.body.addWidget(self.detail_tabs); self.body.addStretch(); self.reload()
        self.stage.setText(self.stage.text() + ' · Representative fixture data')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Native minimum widths are bounded; long context stays selectable and scrollable.
        for _, view in self.cards.values(): view.setMinimumWidth(0)
