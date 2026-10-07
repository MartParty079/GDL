import copy
import json
import platform
import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QScrollArea, QFrame, QGridLayout, QFileDialog, QMessageBox,
    QLineEdit, QTextEdit, QFormLayout, QComboBox, QDialog, QDialogButtonBox)

from app import __version__
from app.services.storage import write_json
from app.services.software import detect, valid_executable, launch, open_resource, LaunchType, launch_type
from app.services.updates import latest_release


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


def button(text, action, primary=False):
    widget = QPushButton(text)
    widget.setProperty("primary", primary)
    widget.clicked.connect(action)
    widget.setCursor(Qt.PointingHandCursor)
    return widget


def label(text, kind="body"):
    widget = QLabel(text)
    widget.setWordWrap(kind not in ("heading", "title", "eyebrow"))
    widget.setTextFormat(Qt.PlainText)
    widget.setProperty("kind", kind)
    widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return widget


def card(title, body):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 22)
    layout.addWidget(label(title, "cardTitle"))
    layout.addWidget(label(body))
    return frame


class HubWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.results = {}
        self.workers = []
        self.scanning = False
        self.update_checking = False
        self.setWindowTitle("Fuel Cell Project Hub")
        self.resize(1180, 850)
        self.setMinimumSize(800, 600)
        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(26, 22, 26, 20)
        top = QHBoxLayout()
        identity = QVBoxLayout()
        identity.addWidget(label("FUEL CELL  /  CAPSTONE", "eyebrow"))
        identity.addWidget(label("Project Hub", "title"))
        top.addLayout(identity)
        top.addStretch()
        top.addWidget(label("LOCAL WORKSPACE\n" + __version__, "muted"))
        outer.addLayout(top)
        self.banner = label("Scanning configured tools…", "notice")
        outer.addWidget(self.banner)
        self.tabs = QTabWidget()
        self.pages = {}
        self.layouts = {}
        for name in ("Dashboard", "Activity", "Software", "Project", "Bugs", "Settings"):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(4, 20, 4, 12)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, name)
            self.pages[name], self.layouts[name] = page, layout
        outer.addWidget(self.tabs)
        self.setCentralWidget(shell)
        self.apply_theme()
        self.render_dashboard()
        self.render_software()
        self.render_project()
        self.render_activity()
        self.render_bugs()
        self.render_settings()
        QTimer.singleShot(0, self.scan)
        QTimer.singleShot(200, self.check_updates_on_startup)

    def apply_theme(self):
        # Offscreen Qt on Windows has no system font database. Explicitly load
        # existing Windows fonts for rendering; native UI can use them too.
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"):
            if (font_dir / filename).is_file():
                QFontDatabase.addApplicationFont(str(font_dir / filename))
        self.setStyleSheet('''
            QWidget { background: #f2f4f3; color: #182e2a; font-family: "Segoe UI"; font-size: 14px; }
            QLabel { background: transparent; line-height: 1.4; }
            QLabel[kind="title"] { font-size: 30px; font-weight: 700; }
            QLabel[kind="eyebrow"] { color: #456e62; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
            QLabel[kind="heading"] { font-size: 24px; font-weight: 650; }
            QLabel[kind="cardTitle"] { font-size: 17px; font-weight: 650; }
            QLabel[kind="muted"] { color: #61736e; font-size: 13px; }
            QLabel[kind="notice"] { background: #e3ece6; padding: 14px; border-radius: 8px; color: #275243; }
            QFrame#card { background: white; border: 1px solid #dbe2de; border-radius: 10px; }
            QPushButton { background: white; border: 1px solid #c6d4cc; padding: 10px 15px; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background: #e5eee8; border-color: #45856a; }
            QPushButton:focus { border: 2px solid #278568; }
            QPushButton[primary="true"] { background: #245f4c; color: white; border-color: #245f4c; }
            QPushButton:disabled { color: #88968f; background: #edf0ee; }
            QTabWidget::pane { border: none; }
            QTabBar::tab { background: transparent; padding: 13px 19px; color: #5b6a64; border-bottom: 3px solid transparent; }
            QTabBar::tab:selected { color: #245f4c; border-bottom: 3px solid #245f4c; font-weight: 700; }
            QLineEdit, QTextEdit, QComboBox { background: white; border: 1px solid #cbd8d0; padding: 8px; border-radius: 5px; }
            QScrollArea { border: none; }
        ''')

    def reset(self, name):
        layout = self.layouts[name]
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        return layout

    def show_page(self, name):
        self.tabs.setCurrentIndex(list(self.pages).index(name))

    def guard(self, action):
        try:
            return action()
        except Exception as exc:
            QMessageBox.warning(self, "Action could not be completed", str(exc))

    def work(self, action, done, failed=None):
        worker = Worker(action, self)
        self.workers.append(worker)
        worker.done.connect(done)
        worker.failed.connect(failed or (lambda message: QMessageBox.warning(self, "Action failed", message)))
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
        self.banner.setText("Scanning configured paths, Windows application registration, and common install folders…")
        self.render_software()
        paths = copy.deepcopy(self.store.local["paths"])
        self.work(lambda: {i["id"]: detect(i, paths.get(i["id"])) for i in self.store.manifest}, self.scan_done, self.scan_failed)

    def scan_failed(self, message):
        self.scanning = False
        self.banner.setText("Software scan failed: " + message)
        self.render_software()

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
        self.banner.setText(f"{len(missing)} required tools need configuration. Open Software to finish setup."
                            if missing else "All required tools are ready. Your project workspace is configured.")
        self.render_dashboard()
        self.render_software()
        if not self.store.local.get("setup_complete"):
            self.show_page("Software")

    def render_dashboard(self):
        layout = self.reset("Dashboard")
        row = QWidget()
        actions = QHBoxLayout(row)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(label("Start your project work", "heading"))
        actions.addStretch()
        actions.addWidget(button("Open Project Repo", lambda: self.guard(lambda: open_resource(self.store.project["repository"])), True))
        layout.addWidget(row)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 10, 0, 10)
        grid.setSpacing(16)
        p = self.store.project
        grid.addWidget(card("Primary goal", p["goal"] or "Add the team's primary goal in Settings."), 0, 0)
        grid.addWidget(card("Near-term work", p["plan"] or "Add the current plan in Settings."), 0, 1)
        grid.addWidget(card("Supporting goals", p["supporting_goals"] or "No supporting goals configured."), 1, 0)
        agenda = card("Meeting agenda", p["agenda"] or "Add agenda notes or link the shared meeting document.")
        agenda.layout().addWidget(button("Open shared agenda", lambda: self.guard(lambda: open_resource(p["links"]["Meeting agenda"]))))
        grid.addWidget(agenda, 1, 1)
        grid.addWidget(card("Major decisions / changes", p["decisions"] or "No major decisions recorded yet."), 2, 0)
        ready = sum(r["status"] == "Ready" for r in self.results.values())
        tools = card("Software readiness", f"{ready} tools available · {len(self.missing())} required tools need attention" if self.results else "Scanning tools…")
        tools.layout().addWidget(button("Set up my system", lambda: self.show_page("Software")))
        grid.addWidget(tools, 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(grid_widget)
        shortcuts = card("Project shortcuts", "Open the team's existing resources.")
        for name, target in p["links"].items():
            if name != "Meeting agenda":
                shortcuts.layout().addWidget(button(name + (" · configure" if not target else ""), lambda checked=False, t=target: self.guard(lambda: open_resource(t))))
        layout.addWidget(shortcuts)
        layout.addStretch()

    def render_software(self):
        layout = self.reset("Software")
        layout.addWidget(label("Set up your system", "heading"))
        layout.addWidget(label("Detection never installs or launches software. Use installation guides for missing tools, then re-scan or locate the application.", "muted"))
        controls = QWidget()
        row = QHBoxLayout(controls)
        row.setContentsMargins(0, 0, 0, 0)
        rescan = button("Scanning…" if self.scanning else "Re-scan tools", self.scan, True)
        rescan.setEnabled(not self.scanning)
        row.addWidget(rescan)
        row.addWidget(button("Continue anyway" if self.missing() else "Finish setup", self.finish_setup))
        row.addStretch()
        layout.addWidget(controls)
        for item in self.store.manifest:
            result = self.results.get(item["id"], {"status": "Not scanned", "path": "", "source": ""})
            kind = item.get("launch_type", "exe")
            status = "Available" if kind in ("uri", "url") and result["status"] == "Ready" else result["status"]
            frame = card(item["name"] + "  ·  " + self.lifecycle(item) + "  ·  " + status, item["note"])
            frame.setProperty("softwareId", item["id"])
            frame.layout().addWidget(label(result["path"] or result["source"], "muted"))
            if kind in ("uri", "url"):
                frame.layout().addWidget(label("Launch Method: " + ("Windows URI Protocol" if kind == "uri" else "Web") + " · " + item.get("launch_target", ""), "muted"))
            actions = QWidget()
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
            launch(item, self.results.get(item["id"], {}), self.store.project["project_folder"])
        except Exception as exc:
            if item.get("launch_type") != "uri":
                QMessageBox.warning(self, "Action could not be completed", str(exc))
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

    def refresh_launch_status(self):
        missing = self.missing()
        self.banner.setText(f"{len(missing)} required tools need configuration. Open Software to finish setup."
                            if missing else "All required tools are ready. Your project workspace is configured.")
        self.render_dashboard()
        self.render_software()

    def locate(self, item):
        if item.get("launch_type", "exe") != "exe":
            return
        path, _ = QFileDialog.getOpenFileName(self, "Locate " + item["name"], str(Path.home()), "Applications (*.exe)")
        if not path:
            return
        if not valid_executable(path):
            QMessageBox.warning(self, "Invalid application", "Choose an existing .exe file. Windows Store aliases are not executable installations.")
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
        layout = self.reset("Project")
        layout.addWidget(label("Project resources", "heading"))
        resources = {"GitHub repository": self.store.project["repository"], "Project folder": self.store.project["project_folder"], **self.store.project["links"]}
        for name, target in resources.items():
            frame = card(name, target or "Not configured. Add the destination in Settings.")
            frame.layout().addWidget(button("Open " + name, lambda checked=False, t=target: self.guard(lambda: open_resource(t))))
            layout.addWidget(frame)
        layout.addWidget(label("Code and releases stay in GitHub. Project files and large data stay in your existing shared storage.", "muted"))
        layout.addStretch()

    def render_activity(self):
        layout = self.reset("Activity")
        layout.addWidget(label("Local activity", "heading"))
        layout.addWidget(label("Settings changes and bug reports recorded on this computer. Team requests and shared feeds are planned for a later version.", "muted"))
        filter_box = QComboBox()
        filter_box.addItems(["All areas", "Settings", "Bugs"])
        entries = QWidget()
        entries_layout = QVBoxLayout(entries)
        entries_layout.setContentsMargins(0, 0, 0, 0)
        def display(area):
            while entries_layout.count():
                entries_layout.takeAt(0).widget().deleteLater()
            events = [e for e in reversed(self.store.events) if area == "All areas" or e["area"] == area]
            if not events:
                entries_layout.addWidget(card("No activity yet", "Changes will appear here as you use the hub."))
            for event in events:
                frame = card(event["area"] + " · " + event["message"], event["timestamp"] + " · " + event["person"])
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
            layout.addWidget(card("No bug reports", "Use Report a bug when something needs attention."))
        for bug in reversed(self.store.bugs):
            frame = card(bug["id"] + " · " + bug["title"], bug["detail"])
            frame.layout().addWidget(label(bug["timestamp"] + " · " + bug["person"] + " · " + bug["version"], "muted"))
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
        write_json(self.store.local_dir / "bugs.json", self.store.bugs)
        self.store.record("Bugs", f"{bug['id']} marked {status}")
        self.render_activity()

    def report_bug(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Report a bug")
        dialog.resize(580, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Describe the problem", "heading"))
        title = QLineEdit()
        title.setPlaceholderText("Short title")
        detail = QTextEdit()
        detail.setPlaceholderText("What happened? What did you expect? How can it be reproduced?")
        layout.addWidget(title)
        layout.addWidget(detail)
        layout.addWidget(label("Automatically included: app version, profile, UTC timestamp, Windows version, current page, and tool readiness. Executable paths and project links are excluded.", "muted"))
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.rejected.connect(dialog.reject)
        def save():
            if not title.text().strip() or not detail.toPlainText().strip():
                QMessageBox.warning(dialog, "Details needed", "Add a title and description.")
                return
            try:
                self.store.add_bug(title.text().strip(), detail.toPlainText().strip(),
                    {"platform": platform.platform(), "page": self.tabs.tabText(self.tabs.currentIndex()),
                     "software": {k: v["status"] for k, v in self.results.items()}}, __version__)
            except Exception as exc:
                QMessageBox.warning(dialog, "Report could not be saved", str(exc))
                return
            dialog.accept()
        buttons.accepted.connect(save)
        layout.addWidget(buttons)
        if dialog.exec():
            self.render_bugs()
            self.render_activity()

    def export_bug(self, bug):
        path, _ = QFileDialog.getSaveFileName(self, "Export bug report", bug["id"] + ".json", "JSON (*.json)")
        if path:
            self.guard(lambda: write_json(Path(path), bug))

    def render_settings(self):
        layout = self.reset("Settings")
        layout.addWidget(label("Project settings", "heading"))
        layout.addWidget(label("Project settings are stored beside the app. Applying a change creates a restorable revision. Application paths stay in your local profile.", "muted"))
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields = {}
        titles = {"goal": "Primary goal", "supporting_goals": "Supporting goals", "plan": "Near-term work", "agenda": "Agenda notes", "decisions": "Major decisions / changes", "repository": "GitHub repository URL", "project_folder": "Project folder", "release_repository": "Release repository (owner/repo)"}
        for key, title in titles.items():
            if key in ("goal", "supporting_goals", "plan", "agenda", "decisions"):
                field = QTextEdit()
                field.setPlainText(self.store.project[key])
                field.setFixedHeight(90)
            else:
                field = QLineEdit(self.store.project[key])
            self.fields[key] = field
            form.addRow(title, field)
        for key, value in self.store.project["links"].items():
            field = QLineEdit(value)
            self.fields["link:" + key] = field
            form.addRow(key, field)
        self.lifecycle_fields = {}
        for item in self.store.manifest:
            field = QComboBox()
            field.addItems(["Required", "Optional", "Retired"])
            field.setCurrentText(self.lifecycle(item))
            self.lifecycle_fields[item["id"]] = field
            form.addRow(item["name"], field)
        layout.addWidget(form_widget)
        layout.addWidget(button("Apply project changes", lambda: self.guard(self.apply_settings), True))
        layout.addWidget(label("Settings history", "heading"))
        revisions = self.store.history()
        if not revisions:
            layout.addWidget(label("No saved revisions yet.", "muted"))
        for revision in revisions:
            frame = card(revision["reason"], revision["timestamp"] + " · " + revision["person"])
            frame.layout().addWidget(button("Restore previous settings", lambda checked=False, r=revision: self.guard(lambda: self.restore_settings(r))))
            layout.addWidget(frame)
        update_frame = card("App updates", "Release checks notify only. Selective installation and executable rollback are not available in this development version.")
        self.update_status = label("Configure the release repository above to enable checks.", "muted")
        update_frame.layout().addWidget(self.update_status)
        update_frame.layout().addWidget(button("Check GitHub releases", self.check_updates))
        layout.addWidget(update_frame)
        layout.addStretch()

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
            QMessageBox.information(self, "No changes", "The saved settings already match these values.")
            return
        answer = QMessageBox.question(self, "Apply project settings?", "Apply these project-wide settings? A revision will preserve the current settings for restoration.")
        if answer != QMessageBox.Yes:
            return
        self.store.save_project(value)
        self.refresh_project()

    def restore_settings(self, revision):
        if QMessageBox.question(self, "Restore settings?", "Restore the settings from before this revision? The current settings will also be preserved.") == QMessageBox.Yes:
            self.store.save_project(revision["previous"], "Restored settings before " + revision["id"])
            self.refresh_project()

    def refresh_project(self):
        self.render_dashboard()
        self.render_project()
        self.render_settings()
        self.render_activity()
        self.scan_done(self.results)

    def check_updates_on_startup(self):
        if self.store.project.get("release_repository"):
            self.check_updates()

    def check_updates(self):
        if self.update_checking:
            return
        repository = self.store.project.get("release_repository", "")
        if not repository:
            self.update_status.setText("Add and apply a release repository first.")
            return
        self.update_checking = True
        self.update_status.setText("Checking approved GitHub releases…")
        self.work(lambda: latest_release(repository), self.update_done, self.update_failed)

    def update_done(self, release):
        self.update_checking = False
        self.update_status.setText("Latest release: " + release["tag"] + " · current: " + __version__)
        if release["tag"].lstrip("v") != __version__:
            box = QMessageBox(self)
            box.setWindowTitle("GitHub release available")
            box.setText("Latest published release: " + release["name"] + "\nCurrent app: " + __version__ + "\nNo files have been downloaded or installed.")
            review = box.addButton("View release", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() == review:
                self.guard(lambda: open_resource(release["url"]))

    def update_failed(self, message):
        self.update_checking = False
        self.update_status.setText("Release check unavailable: " + message)

    def closeEvent(self, event):
        if self.workers:
            self.banner.setText("Finishing a background check. Please close the app again in a moment.")
            event.ignore()
        else:
            event.accept()
