"""Native responsive context and browsing primitives; no extra UI dependency."""
import math
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QTextBrowser, QWidget, QGridLayout, QStyledItemDelegate,
    QToolTip, QAbstractItemView, QPushButton, QStyleOptionButton, QStylePainter, QStyle)


class ContextBrowser(QTextBrowser):
    """Grow with actual text/font; retain a scrollbar for exceptionally long context."""
    def __init__(self):
        super().__init__()
        self.document().documentLayout().documentSizeChanged.connect(self.fit_context)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAccessibleName('Project context and linked records')

    def fit_context(self, *_):
        metrics = self.fontMetrics(); line = metrics.lineSpacing()
        wanted = math.ceil(self.document().size().height()) + 12
        height = max(line * 3 + 12, min(wanted, line * 8 + 12))
        if self.height() != height: self.setFixedHeight(height)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange:
            self.document().setDefaultFont(self.font()); self.fit_context()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.document().setTextWidth(max(80, self.viewport().width()))
        self.fit_context()


class ContextGrid(QWidget):
    def __init__(self, cards, maximum=3):
        super().__init__(); self.cards = cards; self.maximum = maximum; self.columns = 0
        self.grid = QGridLayout(self); self.grid.setContentsMargins(0, 0, 0, 0); self.grid.setSpacing(12)
        self.reflow()

    def reflow(self):
        minimum = max(280, QFontMetrics(self.font()).horizontalAdvance('Current priority & upcoming work') + 40)
        columns = max(1, min(self.maximum, self.width() // minimum))
        if columns == self.columns: return
        for card in self.cards: self.grid.removeWidget(card)
        for i, card in enumerate(self.cards): self.grid.addWidget(card, i // columns, i % columns)
        for i in range(self.maximum): self.grid.setColumnStretch(i, 1 if i < columns else 0)
        self.columns = columns

    def resizeEvent(self, event): super().resizeEvent(event); self.reflow()


class FullValueDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index); option.textElideMode = Qt.ElideMiddle

    def helpEvent(self, event, view, option, index):
        if index.isValid():
            QToolTip.showText(event.globalPos(), str(index.data(Qt.DisplayRole) or ''), view)
            return True
        return super().helpEvent(event, view, option, index)


def prepare_table(table, name):
    table.setAccessibleName(name); table.setTextElideMode(Qt.ElideMiddle)
    table.setItemDelegate(FullValueDelegate(table))
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setSectionsMovable(True)
    table.horizontalHeader().setMinimumSectionSize(70)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setWordWrap(False)


class AccountButton(QPushButton):
    """Keep the complete identity accessible while eliding only painted text."""
    def setText(self, text):
        super().setText(text); self.setToolTip(text); self.setAccessibleName(text)

    def sizeHint(self):
        hint = super().sizeHint(); hint.setWidth(min(420, hint.width() + 20)); return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint(); hint.setWidth(140); return hint

    def paintEvent(self, event):
        option = QStyleOptionButton(); self.initStyleOption(option)
        option.text = self.fontMetrics().elidedText(self.text(), Qt.ElideMiddle, max(0, self.width() - 40))
        painter = QStylePainter(self); painter.drawControl(QStyle.CE_PushButton, option)
