"""Reusable Hub components, feedback, and one restrained line-icon family."""
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QFrame,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy, QLineEdit, QProgressBar, QCheckBox, QLayout)

from app.ui.theme import Theme, repolish

ICONS = {
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "files": '<path d="M14 3H5v18h14V8z"/><path d="M14 3v6h5M8 13h8M8 17h6"/>',
    "storage": '<path d="M3 7h7l2 2h9v11H3z"/><path d="M3 7V4h7l2 3"/>',
    "software": '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "reports": '<path d="M5 3h14v18H5zM8 16v-3M12 16V8M16 16v-5"/>',
    "goal": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "plan": '<path d="M9 6h12M9 12h12M9 18h12M3 6l1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h3M14 14h3M7 18h3"/>',
    "activity": '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    "links": '<path d="M10 14l4-4M8 16l-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M16 8l2-2a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" transform="translate(1 0) scale(.9)"/>',
    "search": '<circle cx="10" cy="10" r="6"/><path d="M15 15l6 6"/>',
    "bug": '<rect x="7" y="7" width="10" height="13" rx="5"/><path d="M9 7V4M15 7V4M3 10h4M17 10h4M3 16h4M17 16h4M12 8v11"/>',
    "history": '<path d="M3 9a9 9 0 1 1 0 6M3 3v6h6M12 7v6l4 2"/>',
}


def icon(name, color=None):
    renderer = QSvgRenderer(f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color or Theme.TEXT_SECONDARY}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, ICONS["files"])}</svg>'.encode())
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def label(value, kind="body"):
    widget = QLabel(value)
    widget.setWordWrap(kind not in ("heading", "title", "eyebrow"))
    widget.setTextFormat(Qt.PlainText)
    widget.setProperty("kind", kind)
    widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


class Button(QPushButton):
    def __init__(self, caption, callback=None, primary=False, variant="secondary"):
        super().__init__(caption.replace("&", "&&"))
        self.setProperty("primary", primary)
        self.setProperty("variant", "primary" if primary else variant)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setAccessibleName(caption)
        if callback:
            self.clicked.connect(callback)
        self.saved_caption = caption.replace("&", "&&")

    def set_loading(self, loading, caption="Working…"):
        self.setText(caption if loading else self.saved_caption)
        self.setEnabled(not loading)
        self.setProperty("loading", loading)
        repolish(self)


def button(caption, callback, primary=False):
    return Button(caption, callback, primary)


class StatusPill(QLabel):
    def __init__(self, caption="", tone="neutral"):
        super().__init__()
        self.setProperty("component", "pill")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.set_status(caption, tone)

    def set_status(self, caption, tone="neutral"):
        self.setText(caption)
        self.setProperty("tone", tone)
        repolish(self)


class InlineMessage(QLabel):
    def __init__(self, value="", tone="info"):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setWordWrap(True)
        self.setTextFormat(Qt.PlainText)
        self.setProperty("component", "message")
        self.set_message(value, tone)

    def set_message(self, value, tone="info"):
        self.setText(value)
        self.setProperty("tone", tone)
        self.setVisible(bool(value))
        repolish(self)


class AppCard(QFrame):
    def __init__(self, title="", body="", icon_name=None):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        if title:
            heading = QHBoxLayout()
            if icon_name:
                image = QLabel()
                image.setPixmap(icon(icon_name, Theme.ACCENT_HOVER).pixmap(20, 20))
                heading.addWidget(image)
            self.title_label = label(title, "cardTitle")
            heading.addWidget(self.title_label, 1)
            layout.addLayout(heading)
        if body:
            self.body_label = label(body)
            layout.addWidget(self.body_label)
        layout.setAlignment(Qt.AlignTop)


def card(title, body, icon_name=None):
    return AppCard(title, body, icon_name)


class SectionHeader(QWidget):
    def __init__(self, title, description="", action=None):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        titles = QVBoxLayout()
        titles.addWidget(label(title, "heading"))
        if description:
            titles.addWidget(label(description, "muted"))
        row.addLayout(titles, 1)
        if action:
            row.addWidget(action)


class EmptyState(AppCard):
    def __init__(self, title, description, caption=None, callback=None, icon_name="files"):
        super().__init__(title, description, icon_name)
        self.title = title
        self.setObjectName("emptyState")
        self.state_callback = callback
        if caption and callback:
            self.state_button = Button(caption, self.activate, True)
            self.layout().addWidget(self.state_button, alignment=Qt.AlignLeft)

    def activate(self):
        if self.state_callback:
            self.state_callback()

    def set_state(self, title, description, caption, callback):
        self.title = title
        self.title_label.setText(title)
        self.body_label.setText(description)
        self.state_button.setText(caption)
        self.state_button.setAccessibleName(caption)
        self.state_callback = callback


class SkeletonLine(QFrame):
    def __init__(self, width=180, height=12):
        super().__init__()
        self.setObjectName("skeletonLine")
        self.setFixedHeight(height)
        self.setMaximumWidth(width)
        self.setMinimumWidth(min(80, width))
        self.setAccessibleName("Loading")


class SkeletonCard(AppCard):
    def __init__(self, description="Loading…"):
        super().__init__()
        self.layout().addWidget(label(description, "muted"))
        for width in (200, 300, 240):
            self.layout().addWidget(SkeletonLine(width))


