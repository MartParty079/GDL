import copy
import json
import platform
import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QScrollArea, QFrame, QGridLayout, QFileDialog, QMessageBox,
    QLineEdit, QTextEdit, QFormLayout, QComboBox, QDialog, QDialogButtonBox, QLayout)

from app import __version__
from app.edition import APP_NAME, BETA
from app.services.storage import write_json
from app.services.software import detect, valid_executable, launch, open_resource, LaunchType, launch_type
from app.services.updates import latest_release, cached_release, newer, verified_download, launch_installer
from app.ui.storage_panels import StoragePanel, FilesPanel
from app.ui.components import (label, button, card, Button, StatusPill, InlineMessage, EmptyState,
    SectionHeader, SkeletonCard, ErrorBanner, ToastManager, ResponsiveCards, icon, local_datetime,
    friendly_error, notify)
from app.ui.theme import apply_theme, Theme
from app.services.gdl_analysis import GDLAnalysisService
from app.services.path_registry import detect_dependency
from app.ui.gdl_panels import GDLPanel, GDLSettingsPanel
from app.services.storage_settings import StorageSettings
from app.ui.branding import application_icon


class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            self.done.emit(self.action())
        except Exception as exc:
            self.failed.emit(str(exc))


class HubWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.setWindowIcon(application_icon())
        self.store = store
        self.storage_settings = StorageSettings(store)
        store.storage_settings = self.storage_settings
        self.storage_panel = StoragePanel(store, self)
        from app.ui.research_panel import ResearchPanel
        self.research_panel = ResearchPanel(self.storage_settings, self, self.storage_panel)
        self.research_panel.changed.connect(self.storage_changed)
        self.research_panel.busy_changed.connect(self.storage_busy_changed)
        self.files_panel = FilesPanel(store, self)
        self.storage_panel.changed.connect(self.storage_changed)
        self.storage_panel.busy_changed.connect(self.storage_busy_changed)
        self.files_panel.connect_requested.connect(lambda: self.open_settings(1))
        self.results = {}
        self.workers = []
        self.scanning = False
        self.update_checking = False
        self.workspace_section = "Resources"
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 850)
        self.setMinimumSize(1024, 700)
        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(26, 22, 26, 20)
        top = QHBoxLayout()
        identity = QVBoxLayout()
        identity.addWidget(label(APP_NAME, "eyebrow"))
        identity.addWidget(label(self.storage_settings.locations.value["active"]["name"], "title"))
        top.addLayout(identity)
        top.addStretch()
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Search all research files...")
        self.global_search.setMaximumWidth(320)
        self.global_search.returnPressed.connect(self.search_workspace)
        top.addWidget(self.global_search)
        self.index_status = label("Index available" if self.storage_settings.catalog else "Storage not configured", "muted")
        top.addWidget(self.index_status)
        from app.ui.research_workspace import version_dialog
        top.addWidget(button("v" + __version__, lambda: version_dialog(self)))
        self.header_update = button("Updates", self.show_update_dialog)
        top.addWidget(self.header_update)
        outer.addLayout(top)
        self.banner = InlineMessage("Checking your system…", "info")
        outer.addWidget(self.banner)
        self.global_error = ErrorBanner()
        outer.addWidget(self.global_error)
        self.tabs = QTabWidget()
        self.pages = {}
        self.layouts = {}
        for name in ("Dashboard", "Activity", "Software", "Project", "Bugs", "Settings"):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setSizeConstraint(QLayout.SetMinimumSize)
            layout.setContentsMargins(4, 20, 4, 12)
            scroll.setWidget(page)
            if name == "Project":
                scroll.takeWidget()
                self.tabs.addTab(page, name)
                layout.setSizeConstraint(QLayout.SetDefaultConstraint)
                layout.setContentsMargins(0, 4, 0, 0)
            else:
                self.tabs.addTab(scroll, name)
            self.pages[name], self.layouts[name] = page, layout
        outer.addWidget(self.tabs)
        self.setCentralWidget(shell)
        self.apply_theme()
        self.toasts = ToastManager(self)
        self.gdl_service = GDLAnalysisService(store)
        self.gdl_settings = GDLSettingsPanel(self.gdl_service, self)
        self.gdl_panel = GDLPanel(self.gdl_service, self)
        self.render_dashboard()
        self.render_software()
        self.render_project()
        self.project_tabs.setCurrentIndex(1)
        self.show_page("Project")
        self.render_activity()
        self.render_bugs()
        self.render_settings()
        QTimer.singleShot(0, self.scan)
        QTimer.singleShot(200, self.check_updates_on_startup)
        from app.ui.update_recovery import UpdateRecovery
        from app.ui.update_installation import SafeUpdate
        self.update_recovery=UpdateRecovery(self)
        self.update_recovery.restore_settings()
        self.safe_update=SafeUpdate(self)

    def apply_theme(self):
        apply_theme(self)

    def reset(self, name):
        layout = self.layouts[name]
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        return layout

    def show_page(self, name):
        self.tabs.setCurrentIndex(list(self.pages).index(name))

    def guard(self, action):
        try:
            return action()
        except Exception as exc:
            self.global_error.show_error("Action could not be completed", exc)

    def work(self, action, done, failed=None):
        worker = Worker(action, self)
        self.workers.append(worker)
        worker.done.connect(done)
        worker.failed.connect(failed or (lambda message: self.global_error.show_error("Action failed", message)))
        worker.finished.connect(lambda: self.workers.remove(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def lifecycle(self, item):
        return self.store.project.get("software_lifecycle", {}).get(item["id"], item["lifecycle"])

    def missing(self):
        return [i for i in self.store.manifest if self.lifecycle(i) == "Required"
                and self.results.get(i["id"], {}).get("status") != "Ready"]

    def scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.banner.set_message("Checking your system… You can continue working while tools are detected.", "info")
        self.render_software()
        paths = copy.deepcopy(self.store.local["paths"])
        def scan_tools():
            results = {i["id"]: detect(i, paths.get(i["id"])) for i in self.store.manifest}
            for item_id, key in (("fiji", "fiji_executable"), ("jmp", "jmp_executable")):
                if not paths.get(item_id):
                    found = detect_dependency(self.store, key, self.gdl_service.registry.config["extra_search_roots"])
                    if found:
                        results[item_id] = {"path": found, "status": "Ready", "source": "Detected"}
            return results
        self.work(scan_tools, self.scan_done, self.scan_failed)

    def scan_failed(self, message):
        self.scanning = False
        self.banner.set_message("Software detection could not finish. Try scanning again.", "warning")
        self.global_error.show_error("Software detection unavailable", message)
        self.render_software()
        self.gdl_panel.validate()

    def scan_done(self, results):
        self.scanning = False
        # Keep explicit URI launch results through a re-scan in this session.
        # Never run a protocol merely to detect it.
        for item in self.store.manifest:
            previous = self.results.get(item["id"], {})
            current = results.get(item["id"], {})
            if (item.get("launch_type") == "uri" and previous.get("target") == current.get("target")
                    and previous.get("status") in ("Ready", "Launch failed")):
                results[item["id"]] = previous
        self.results = results
        missing = self.missing()
        self.banner.set_message(f"{len(missing)} required tools need setup. Open Software to configure them."
                            if missing else "All required tools are ready.", "warning" if missing else "success")
        self.render_dashboard()
        self.render_software()
        if not self.store.local.get("setup_complete"):
            self.show_page("Software")
        self.gdl_panel.validate()

    def render_dashboard(self):
        container = self.reset("Dashboard")
        workspace = QWidget()
        row = QHBoxLayout(workspace)
        row.setSizeConstraint(QLayout.SetMinimumSize)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(24)
        row.addWidget(self.workspace_sidebar("Overview"))
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        row.addWidget(body, 1)
        container.addWidget(workspace)
        p = self.store.project
        active_name = self.storage_settings.locations.value['active']['name'] if self.storage_settings.catalog else p.get("storage", {}).get("project_name", "Fuel cell capstone")
        layout.addWidget(SectionHeader("Overview", active_name,
            button("Open project repo", lambda: self.guard(lambda: open_resource(p["repository"])), True)))
        goal = card("Primary goal", p["goal"] or "Set the goal that guides the team's current work.", "goal")
        if p["supporting_goals"]:
            goal.layout().addWidget(label(p["supporting_goals"], "muted"))
        if not p["goal"]:
            goal.layout().addWidget(button("Set project goals", lambda: self.open_settings(0)))
        plan = card("Current plan", p["plan"] or "Add the next steps for your current work.", "plan")
        if not p["plan"]:
            plan.layout().addWidget(button("Add next steps", lambda: self.open_settings(0)))
        provider = self.store.provider
        storage_status = "Indexing" if self.storage_panel.indexing else provider.status() if provider else "Needs setup"
        if self.storage_settings.catalog:
            sources_available = all(s['status'] == 'Available' for s in self.storage_settings.locations.status())
            storage_status = 'Indexing' if self.research_panel.indexing else 'Connected' if sources_available else 'Unavailable'
        storage = card("Storage & index", "OneDrive / SharePoint", "storage")
        storage.layout().addWidget(StatusPill(storage_status, "success" if storage_status == "Connected" else "info" if storage_status == "Indexing" else "warning"))
        if self.storage_settings.catalog:
            summary = self.storage_settings.catalog.summary()
            available = all(s['status'] == 'Available' for s in self.storage_settings.locations.status())
            storage.layout().addWidget(label(f"Current Project Files: {summary['current']:,} · Legacy Indexed Files: {summary['legacy']:,}"))
            storage.layout().addWidget(label('Last indexed: ' + (local_datetime(summary['last_indexed']) if summary['last_indexed'] else 'Not indexed')))
            storage.layout().addWidget(label('Index Status: ' + ('Indexing' if self.research_panel.indexing else 'Ready' if available else 'Source unavailable · index preserved')))
            storage.layout().addWidget(label('Active Project: ' + Path(self.store.project_folder()).name + f" · Legacy Sources: {summary['sources'] - 1}"))
            for caption, origin in (('Current Project', 'current'), ('Legacy Data', 'legacy'), ('All Files', '')):
                storage.layout().addWidget(button(caption, lambda checked=False, value=origin: self.show_research_files(value)))
        elif provider and storage_status != "Unavailable":
            try:
                from app.ui.storage_panels import size_text
                summary = provider.summary()
                storage.layout().addWidget(label(f"{summary['files']:,} files · {size_text(summary['size'])}"))
                storage.layout().addWidget(label("Last indexed " + local_datetime(summary["last_index_time"]), "muted"))
            except (ValueError, OSError):
                storage.layout().addWidget(label("The index is unavailable. Reconnect storage to retry.", "muted"))
        else:
            storage.layout().addWidget(label("Connect your synced project library to browse files.", "muted"))
        storage.layout().addWidget(button("View storage" if provider or self.storage_settings.catalog else "Connect storage", lambda: self.open_settings(1)))
        if self.scanning and not self.results:
            tools = SkeletonCard("Checking your system…")
        else:
            required = [i for i in self.store.manifest if self.lifecycle(i) == "Required"]
            missing = len(self.missing())
            tools = card("Software", f"{len(required) - missing} of {len(required)} required tools ready", "software")
            tools.layout().addWidget(StatusPill(f"{missing} need setup" if missing else "Ready", "warning" if missing else "success"))
            tools.layout().addWidget(button("Set up missing software" if missing else "Open software", lambda: self.show_page("Software")))
        shortcuts = card("Project shortcuts", "Your team's existing tools and resources.", "links")
        configured = [(name, target) for name, target in p["links"].items() if name != "Meeting agenda" and target]
        for name, target in configured:
            shortcuts.layout().addWidget(button("Open " + name.lower(), lambda checked=False, n=name: self.guard(lambda: self.open_project_link(n))))
        if not configured:
            shortcuts.layout().addWidget(button("Configure resources", lambda: self.open_settings(3)))
        agenda = card("Upcoming meeting", p["agenda"] or "Link the shared agenda or add meeting notes.", "calendar")
        agenda.layout().addWidget(button("Open shared agenda", lambda: self.guard(lambda: self.open_project_link("Meeting agenda"))))
        changes = card("Recent changes", p["decisions"] or "No major decisions recorded yet.", "activity")
        changes.layout().addWidget(button("View activity", lambda: self.show_page("Activity")))
        layout.addWidget(ResponsiveCards([goal, plan, storage, tools, shortcuts, agenda, changes]))
        layout.addStretch()

    def workspace_sidebar(self, active):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(176)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)
        layout.addWidget(label("Workspace", "muted"))
        for name, image in (("Overview", "overview"), ("Files & Data", "files"), ("Reports", "reports"), ("Analysis", "software"), ("Resources", "links")):
            control = Button(name, lambda checked=False, n=name: self.open_workspace(n), variant="sidebar")
            control.setIcon(icon(image, Theme.ACCENT_HOVER if active == name else Theme.TEXT_SECONDARY))
            control.setProperty("iconName", image)
            control.setCheckable(True)
            control.setProperty("workspacePage", name)
            control.setChecked(active == name)
            layout.addWidget(control)
        layout.addSpacing(24)
        layout.addWidget(label("Quick access", "muted"))
        storage = Button("Shared storage", lambda: self.open_settings(1), variant="sidebar")
        storage.setIcon(icon("storage"))
        layout.addWidget(storage)
        layout.addStretch()
        return sidebar

    def open_workspace(self, name):
        previous = self.workspace_section
        self.workspace_section = name
        if name == "Overview":
            self.show_page("Dashboard")
            return
        self.show_page("Project")
        self.project_tabs.setCurrentIndex(0 if name == "Resources" else 2 if name == "Analysis" else 1)
        if name == "Reports":
            self.files_panel.clear_filters()
            category = self.files_panel.filters["category"]
            if category.findData("Report") < 0:
                category.addItem("Report", "Report")
            category.setCurrentIndex(category.findData("Report"))
        elif name == "Files & Data" and previous == "Reports":
            self.files_panel.clear_filters()
        self.render_project()

    def open_settings(self, index):
        self.show_page("Settings")
        self.settings_tabs.setCurrentIndex(index)

    def open_analysis_settings(self):
        self.open_settings(next(i for i in range(self.settings_tabs.count()) if self.settings_tabs.tabText(i) == 'Analysis Tools'))
        self.gdl_settings.validate_paths()

    def render_software(self):
        layout = self.reset("Software")
        layout.addWidget(SectionHeader("Welcome to Fuel Cell Project Hub" if not self.store.local.get("setup_complete") else "Software", "Configure your tools once, then launch them here."))
        controls = QWidget()
        row = QHBoxLayout(controls)
        row.setContentsMargins(0, 0, 0, 0)
        rescan = button("Scanning…" if self.scanning else "Re-scan tools", self.scan, True)
        rescan.setEnabled(not self.scanning)
        row.addWidget(rescan)
        row.addWidget(button("Continue anyway" if self.missing() else "Finish setup", self.finish_setup))
        row.addStretch()
        layout.addWidget(controls)
        gdl = card("GDL Analysis", "YOURE A BETA · Engine v" + str(self.gdl_service.registry.manifest().get("version", "Unknown")), "software")
        gdl.layout().addWidget(button("Open analysis", lambda: self.open_workspace("Analysis"), True))
        gdl.layout().addWidget(button("Analysis settings", self.open_analysis_settings))
        layout.addWidget(gdl)
        if self.scanning and not self.results:
            layout.addWidget(SkeletonCard("Checking your system…"))
            layout.addWidget(SkeletonCard("Finding required applications…"))
            layout.addStretch()
            return
        group = ""
        items = sorted(self.store.manifest, key=lambda i: (2 if self.lifecycle(i) != "Required" else 1 if self.results.get(i["id"], {}).get("status") == "Ready" else 0, i["name"]))
        for item in items:
            result = self.results.get(item["id"], {"status": "Not scanned", "path": "", "source": ""})
            kind = item.get("launch_type", "exe")
            status = "Available" if kind in ("uri", "url") and result["status"] == "Ready" else result["status"]
            section = "Optional & retired" if self.lifecycle(item) != "Required" else "Ready" if result["status"] == "Ready" else "Needs setup"
            if group != section:
                layout.addWidget(label(section, "section"))
                group = section
            frame = card(item["name"], item["note"], "software")
            frame.layout().insertWidget(1, StatusPill(status, "success" if status in ("Available", "Ready") else "error" if status == "Launch failed" else "warning"))
            frame.layout().addWidget(label(item["category"] + " · " + self.lifecycle(item), "muted"))
            frame.setProperty("softwareId", item["id"])
            frame.layout().addWidget(label(result["path"] or result["source"], "muted"))
            if kind in ("uri", "url"):
                frame.layout().addWidget(label("Launch Method: " + ("Windows URI Protocol" if kind == "uri" else "Web") + " · " + item.get("launch_target", ""), "muted"))
            actions = QWidget()
            actions.setObjectName("cardActions")
            row = QHBoxLayout(actions)
            row.setContentsMargins(0, 6, 0, 0)
            launch_text = "Test Launch" if kind == "uri" else "Open" if kind == "url" else "Open terminal" if item["id"] == "git" else "Launch"
            launch_button = button(launch_text, lambda checked=False, i=item: self.launch_item(i), True)
            launch_button.setEnabled((result["status"] == "Ready" or kind == "uri") and self.lifecycle(item) != "Retired" and not self.scanning)
            row.addWidget(launch_button)
            if kind == "exe":
                locate_button = button("Locate application", lambda checked=False, i=item: self.locate(i))
                locate_button.setEnabled(not self.scanning)
                row.addWidget(locate_button)
            row.addWidget(button("Installation guide", lambda checked=False, i=item: self.guard(lambda: open_resource(i["url"]))))
            if kind == "exe" and item["id"] in self.store.local["paths"]:
                clear = button("Clear saved path", lambda checked=False, i=item: self.clear_path(i))
                clear.setEnabled(not self.scanning)
                row.addWidget(clear)
            row.addStretch()
            frame.layout().addWidget(actions)
            layout.addWidget(frame)
        layout.addStretch()

    def launch_item(self, item):
        try:
            kind = launch_type(item)
            launch(item, self.results.get(item["id"], {}), self.store.project_folder())
        except Exception as exc:
            if item.get("launch_type") != "uri":
                self.global_error.show_error(item["name"] + " could not be launched", exc)
                return
            self.results[item["id"]] = {"path": "", "target": item.get("launch_target", ""),
                "source": "Install or repair " + item["name"] + ", then retry.", "status": "Launch failed"}
            self.refresh_launch_status()
            box = QMessageBox(self)
            box.setWindowTitle(item["name"] + " could not be launched")
            box.setText(item["name"] + " could not be launched.\nInstall or repair " + item["name"] + ", then retry.")
            box.setDetailedText(str(exc))
            download = box.addButton("Open " + ("Teams" if item["id"] == "teams" else item["name"]) + " Download Page", QMessageBox.ActionRole)
            retry = box.addButton("Retry", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() == download:
                self.guard(lambda: open_resource(item["url"]))
            elif box.clickedButton() == retry:
                QTimer.singleShot(0, lambda: self.launch_item(item))
            return
        if kind == LaunchType.URI:
            self.results[item["id"]] = {"path": "", "target": item["launch_target"],
                "source": "Windows URI Protocol · Windows accepted the launch request", "status": "Ready"}
            self.refresh_launch_status()
        notify(self, item["name"] + " launch requested", "success")

    def refresh_launch_status(self):
        missing = self.missing()
        self.banner.set_message(f"{len(missing)} required tools need setup. Open Software to configure them."
                            if missing else "All required tools are ready.", "warning" if missing else "success")
        self.render_dashboard()
        self.render_software()

    def locate(self, item):
        if item.get("launch_type", "exe") != "exe":
            return
        path, _ = QFileDialog.getOpenFileName(self, "Locate " + item["name"], str(Path.home()), "Applications (*.exe)")
        if not path:
            return
        if not valid_executable(path):
            self.global_error.show_error("Choose a desktop executable", "Choose an existing .exe file. Windows Store aliases are not executable installations.")
            return
        self.store.local["paths"][item["id"]] = str(Path(path).resolve())
        self.guard(self.store.save_local)
        self.scan()

    def clear_path(self, item):
        self.store.local["paths"].pop(item["id"], None)
        self.guard(self.store.save_local)
        self.scan()

    def finish_setup(self):
        self.store.local["setup_complete"] = True
        self.guard(self.store.save_local)
        self.show_page("Dashboard")

    def render_project(self):
        selected = self.project_tabs.currentIndex() if hasattr(self, "project_tabs") else 0
        self.files_panel.setParent(self)
        if hasattr(self, 'research_workspace'):
            self.research_workspace.setParent(self)
            self.gdl_panel.setParent(self)
        container = self.reset("Project")
        tabs = QTabWidget()
        self.project_tabs = tabs
        tabs.tabBar().hide()
        resources_page = QWidget()
        layout = QVBoxLayout(resources_page)
        resources_scroll = QScrollArea()
        resources_scroll.setWidgetResizable(True)
        resources_scroll.setFrameShape(QFrame.NoFrame)
        resources_scroll.setWidget(resources_page)
        tabs.addTab(resources_scroll, "Resources")
        from app.ui.research_workspace import ResearchHub
        if not hasattr(self, 'research_workspace'):
            self.research_workspace = ResearchHub(self.storage_settings, self)
        tabs.addTab(self.research_workspace if self.storage_settings.catalog else self.files_panel, "Files & Data")
        analysis_scroll = QScrollArea()
        analysis_scroll.setWidgetResizable(True)
        analysis_scroll.setFrameShape(QFrame.NoFrame)
        analysis_scroll.setWidget(self.gdl_panel)
        tabs.addTab(analysis_scroll, "Analysis")
        workspace = QWidget()
        row = QHBoxLayout(workspace)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(24)
        self.project_sidebar = self.workspace_sidebar("Resources" if selected == 0 else "Analysis" if selected == 2 else "Reports" if self.workspace_section == "Reports" else "Files & Data")
        row.addWidget(self.project_sidebar)
        row.addWidget(tabs, 1)
        container.addWidget(workspace)
        tabs.setCurrentIndex(selected)
        tabs.currentChanged.connect(self.update_project_sidebar)
        self.project_sidebar.setVisible(selected != 1)
        tabs.currentChanged.connect(lambda index: self.project_sidebar.setVisible(index != 1))
        layout.addWidget(SectionHeader("Project resources", "Open the team's existing files and tools.", button("Edit resources", lambda: self.open_settings(3))))
        resources = {"GitHub repository": self.store.project["repository"], "Project folder": self.store.project_folder(), **self.store.project["links"]}
        for name, target in resources.items():
            frame = card(name, target or "Add a link or relative path in Project resources settings.", "links")
            frame.layout().addWidget(button("Open " + name, lambda checked=False, n=name, t=target: self.guard(lambda: self.open_project_link(n) if n in self.store.project["links"] else self.store.provider.open_folder() if n == "Project folder" and self.store.provider else open_resource(t))))
            layout.addWidget(frame)
        layout.addWidget(label("Code and releases stay in GitHub. Project files and large data stay in your existing shared storage.", "muted"))
        layout.addStretch()

    def show_research_files(self, origin):
        self.show_page('Project')
        if self.research_workspace.catalog:
            self.research_workspace.navigate('Legacy' if origin == 'legacy' else 'Files')
            self.research_workspace.browser.origin.setCurrentIndex(max(0,self.research_workspace.browser.origin.findData(origin)))
        self.project_tabs.setCurrentIndex(1)
        self.files_panel.origin.setCurrentIndex(max(0, self.files_panel.origin.findData(origin)))
        self.files_panel.reload()
        parent = self.files_panel.parentWidget()
        while parent:
            if isinstance(parent, QTabWidget):
                parent.setCurrentWidget(self.files_panel)
                break
            parent = parent.parentWidget()

    def update_project_sidebar(self, selected):
        active = "Resources" if selected == 0 else "Analysis" if selected == 2 else "Reports" if self.workspace_section == "Reports" else "Files & Data"
        for control in self.project_sidebar.findChildren(QPushButton):
            name = control.property("workspacePage")
            if name:
                control.setChecked(name == active)
                control.setIcon(icon(control.property("iconName"), Theme.ACCENT_HOVER if name == active else Theme.TEXT_SECONDARY))

    def open_project_link(self, name):
        target = self.store.project["links"].get(name) or self.store.local.get("local_resource_paths", {}).get(name, "")
        if not target or target.startswith(("http://", "https://")):
            return open_resource(target)
        if name in self.store.local.get("local_resource_paths", {}) and not self.store.project["links"].get(name):
            return open_resource(target)
        if not self.store.provider:
            raise ValueError("Connect project storage under Settings → Storage to open this relative path.")
        try:
            self.store.provider.open_folder(target)
        except ValueError:
            self.store.provider.open_item(target)

    def search_workspace(self):
        self.show_page('Project')
        self.project_tabs.setCurrentIndex(1)
        if self.research_workspace.catalog:
            self.research_workspace.global_search(self.global_search.text())
        else:
            self.files_panel.search.setText(self.global_search.text())

    def storage_changed(self):
        if hasattr(self,'meetings_panel'):
            self.meetings_panel.service.catalog=self.storage_settings.catalog
        self.index_status.setText('Index available' if self.storage_settings.catalog else 'Storage not configured')
        if hasattr(self, 'research_workspace'):
            if self.research_workspace.catalog is not self.storage_settings.catalog:
                if self.research_workspace.busy():
                    QTimer.singleShot(300, self.storage_changed)
                    return
                old = self.research_workspace
                from app.ui.research_workspace import ResearchHub
                self.research_workspace = ResearchHub(self.storage_settings, self)
                old.setParent(None)
                old.deleteLater()
            else:
                self.research_workspace.reload()
        self.files_panel.reload()
        self.render_dashboard()
        self.render_activity()
        # Keep the persistent storage panel alive during its worker thread.
        self.render_project()
        if self.store.project != getattr(self, "settings_snapshot", None):
            self.render_settings()
            self.storage_panel.reload_fields()

    def storage_busy_changed(self, busy):
        self.files_panel.set_loading(busy)
        self.render_dashboard()

    def render_activity(self):
        layout = self.reset("Activity")
        layout.addWidget(SectionHeader("Activity", "Local settings, storage, and bug updates. Discussions stay in Teams or Discord."))
        filter_box = QComboBox()
        filter_box.addItems(["All areas", "Settings", "Bugs", "Storage"])
        entries = QWidget()
        entries_layout = QVBoxLayout(entries)
        entries_layout.setContentsMargins(0, 0, 0, 0)
        def display(area):
            while entries_layout.count():
                entries_layout.takeAt(0).widget().deleteLater()
            events = [e for e in reversed(self.store.events) if area == "All areas" or e["area"] == area]
            if not events:
                entries_layout.addWidget(EmptyState("No activity yet", "Settings, index changes, and bug reports will appear here.", "Open project overview", lambda: self.show_page("Dashboard"), "activity"))
            for event in events:
                frame = card(event["area"] + " · " + event["message"], local_datetime(event["timestamp"]) + " · " + event["person"], "activity")
                entries_layout.addWidget(frame)
        filter_box.currentTextChanged.connect(display)
        layout.addWidget(filter_box)
        layout.addWidget(entries)
        display("All areas")
        layout.addStretch()

    def render_bugs(self):
        layout = self.reset("Bugs")
        layout.addWidget(label("Bug support", "heading"))
        layout.addWidget(label("Reports stay on this computer. Export a report for the project lead to review before posting it to GitHub.", "muted"))
        layout.addWidget(button("Report a bug", self.report_bug, True))
        if not self.store.bugs:
            layout.addWidget(EmptyState("No bug reports", "Report a problem when something needs attention.", "Report a bug", self.report_bug, "bug"))
        for bug in reversed(self.store.bugs):
            frame = card(bug["id"] + " · " + bug["title"], bug["detail"])
            if bug.get("expected"):
                frame.layout().addWidget(label("Expected: " + bug["expected"], "muted"))
            frame.layout().addWidget(label(local_datetime(bug["timestamp"]) + " · " + bug["person"] + " · " + bug["version"], "muted"))
            status = QComboBox()
            status.addItems(["Open", "Investigating", "Fixed", "Closed"])
            status.setCurrentText(bug["status"])
            status.currentTextChanged.connect(lambda value, b=bug: self.guard(lambda: self.set_bug_status(b, value)))
            frame.layout().addWidget(status)
            frame.layout().addWidget(button("Export report…", lambda checked=False, b=bug: self.export_bug(b)))
            layout.addWidget(frame)
        layout.addStretch()

    def set_bug_status(self, bug, status):
        bug["status"] = status
        if self.store.shared_index:
            write_json(self.store.project_data('metadata/bugs') / (bug['id'] + '.json'), bug)
        else:
            write_json(self.store.local_dir / "bugs.json", self.store.bugs)
        self.store.record("Bugs", f"{bug['id']} marked {status}")
        self.render_activity()

    def report_bug(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Report a bug")
        dialog.resize(620, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Describe the problem", "heading"))
        title = QLineEdit()
        title.setPlaceholderText("Short title")
        detail = QTextEdit()
        detail.setPlaceholderText("Describe what happened")
        expected = QTextEdit()
        expected.setPlaceholderText("Describe the expected behavior")
        steps = QTextEdit()
        steps.setPlaceholderText("Optional steps to reproduce")
        form = QFormLayout()
        for caption, field in (("Title", title), ("What happened", detail), ("Expected behavior", expected), ("Steps to reproduce", steps)):
            if isinstance(field, QTextEdit):
                field.setFixedHeight(90)
            form.addRow(caption, field)
        layout.addLayout(form)
        layout.addWidget(label("Automatically included: app version, profile, UTC timestamp, Windows version, current page, and tool readiness. Executable paths and project links are excluded.", "muted"))
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.rejected.connect(dialog.reject)
        error = InlineMessage()
        error.hide()
        layout.addWidget(error)
        def save():
            if not title.text().strip() or not detail.toPlainText().strip():
                error.set_message("Add a title and describe what happened.", "warning")
                return
            try:
                self.store.add_bug(title.text().strip(), detail.toPlainText().strip(),
                    {"platform": platform.platform(), "page": self.tabs.tabText(self.tabs.currentIndex()),
                     "software": {k: v["status"] for k, v in self.results.items()}}, __version__, expected.toPlainText().strip(), steps.toPlainText().strip())
            except Exception as exc:
                error.set_message("Report could not be saved. " + friendly_error(exc), "error")
                return
            dialog.accept()
        buttons.accepted.connect(save)
        layout.addWidget(buttons)
        if dialog.exec():
            self.render_bugs()
            self.render_activity()
            notify(self, "Bug report saved", "success")

    def export_bug(self, bug):
        path, _ = QFileDialog.getSaveFileName(self, "Export bug report", bug["id"] + ".json", "JSON (*.json)")
        if path:
            self.guard(lambda: write_json(self.store.validate_project_output(path), bug))

    def render_settings(self):
        selected = self.settings_tabs.currentIndex() if hasattr(self, "settings_tabs") else 0
        container = self.reset("Settings")
        container.addWidget(SectionHeader("Settings"))
        tabs = QTabWidget()
        self.settings_tabs = tabs
        self.settings_snapshot = copy.deepcopy(self.store.project)
        self.fields, self.lifecycle_fields = {}, {}
        sections = {}
        for name in ("General", "Storage", "Software", "Project resources", "Updates", "History", "Analysis Tools"):
            if name == "Storage":
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(self.research_panel)
                tabs.addTab(scroll, name)
                continue
            if name == "Analysis Tools":
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                scroll.setWidget(self.gdl_settings)
                tabs.addTab(scroll, name)
                continue
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(8, 20, 8, 20)
            layout.setSpacing(16)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setWidget(page)
            tabs.addTab(scroll, name)
            sections[name] = layout
        container.addWidget(tabs)
        tabs.setCurrentIndex(selected)

        general = sections["General"]
        editor_row = QHBoxLayout()
        self.code_editor = QLineEdit(self.store.local.get('code_editor', ''))
        self.code_editor.setPlaceholderText('Optional editor executable; scripts use Notepad by default')
        editor_row.addWidget(self.code_editor, 1)
        def save_editor():
            path = self.code_editor.text().strip()
            if path and not Path(path).is_file():
                notify(self, 'Choose an existing editor executable.', 'warning')
                return
            self.store.local['code_editor'] = path
            self.guard(self.store.save_local)
        editor_row.addWidget(button('Save code editor', save_editor))
        general.addWidget(label('Code file editor', 'heading'))
        general.addLayout(editor_row)

        overview = card("Project overview", "Keep the dashboard focused on the team's current work.", "overview")
        form = QFormLayout()
        form.setSpacing(16)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for key, title in (("goal", "Primary goal"), ("plan", "Current plan"), ("supporting_goals", "Supporting goals"), ("agenda", "Meeting notes"), ("decisions", "Recent decisions")):
            field = QTextEdit()
            field.setPlainText(self.store.project[key])
            field.setFixedHeight(76)
            self.fields[key] = field
            form.addRow(title, field)
        overview.layout().addLayout(form)
        general.addWidget(overview)

        resources = sections["Project resources"]
        frame = card("Project resources", "Use a web address or a path relative to your synced project folder.", "links")
        form = QFormLayout()
        form.setSpacing(16)
        repository = QLineEdit(self.store.project["repository"])
        repository.setClearButtonEnabled(True)
        self.fields["repository"] = repository
        form.addRow("GitHub repository", repository)
        for key, value in self.store.project["links"].items():
            field = QLineEdit(value)
            field.setClearButtonEnabled(True)
            self.fields["link:" + key] = field
            form.addRow(key, field)
        frame.layout().addLayout(form)
        resources.addWidget(frame)

        software = sections["Software"]
        frame = card("Software requirements", "Choose which tools the project needs. Retired tools keep their configuration.", "software")
        form = QFormLayout()
        form.setSpacing(12)
        for item in self.store.manifest:
            field = QComboBox()
            field.addItems(["Required", "Optional", "Retired"])
            field.setCurrentText(self.lifecycle(item))
            self.lifecycle_fields[item["id"]] = field
            form.addRow(item["name"], field)
        frame.layout().addLayout(form)
        software.addWidget(frame)

        updates = sections["Updates"]
        frame = card("App updates", "Updates use verified Windows installers from the official GitHub releases.", "history")
        repository = QLineEdit("MartParty079/GDL")
        repository.setReadOnly(True)
        repository.setPlaceholderText("owner/repository")
        self.fields["release_repository"] = repository
        form = QFormLayout()
        form.addRow("Release repository", repository)
        frame.layout().addLayout(form)
        from app.ui.components import ToggleSwitch
        self.update_toggle = ToggleSwitch("Check for updates at startup")
        self.update_toggle.setChecked(self.store.local.get("check_updates_at_startup", True))
        self.update_toggle.toggled.connect(self.save_update_preference)
        frame.layout().addWidget(self.update_toggle)
        self.update_status = InlineMessage(getattr(self, "release_status_text", "Configure a release repository to check for updates."))
        self.update_skeleton = SkeletonCard("Checking GitHub releases...")
        self.update_skeleton.setVisible(self.update_checking)
        frame.layout().addWidget(self.update_status)
        frame.layout().addWidget(self.update_skeleton)
        self.update_button = button("Check GitHub releases", self.check_updates)
        self.update_button.set_loading(self.update_checking, "Checking...")
        frame.layout().addWidget(self.update_button)
        self.release_button = button("View release", lambda: self.guard(lambda: open_resource(self.latest_release_url)))
        self.release_button.setVisible(bool(getattr(self, "latest_release_url", "")))
        frame.layout().addWidget(self.release_button)
        updates.addWidget(frame)

        history = sections["History"]
        history.addWidget(SectionHeader("Settings history", "Restore a revision without discarding the current settings."))
        try:
            revisions = self.store.history()
        except (OSError, ValueError) as exc:
            revisions = []
            error = ErrorBanner()
            error.show_error("History unavailable", exc)
            history.addWidget(error)
        if not revisions:
            history.addWidget(EmptyState("No saved revisions", "A revision is created when project settings change.", "Edit project settings", lambda: self.open_settings(0), "history"))
        for revision in revisions:
            frame = card(revision["reason"], local_datetime(revision["timestamp"]) + " · " + revision["person"], "history")
            frame.layout().addWidget(button("Restore previous settings", lambda checked=False, r=revision: self.guard(lambda: self.restore_settings(r))))
            history.addWidget(frame)
        for name, layout in sections.items():
            if name != "History":
                layout.addWidget(button("Apply project changes", lambda: self.guard(self.apply_settings), True), alignment=Qt.AlignLeft)
            layout.addStretch()

    def save_update_preference(self, enabled):
        def save():
            self.store.local["check_updates_at_startup"] = enabled
            self.store.save_local()
            notify(self, "Update preference saved", "success")
        self.guard(save)

    def apply_settings(self):
        value = copy.deepcopy(self.store.project)
        for key, field in self.fields.items():
            text = field.toPlainText().strip() if isinstance(field, QTextEdit) else field.text().strip()
            if key.startswith("link:"):
                value["links"][key[5:]] = text
            else:
                value[key] = text
        value["software_lifecycle"] = {key: field.currentText() for key, field in self.lifecycle_fields.items()}
        if value == self.store.project:
            notify(self, "Settings are already up to date")
            return
        answer = QMessageBox.question(self, "Apply project settings?", "Apply these settings to the entire team? A revision will preserve the current settings.")
        if answer != QMessageBox.Yes:
            return
        self.store.save_project(value)
        self.refresh_project()
        notify(self, "Project settings saved", "success")

    def restore_settings(self, revision):
        if QMessageBox.question(self, "Restore settings?", "Restore the settings from before this revision? The current settings will also be preserved.") == QMessageBox.Yes:
            self.store.save_project(revision["previous"], "Restored settings before " + revision["id"])
            self.refresh_project()
            notify(self, "Previous settings restored", "success")

    def refresh_project(self):
        self.render_dashboard()
        self.render_project()
        self.render_settings()
        self.storage_panel.reload_fields()
        self.files_panel.reload()
        self.render_activity()
        self.scan_done(self.results)

    def check_updates_on_startup(self):
        if self.store.local.get("check_updates_at_startup", True):
            self.check_updates(manual=False)

    def check_updates(self, checked=False, manual=True):
        if self.update_checking:
            return
        repository = "MartParty079/GDL"
        if not repository:
            self.update_status.setText("Add and apply a release repository first.")
            return
        self.update_checking = True
        self.manual_update_check = manual
        self.update_status.set_message("Checking approved GitHub releases…")
        self.update_button.set_loading(True, "Checking…")
        self.update_skeleton.show()
        self.work(lambda: latest_release(repository) if manual else cached_release(self.store.local_dir), self.update_done, self.update_failed)

    def update_done(self, release):
        self.update_checking = False
        self.update_button.set_loading(False)
        self.update_skeleton.hide()
        self.latest_release_info = release
        self.latest_release_url = release["url"]
        self.release_button.show()
        self.release_status_text = "Latest release: " + release["tag"] + " · current: " + __version__
        self.update_status.set_message(self.release_status_text, "success")
        self.header_update.setText("Update " + release["tag"] if newer(release["tag"]) else "Up to date")
        if newer(release["tag"]) and getattr(self, 'manual_update_check', True):
            notify(self, "Update available. Review it under Settings → Updates.")
        elif getattr(self, 'manual_update_check', True):
            notify(self, "The app is up to date", "success")

    def update_failed(self, message):
        self.update_checking = False
        self.update_button.set_loading(False)
        self.update_skeleton.hide()
        self.release_status_text = "GitHub is unavailable. Check your connection and retry. Local project work is still available."
        self.update_status.set_message(self.release_status_text, "warning")
        if getattr(self, 'manual_update_check', True):
            notify(self, "GitHub check unavailable. You can retry under Settings → Updates.", "warning")

    def show_update_dialog(self):
        release = getattr(self, "latest_release_info", None)
        if not release:
            self.check_updates(); return
        dialog = QDialog(self); dialog.setWindowTitle(APP_NAME + " Updates")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Installed: v" + __version__ + (" · Latest Beta: " if BETA else " · Latest Stable: ") + release["tag"]))
        notes = QTextEdit(); notes.setReadOnly(True); notes.setPlainText(release.get("notes", "View the release for changes.")); layout.addWidget(notes)
        update = button("Update Now", lambda: (dialog.accept(), self.download_update()))
        update.setEnabled(newer(release["tag"])); layout.addWidget(update)
        later=button("Update on Next Open",lambda:(self.schedule_update(),dialog.accept()))
        later.setEnabled(newer(release['tag']));layout.addWidget(later)
        layout.addWidget(button("Cancel", dialog.reject)); dialog.resize(650,450); dialog.exec()

    def download_update(self):
        answer=QMessageBox.question(self,'Update Now?', 'Active indexing will be cancelled gracefully. Other background writes will be allowed to finish safely. Pending settings and editor drafts will be saved before updating. Continue?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)
        if answer==QMessageBox.Yes:self.guard(self.safe_update.start)

    def schedule_update(self):
        if self.guard(self.safe_update.schedule):
            notify(self,'Update saved for next open. Current background work will continue.','success')

    def offer_deferred_update(self,message):
        box=QMessageBox(self);box.setWindowTitle('Update safely');box.setText(message)
        retry=box.addButton('Retry Download',QMessageBox.ActionRole)
        from app.services.storage import read_json
        import json
        details=read_json(self.store.local_dir/'updates'/'update-diagnostics.local.json',{})
        box.setDetailedText(json.dumps(details,indent=2) if details else 'No download details recorded. The existing installation is preserved.')
        later=box.addButton('Update on Next Open',QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel);box.exec()
        if box.clickedButton()==later:self.schedule_update()
        elif box.clickedButton()==retry:QTimer.singleShot(0,self.safe_update.start)

    def install_update(self, path):
        self.safe_update.install(path)

    def closeEvent(self, event):
        if hasattr(self,'safe_update') and self.safe_update.state not in ('idle','installed'):
            event.ignore();return
        if self.workers or self.storage_panel.indexing or self.research_panel.indexing or self.research_workspace.busy() or (hasattr(self, "account_tasks") and self.account_tasks.busy()) or (hasattr(self, "admin_workspace") and self.admin_workspace.tasks.busy()) or (hasattr(self, 'meetings_panel') and self.meetings_panel.busy()) or (hasattr(self,'weekly_panel') and self.weekly_panel.tasks.busy()):
            self.storage_panel.cancel_index()
            self.research_panel.cancel_index()
            self.banner.setText("Finishing a background check. Please close the app again in a moment.")
            event.ignore()
        else:
            self.closing = True
            if hasattr(self, 'session_presence') and not getattr(self,'update_exit_ready',False):
                self.session_presence.stop()
            self.research_panel.watcher.stop()
            self.research_workspace.save_layout()
            event.accept()
            if hasattr(self, "account_service") and not getattr(self, "signing_out", False):
                from PySide6.QtWidgets import QApplication
                QApplication.instance().quit()
