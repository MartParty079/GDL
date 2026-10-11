"""Structured Sidebar: persistent category rail beside the work area."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from .common import PrototypeHome, heading, CARD_NAMES


class StructuredSidebar(PrototypeHome):
    def __init__(self, window):
        super().__init__(window)
        self.header()
        row = QHBoxLayout(); row.setSpacing(20)
        rail = QWidget(); rail.setObjectName('sidebar'); rail.setFixedWidth(210)
        side = QVBoxLayout(rail); side.setContentsMargins(12, 12, 12, 12)
        side.addWidget(heading('Project sections', 'muted')); side.addLayout(self.categories(True))
        side.addSpacing(18); side.addWidget(heading('Workspace utilities', 'muted'))
        side.addLayout(self.utilities(True)); side.addStretch(); row.addWidget(rail)
        work = QVBoxLayout(); work.setSpacing(12)
        work.addWidget(self.notifications); work.addWidget(heading('Current priority & upcoming work'))
        work.addLayout(self.grid((CARD_NAMES[0], CARD_NAMES[4], CARD_NAMES[3])))
        work.addLayout(self.grid((CARD_NAMES[2], CARD_NAMES[1]), 2))
        work.addWidget(heading('Quick Start')); work.addLayout(self.quick())
        # Health remains available, but doesn't compete with the current priority.
        work.addWidget(self.cards[CARD_NAMES[5]][0]); work.addWidget(self.detail_tabs)
        row.addLayout(work, 1); self.body.addLayout(row); self.body.addStretch(); self.reload()