class SkeletonTable(AppCard):
    def __init__(self, rows=5):
        super().__init__("Loading files", "Reading the local index…")
        for _ in range(rows):
            row = QHBoxLayout()
            for width in (180, 90, 160, 120):
                row.addWidget(SkeletonLine(width, 22))
            self.layout().addLayout(row)


class SearchField(QLineEdit):
    def __init__(self, caption):
        super().__init__()
        self.setPlaceholderText(caption)
        self.setAccessibleName(caption)
        self.setClearButtonEnabled(True)
        self.addAction(icon("search"), QLineEdit.LeadingPosition)


class ToggleSwitch(QCheckBox):
    def __init__(self, caption):
        super().__init__(caption)
        self.setMinimumHeight(40)
        self.setAccessibleName(caption)
        self.setProperty("component", "toggle")


class ResponsiveCards(QWidget):
    def __init__(self, cards):
        super().__init__()
        self.cards = cards
        self.grid = QGridLayout(self)
        self.grid.setSizeConstraint(QLayout.SetMinimumSize)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.columns = 0
        self.reflow(2)

    def reflow(self, columns):
        if self.columns == columns:
            return
        for widget in self.cards:
            self.grid.removeWidget(widget)
        for i, widget in enumerate(self.cards):
            self.grid.addWidget(widget, i // columns, i % columns)
        for i in range(3):
            self.grid.setColumnStretch(i, 1 if i < columns else 0)
        self.columns = columns

    def resizeEvent(self, event):
        self.reflow(2 if self.width() >= 650 else 1)
        super().resizeEvent(event)


def friendly_error(error, context="complete this action"):
    message = str(error)
    lowered = message.lower()
    if 'admin approval' in lowered:
        return 'Admin approval required for this cloud feature. Local OneDrive and cached indexes remain usable.'
    if 'aadsts' in lowered or 'consent_required' in lowered or 'access_token' in lowered or 'error_description' in lowered:
        return 'Microsoft access is unavailable. Retry basic sign-in or continue with Local OneDrive.'
    if "permission" in lowered or "access is denied" in lowered or "winerror 5" in lowered:
        return "Access was denied. Check the folder permissions or close the app using this file, then retry."
    if "unavailable" in lowered or "not found" in lowered or "missing" in lowered or "no such file" in lowered:
        return "The saved location or application is unavailable. Check OneDrive or locate it again, then retry."
    if "json" in lowered or "schema" in lowered or "metadata" in lowered or "cache" in lowered:
        return "The project data could not be read safely. Existing data was preserved. Check the metadata or restore a valid version, then retry."
    if "url" in lowered or "http" in lowered or "address" in lowered:
        return "Check the web address in Settings, then retry. Use a complete https:// address."
    if "timed out" in lowered or "network" in lowered or "urlopen" in lowered or "resolve" in lowered:
        return "The online service could not be reached. Check your connection and retry; local project work is still available."
    if "settings changed" in lowered or "reconnect" in lowered:
        return "Shared settings changed since they were loaded. Reconnect storage before applying your edits."
    if "winerror" in lowered or "errno" in lowered or "traceback" in lowered:
        return "The action could not be completed. Check the location and permissions, then retry."
    return message if len(message) < 260 else "The action could not be completed. Review the details and retry."


class ErrorBanner(AppCard):
    def __init__(self):
        super().__init__()
        self.heading = label("", "cardTitle")
        self.message = InlineMessage("", "error")
        self.details = label("", "muted")
        self.details.hide()
        self.details_button = Button("Show details", self.toggle_details, variant="quiet")
        self.layout().addWidget(self.heading)
        self.layout().addWidget(self.message)
        self.layout().addWidget(self.details_button, alignment=Qt.AlignLeft)
        self.layout().addWidget(self.details)
        self.hide()

    def show_error(self, title, error):
        self.heading.setText(title)
        self.message.set_message(friendly_error(error), "error")
        raw = str(error)
        self.details.setText(friendly_error(error) if any(value in raw.lower() for value in ('aadsts', 'consent_required', 'access_token', 'error_description')) else raw)
        self.details.hide()
        self.details_button.setText("Show details")
        self.show()

    def toggle_details(self):
        visible = not self.details.isVisible()
        self.details.setVisible(visible)
        self.details_button.setText("Hide details" if visible else "Show details")


def local_datetime(value):
    if not value:
        return "Not yet"
    try:
        instant = datetime.fromisoformat(value).astimezone()
        return instant.strftime("%b %d, %Y · %I:%M %p").replace(" 0", " ")
    except (ValueError, TypeError):
        return "Date unavailable"


class ToastManager(QWidget):
    """One nonmodal, timed notification surface per window."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toastHost")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.message = InlineMessage()
        self.layout_box.addWidget(self.message)
        self.setMinimumWidth(360)
        self.setMaximumWidth(520)
        self.hide()

    def notify(self, caption, tone="info", timeout=5000):
        self.message.set_message(caption, tone)
        self.adjustSize()
        self.move(max(16, self.parentWidget().width() - self.width() - 32), max(16, self.parentWidget().height() - self.height() - 32))
        self.show()
        self.raise_()
        self.timer.start(timeout)


def notify(widget, caption, tone="info"):
    manager = getattr(widget.window(), "toasts", None)
    if manager:
        manager.notify(caption, tone)
