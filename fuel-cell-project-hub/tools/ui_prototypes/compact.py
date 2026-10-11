"""Command Center: compact commands, searchable canonical worklist."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView
from .common import PrototypeHome, heading, CARD_NAMES


class CommandCenter(PrototypeHome):
    def __init__(self, window):
        super().__init__(window)
        self.header(); self.body.addLayout(self.categories())
        self.body.addLayout(self.utilities()); self.body.addLayout(self.quick(True))
        self.body.addWidget(self.notifications)
        for _, view in self.cards.values(): view.setFixedHeight(75)
        self.body.addLayout(self.grid((CARD_NAMES[0], CARD_NAMES[2], CARD_NAMES[3])))
        panel, view = self.cards[CARD_NAMES[1]]; view.hide()
        self.work_filter = QLineEdit(); self.work_filter.setPlaceholderText('Filter work by ID, owner, title or state')
        self.work_filter.setAccessibleName('Canonical worklist filter'); panel.layout().addWidget(self.work_filter)
        self.work_table = QTableWidget(0, 4); self.work_table.setHorizontalHeaderLabels(('ID / Type', 'Work item', 'Owner / State', 'Due'))
        self.work_table.setEditTriggers(QTableWidget.NoEditTriggers); self.work_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.work_table.setSortingEnabled(True); self.work_table.setMinimumHeight(155)
        self.work_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.work_table.cellDoubleClicked.connect(lambda row, col: self.open_record(self.work_table.item(row, 0).data(Qt.UserRole)))
        self.work_filter.textChanged.connect(self.filter_work)
        panel.layout().addWidget(self.work_table); self.body.addWidget(panel)
        self.body.addLayout(self.grid((CARD_NAMES[4], CARD_NAMES[5]), 2)); self.finish()

    def reload(self):
        super().reload()
        if not hasattr(self, 'work_table'): return
        people = {p['id']: p['display_name'] for p in self.service.accounts.users()}
        rows = [r for r in self.service.rows() if r['kind'] in ('goal', 'task', 'deliverable')]
        self.work_table.setSortingEnabled(False); self.work_table.setRowCount(len(rows))
        for i, record in enumerate(rows):
            f = record['fields']; values = (record['id'] + ' / ' + record['kind'], record['title'],
                people.get(f.get('owner_id'), 'Unassigned') + ' / ' + f.get('submission_status', f.get('status', 'To Do')), f.get('due_date', 'Period deadline'))
            for j, value in enumerate(values):
                item = QTableWidgetItem(value); item.setToolTip(value); item.setData(Qt.UserRole, record['uuid']); self.work_table.setItem(i, j, item)
        self.work_table.setSortingEnabled(True); self.filter_work()

    def filter_work(self):
        query = self.work_filter.text().casefold()
        for row in range(self.work_table.rowCount()):
            text = ' '.join(self.work_table.item(row, col).text() for col in range(4)).casefold()
            self.work_table.setRowHidden(row, query not in text)
