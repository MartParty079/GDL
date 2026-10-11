"""Quiet Workspace: horizontal navigation, balanced project context."""
from .common import PrototypeHome, heading, CARD_NAMES


class QuietWorkspace(PrototypeHome):
    def __init__(self, window):
        super().__init__(window)
        self.header(); self.body.addLayout(self.utilities())
        self.body.addLayout(self.categories()); self.body.addWidget(heading('Quick Start'))
        self.body.addLayout(self.quick()); self.body.addWidget(self.notifications)
        order = (CARD_NAMES[0], CARD_NAMES[2], CARD_NAMES[3], CARD_NAMES[1], CARD_NAMES[4], CARD_NAMES[5])
        self.body.addLayout(self.grid(order)); self.finish()
