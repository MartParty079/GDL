"""Persistent four-category rail and native utility navigation."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QButtonGroup, QMenu, QToolButton, QSizePolicy, QGridLayout)
from app.edition import APP_NAME, CHANNEL
from app.ui.components import button, label


class WorkspaceHeader(QWidget):
    """A second header row at narrow widths or enlarged text; no transition."""
    def __init__(self, window, identity, controls):
        super().__init__(); self.window = window; self.identity = identity; self.controls = controls
        self.grid = QGridLayout(self); self.grid.setContentsMargins(0, 0, 0, 0)
        self.stacked = None; self.reflow()

    def reflow(self):
        stacked = self.width() < 1100 or self.fontMetrics().height() > 22
        if stacked == self.stacked: return
        self.grid.removeWidget(self.identity); self.grid.removeWidget(self.controls)
        self.grid.addWidget(self.identity, 0, 0)
        self.grid.addWidget(self.controls, 1 if stacked else 0, 0 if stacked else 1)
        self.grid.setColumnStretch(0, 1); self.grid.setColumnStretch(1, 0)
        self.stacked = stacked

    def resizeEvent(self, event): super().resizeEvent(event); self.reflow()

    def refresh_health(self):
        status = self.window.organization_panel.service.status
        warning = self.window.account_service.warning
        caution = any(word in (status + warning).lower() for word in ('offline', 'stale', 'conflict', 'pending', 'not initialized'))
        compact = status.split(' · ', 1)[0]
        if 'possibly stale' in status.lower() and 'stale' not in compact.lower():
            compact += ' · Possibly stale until OneDrive sync completes'
        self.window.banner.set_message(CHANNEL.upper() + ' · ' + compact + (' · Activity sync needs review' if warning else ''), 'warning' if caution else 'info')
        self.window.banner.setToolTip(status + ('\n' + warning if warning else ''))
        self.window.banner.setAccessibleName('Shared index status: ' + status)


class WorkspaceRail(QScrollArea):
    def __init__(self, window):
        super().__init__(window); self.window = window
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget(); page.setObjectName('sidebar'); layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(8); self.setWidget(page)
        self.home = button('Home', lambda: self.go_home()); layout.addWidget(self.home)
        layout.addWidget(label('PROJECT SECTIONS', 'eyebrow'))
        self.group = QButtonGroup(self)
        for control in window.home_panel.category_buttons:
            control.setProperty('variant', 'sidebar'); control.setCheckable(True); self.group.addButton(control); layout.addWidget(control)
        layout.addSpacing(16); layout.addWidget(label('WORKSPACE', 'eyebrow'))
        for text, action in (('My Workspace', window.home_panel.workspace), ('Activity', window.home_panel.activity),
                             ('Weekly Reports', lambda: window.tabs.setCurrentWidget(window.weekly_panel)),
                             ('Files & Analysis', lambda: window.show_page('Project')),
                             ('Software & Resources', lambda: window.show_page('Software')),
                             ('Settings', window.home_panel.settings)):
            layout.addWidget(button(text, action))
        if window.account_service.admin_unlocked:
            layout.addSpacing(16); layout.addWidget(label('ADMINISTRATION', 'eyebrow'))
            layout.addWidget(button('Team & Activity Audit', window.home_panel.administration))
            layout.addWidget(button('Index Maintenance', lambda: window.tabs.setCurrentWidget(window.organization_panel)))
        layout.addStretch(); layout.addWidget(label('Local team identity\nOneDrive controls file access', 'muted'))
        window.tabs.currentChanged.connect(self.route_changed)
        window.organization_panel.category.currentTextChanged.connect(self.route_changed)
        window.organization_panel.subsection.currentTextChanged.connect(self.route_changed)
        self.route_changed()

    def go_home(self):
        self.window.home_panel.reload(); self.window.tabs.setCurrentWidget(self.window.home_panel)

    def route_changed(self, *_):
        window = self.window; page = window.tabs.currentWidget()
        organization = page is window.organization_panel
        self.group.setExclusive(False)
        for control in window.home_panel.category_buttons:
            control.setChecked(organization and control.text().replace('&&', '&') == window.organization_panel.category.currentText())
        self.group.setExclusive(True)
        if organization:
            text = window.organization_panel.category.currentText() + ' / ' + window.organization_panel.subsection.currentText()
        else: text = 'Home' if page is window.home_panel else window.tabs.tabText(window.tabs.currentIndex())
        window.workspace_breadcrumb.setText(text); window.workspace_breadcrumb.setToolTip(text)
        self.home.setProperty('primary', page is window.home_panel)
        from app.ui.theme import repolish
        repolish(self.home)
        if hasattr(window, 'workspace_header'): window.workspace_header.refresh_health()

    def resize_to_text(self):
        longest = max(self.fontMetrics().horizontalAdvance(c.text().replace('&&', '&')) for c in self.window.home_panel.category_buttons)
        self.setFixedWidth(max(220, longest + 58))


def install_workspace_navigation(window):
    outer = window.centralWidget().layout(); old = outer.takeAt(0).layout()
    # Keep real account controls; remove the old crowded header composition.
    def hide(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().hide()
            elif item.layout(): hide(item.layout())
    account = window.findChild(QPushButton, 'current-user'); hide(old)
    identity_widget = QWidget(); identity = QVBoxLayout(identity_widget); identity.setContentsMargins(0, 0, 0, 0)
    controls_widget = QWidget(); header = QHBoxLayout(controls_widget); header.setContentsMargins(0, 0, 0, 0)
    identity.addWidget(label(APP_NAME, 'eyebrow'))
    window.workspace_breadcrumb = label('Home', 'cardTitle'); identity.addWidget(window.workspace_breadcrumb)
    window.global_search.setAccessibleName('Search all research files')
    window.global_search.setMinimumWidth(220); window.global_search.setMaximumWidth(360); header.addWidget(window.global_search); window.global_search.show()
    header.addWidget(account); account.show()
    more = QToolButton(); more.setText('About / Updates'); more.setPopupMode(QToolButton.InstantPopup)
    menu = QMenu(more)
    from app.ui.research_workspace import version_dialog
    menu.addAction('About / Version History', lambda: version_dialog(window))
    menu.addAction('Check for Updates', window.show_update_dialog)
    menu.addAction('My Settings', window.home_panel.settings)
    menu.addAction('App Activity & Diagnostics', lambda: window.show_page('Activity'))
    menu.addAction('Bug Reports', lambda: window.show_page('Bugs'))
    menu.addAction('Attendance & Participation', lambda: window.tabs.setCurrentWidget(window.meetings_panel))
    more.setMenu(menu); header.addWidget(more)
    window.workspace_header = WorkspaceHeader(window, identity_widget, controls_widget)
    outer.insertWidget(0, window.workspace_header)
    window.tabs.tabBar().hide(); outer.removeWidget(window.tabs)
    row = QHBoxLayout(); row.setSpacing(16)
    window.workspace_rail = WorkspaceRail(window); row.addWidget(window.workspace_rail)
    row.addWidget(window.tabs, 1); outer.addLayout(row, 1)
    outer.setContentsMargins(16, 12, 16, 12); outer.setSpacing(8)
    window.workspace_rail.resize_to_text()
    window.workspace_header.refresh_health()
