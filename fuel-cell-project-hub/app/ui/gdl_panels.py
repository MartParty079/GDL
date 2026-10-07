"""GDL configuration and run controls, using the shared Hub design components."""
import copy
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QFileDialog,
    QMessageBox, QDialog, QTextEdit, QCheckBox, QGridLayout)
from app.services.path_registry import FIELDS, SHAREABLE, detect_dependency
from app.services.gdl_analysis import STATES, TERMINAL
from app.services.software import open_resource
from app.ui.components import (SectionHeader, AppCard, Button, StatusPill, InlineMessage, ErrorBanner,
    SkeletonCard, label, local_datetime, notify)
from app.ui.theme import repolish


class GDLSettingsPanel(QWidget):
    def __init__(self, service, window):
        super().__init__()
        self.service, self.window = service, window
        self.fields, self.originals, self.statuses = {}, {}, {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 20, 8, 20)
        layout.setSpacing(16)
        layout.addWidget(SectionHeader("Analysis Tools · GDL", "Configure paths here; the existing Fiji analysis interface controls processing."))
        self.error = ErrorBanner()
        layout.addWidget(self.error)
        self.skeleton = SkeletonCard("Validating analysis paths…")
        self.skeleton.hide()
        layout.addWidget(self.skeleton)
        modes = AppCard("Input and output", "Folders outside the project library remain personal settings.", "files")
        self.input_mode = QComboBox()
        self.input_mode.addItems(["Choose at launch", "Project Files & Data", "Remember last folder", "Configured folder"])
        self.output_mode = QComboBox()
        self.output_mode.addItems(["Project default", "Remember last folder", "Custom configured folder", "Ask when analysis starts"])
        self.input_mode.setCurrentText(service.registry.config["input_mode"])
        self.output_mode.setCurrentText(service.registry.config["output_mode"])
        for name, control in (("Input location mode", self.input_mode), ("Output location mode", self.output_mode)):
            modes.layout().addWidget(label(name, "muted"))
            control.setAccessibleName(name)
            modes.layout().addWidget(control)
        self.share = QCheckBox("Save folders inside project storage as shared relative paths")
        self.share.setChecked(True)
        modes.layout().addWidget(self.share)
        layout.addWidget(modes)
        for key, title in FIELDS.items():
            frame = AppCard(title, icon_name="software" if key.endswith("executable") else "files")
            field = QLineEdit()
            field.setAccessibleName(title + " path")
            field.setPlaceholderText("Leave blank to reset to the default")
            self.fields[key] = field
            frame.layout().addWidget(field)
            status = InlineMessage("Not yet validated", "info")
            self.statuses[key] = status
            frame.layout().addWidget(status)
            actions = QHBoxLayout()
            for caption, callback in (("Browse", lambda checked=False, k=key: self.browse(k)),
                ("Auto detect" if key.endswith("executable") else "Use default", lambda checked=False, k=key: self.auto_detect(k)),
                ("Reset", lambda checked=False, k=key: self.fields[k].clear()),
                ("Open folder", lambda checked=False, k=key: self.open_path(k))):
                actions.addWidget(Button(caption, callback))
            actions.addStretch()
            frame.layout().addLayout(actions)
            layout.addWidget(frame)
        roots = AppCard("Additional search roots", "Optional local folders, separated by semicolons. Searches remain bounded.")
        self.extra_roots = QLineEdit(";".join(service.registry.config["extra_search_roots"]))
        roots.layout().addWidget(self.extra_roots)
        layout.addWidget(roots)
        self.apply_button = Button("Apply analysis settings", self.apply, True)
        layout.addWidget(self.apply_button, alignment=Qt.AlignLeft)
        layout.addStretch()
        self.reload()
        if service.registry.config_error:
            self.error.show_error("GDL settings could not be read", service.registry.config_error)

    def reload(self):
        for key, field in self.fields.items():
            try:
                value = self.service.registry.resolve(key, self.window.results)
                field.setText(value)
                self.originals[key] = value
            except (OSError, ValueError) as exc:
                field.clear()
                self.originals[key] = ""
                self.statuses[key].set_message(str(exc), "warning")

    def validate_paths(self):
        self.skeleton.show()
        self.window.work(lambda: self.service.validate_paths(self.window.results), self.validated, self.failed)

    def validated(self, rows):
        self.skeleton.hide()
        for key, result in rows.items():
            self.statuses[key].set_message(result["status"] + " · " + result["message"], "success" if result["status"] == "Ready" else "warning")
            # Detection may finish after the screen opened; never overwrite a pending edit.
            if self.fields[key].text() == self.originals[key]:
                self.fields[key].setText(result["path"])
                self.originals[key] = result["path"]

    def failed(self, error):
        self.skeleton.hide()
        self.apply_button.set_loading(False)
        self.error.show_error("Analysis settings need attention", error)

    def browse(self, key):
        value = QFileDialog.getOpenFileName(self, "Locate " + FIELDS[key], self.fields[key].text(), "Executables (*.exe)")[0] if key.endswith("executable") else QFileDialog.getExistingDirectory(self, "Choose " + FIELDS[key], self.fields[key].text())
        if value:
            self.fields[key].setText(value)

    def auto_detect(self, key):
        if key.endswith("executable"):
            # Use a copy without this explicit override, so Auto detect is an explicit choice.
            proxy = copy.copy(self.service.store)
            proxy.local = copy.deepcopy(proxy.local)
            proxy.local["paths"].pop("fiji" if key == "fiji_executable" else "jmp", None)
            self.skeleton.show()
            def done(value):
                self.skeleton.hide()
                if value:
                    self.fields[key].setText(value)
                else:
                    self.statuses[key].set_message("Not found. Browse to the application.", "warning")
            self.window.work(lambda: detect_dependency(proxy, key, self.service.registry.config["extra_search_roots"]), done, self.failed)
        else:
            self.fields[key].clear()
            self.statuses[key].set_message("Default will be used after Apply.", "info")

    def open_path(self, key):
        try:
            path = Path(self.fields[key].text() or self.service.registry.resolve(key, self.window.results))
            open_resource(str(path.parent if key.endswith("executable") else path))
        except Exception as exc:
            self.failed(exc)

    def apply(self):
        if self.window.gdl_panel.busy:
            self.failed("Wait for the current analysis action to finish, then apply settings.")
            return
        values = {key: field.text().strip() for key, field in self.fields.items() if field.text().strip() != self.originals[key]}
        # Sharing only user-edited folders avoids turning displayed defaults into frozen overrides.
        existing_shared = self.service.store.project.get("gdl_analysis", {}).get("paths", {})
        shared_change = (self.share.isChecked() and self.service.store.provider and any(key in SHAREABLE for key in values)) or any(key in existing_shared and not value for key, value in values.items())
        if shared_change and QMessageBox.question(self, "Apply shared analysis folders?", "Folders inside project storage will be saved for the team, with revision history. Executables and external folders remain local.") != QMessageBox.Yes:
            return
        input_mode, output_mode = self.input_mode.currentText(), self.output_mode.currentText()
        roots = [p.strip() for p in self.extra_roots.text().split(";") if p.strip()]
        share = self.share.isChecked()
        self.error.hide()
        self.apply_button.set_loading(True, "Saving…")
        def save():
            if self.service.active():
                raise ValueError("Finish the active watchdog session before changing analysis paths.")
            checks = {key: self.service.registry.validate(key, value) for key, value in values.items() if value}
            if any(row["status"] != "Ready" for row in checks.values()):
                return checks
            self.service.registry.save_paths(values, share, input_mode, output_mode, roots)
            return {}
        def done(checks):
            self.apply_button.set_loading(False)
            if checks:
                for key, check in checks.items():
                    bad = check["status"] != "Ready"
                    self.fields[key].setProperty("state", "error" if bad else "normal")
                    repolish(self.fields[key])
                    self.statuses[key].set_message(check["message"], "error" if bad else "success")
                return
            for field in self.fields.values():
                field.setProperty("state", "normal")
                repolish(field)
            self.reload()
            if shared_change:
                self.window.render_settings()
            self.window.render_activity()
            self.window.scan()
            self.window.gdl_panel.refresh()
            notify(self.window, "Analysis settings saved", "success")
        self.window.work(save, done, self.failed)


class GDLPanel(QWidget):
    def __init__(self, service, window):
        super().__init__()
        self.service, self.window = service, window
        self.busy = False
        self.polling = False
        self.last_state = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(SectionHeader("GDL Analysis", "Launch the existing Fiji interface and manage engine versions here."))
        self.error = ErrorBanner()
        layout.addWidget(self.error)
        self.engine = AppCard("YOURE A BETA GDL Analysis", icon_name="software")
        self.version = label("")
        self.engine.layout().addWidget(self.version)
        self.dependencies = InlineMessage("Configure Fiji and JMP under Analysis Tools.", "info")
        self.engine.layout().addWidget(self.dependencies)
        row = QHBoxLayout()
        self.launch_button = Button("Launch GDL Analysis", self.launch, True)
        row.addWidget(self.launch_button)
        row.addWidget(Button("Analysis settings", window.open_analysis_settings))
        self.validate_button = Button("Validate paths", self.validate)
        row.addWidget(self.validate_button)
        row.addStretch()
        self.engine.layout().addLayout(row)
        layout.addWidget(self.engine)
        self.skeleton = SkeletonCard("Checking analysis dependencies…")
        self.skeleton.hide()
        layout.addWidget(self.skeleton)
        run = AppCard("Analysis session", icon_name="activity")
        self.state = StatusPill("No session yet")
        self.run_detail = label("The full analysis interface opens in Fiji. Processing settings and Quick Runs stay there.", "muted")
        run.layout().addWidget(self.state)
        run.layout().addWidget(self.run_detail)
        run_actions = QGridLayout()
        for index, (title, callback) in enumerate((("Open input folder", lambda: self.open_folder("default_input_folder")),
            ("Open output folder", self.open_output), ("Quick Runs", lambda: self.open_folder("quick_run_folder")),
            ("View latest log", self.view_log), ("Open log folder", lambda: self.window.guard(service.open_logs)))):
            run_actions.addWidget(Button(title, callback), index // 3, index % 3)
        self.stop_button = Button("Stop watchdog monitoring", self.stop)
        self.stop_button.setEnabled(False)
        run_actions.addWidget(self.stop_button, 1, 2)
        run.layout().addLayout(run_actions)
        self.report_button = Button("View generated report", self.view_report)
        self.report_button.hide()
        run.layout().addWidget(self.report_button, alignment=Qt.AlignLeft)
        run.layout().addWidget(label("To cancel processing safely, use the existing controls inside Fiji. Stopping monitoring disables automatic relaunch and keeps Fiji open.", "muted"))
        layout.addWidget(run)
        package = AppCard("Engine updates", "Import a complete GDL ZIP here. The current version stays available for rollback; custom Quick Run folders are preserved.", "history")
        self.package_status = InlineMessage("Updates are installed only when you request them.", "info")
        package.layout().addWidget(self.package_status)
        actions = QHBoxLayout()
        self.import_button = Button("Import / update ZIP", self.import_zip, True)
        self.check_button = Button("Check for engine updates", self.check_zip)
        self.rollback_button = Button("Roll back engine", self.rollback)
        for control in (self.import_button, self.check_button, self.rollback_button):
            actions.addWidget(control)
        package.layout().addLayout(actions)
        self.install_available = Button("Install available update", self.update_available, True)
        self.install_available.hide()
        package.layout().addWidget(self.install_available, alignment=Qt.AlignLeft)
        package.layout().addWidget(Button("Import legacy path overrides", self.import_legacy))
        layout.insertWidget(4, package)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.poll)
        self.refresh()
        QTimer.singleShot(0, self.validate)

    def refresh(self):
        try:
            manifest = self.service.registry.manifest()
            self.version.setText("Engine v" + str(manifest.get("version", "Unknown")))
            if self.service.registry.config_error:
                self.error.show_error("GDL settings could not be read", self.service.registry.config_error)
            self.rollback_button.setEnabled(bool(self.service.registry.config.get("previous_engine")))
            if self.service.session:
                self.display_status(dict(self.service.session))
                if self.service.session.get("status_file"):
                    self.timer.start()
        except Exception as exc:
            self.fail(exc)

    def validate(self):
        if self.busy:
            return
        self.skeleton.show()
        self.validate_button.set_loading(True, "Checking…")
        self.busy = True
        self.window.work(lambda: self.service.validate_paths(self.window.results), self.validated, self.fail)

    def validated(self, rows):
        self.busy = False
        self.skeleton.hide()
        self.validate_button.set_loading(False)
        essentials = ("fiji_executable", "jmp_executable", "analysis_engine_root", "module_folder")
        if self.service.registry.config["output_mode"] in ("Project default", "Custom configured folder"):
            essentials += ("default_output_folder",)
        missing = [FIELDS[key] for key in essentials if rows[key]["status"] != "Ready"]
        self.dependencies.set_message("Needs setup: " + ", ".join(missing) + ". Open Analysis settings." if missing else "Fiji, JMP and the analysis engine are ready.", "warning" if missing else "success")
        self.window.gdl_settings.validated(rows)

    def fail(self, error):
        self.busy = False
        self.polling = False
        self.skeleton.hide()
        for control in (self.launch_button, self.validate_button, self.import_button, self.check_button, self.rollback_button):
            control.set_loading(False)
        self.error.show_error("GDL analysis needs attention", error)

    def open_folder(self, key):
        self.window.guard(lambda: open_resource(self.service.registry.resolve(key, self.window.results)))

    def open_output(self):
        self.window.guard(lambda: open_resource(self.service.resolve_output()))

    def launch(self):
        if self.busy:
            return
        registry = self.service.registry
        input_folder, output_folder = None, None
        if registry.config["input_mode"] == "Choose at launch" or (registry.config["input_mode"] == "Remember last folder" and not registry.config.get("last_input")):
            input_folder = QFileDialog.getExistingDirectory(self, "Choose GDL input folder")
            if not input_folder:
                return
        if registry.config["output_mode"] == "Ask when analysis starts" or (registry.config["output_mode"] == "Remember last folder" and not registry.config.get("last_output")):
            output_folder = QFileDialog.getExistingDirectory(self, "Choose GDL output folder")
            if not output_folder:
                return
        try:
            proposed = output_folder or (registry.config.get("last_output", "") if registry.config["output_mode"] == "Remember last folder" else registry.resolve("default_output_folder"))
            text = "GDL Analysis requires a clean Fiji session. The launcher may close all open Fiji/ImageJ windows, including during crash recovery. Save unrelated Fiji work before continuing."
            if proposed and len(proposed) + 100 > 240:
                text += "\n\nThis output path may be too long for JMP. Consider a shorter configured folder. Continue anyway?"
            if QMessageBox.question(self, "Launch GDL Analysis?", text) != QMessageBox.Yes:
                return
        except Exception as exc:
            self.fail(exc)
            return
        self.busy = True
        self.error.hide()
        self.launch_button.set_loading(True, "Starting analysis…")
        snapshot = copy.deepcopy(self.window.results)
        self.window.work(lambda: self.service.launch_analysis(snapshot, input_folder, output_folder), self.launched, self.fail)

    def launched(self, session):
        self.busy = False
        self.launch_button.set_loading(False)
        self.launch_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.import_button.setEnabled(False)
        self.rollback_button.setEnabled(False)
        self.display_status(session)
        self.timer.start()
        notify(self.window, "GDL watchdog started", "success")

    def poll(self):
        if self.polling or self.busy:
            return
        self.polling = True
        self.window.work(lambda: (self.service.read_status(), self.service.active()), self.polled, self.fail)

    def polled(self, value):
        self.polling = False
        status, active = value
        self.display_status(status)
        self.launch_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        for control in (self.import_button, self.rollback_button):
            control.setEnabled(not active)
        if not active:
            self.timer.stop()

    def display_status(self, status):
        state = status.get("state", "IDLE")
        self.state.set_status(STATES.get(state, "No session yet"), "success" if state == "COMPLETED" else "error" if state in ("FAILED", "LAUNCH_FAILED") else "info")
        self.run_detail.setText("Started " + local_datetime(status.get("started")) + "\n" + status.get("message", "") + "\nOutput: " + (status.get("actual_output") or status.get("output_folder", "")))
        if state in ("FAILED", "LAUNCH_FAILED") and status.get("details"):
            self.error.show_error("Analysis failed", status["details"])
            self.error.message.set_message(status.get("message", "View the session log and retry."), "error")
        if state in TERMINAL and self.last_state and state != self.last_state:
            notify(self.window, "GDL analysis " + STATES.get(state, state).lower(), "error" if state in ("FAILED", "LAUNCH_FAILED") else "info")
        self.last_state = state
        self.report_button.setVisible(bool(status.get("reports")))

    def view_report(self):
        reports = self.service.session.get("reports", [])
        if reports:
            self.window.guard(lambda: open_resource(reports[0]))

    def stop(self):
        self.window.guard(self.service.stop_analysis)
        self.poll()

    def view_log(self):
        path = self.service.session.get("watchdog_log") or self.service.session.get("launcher_log")
        if not path or not Path(path).is_file():
            self.fail("No log is available yet. Launch an analysis session first.")
            return
        def read():
            chunks = []
            for key in ("watchdog_log", "launcher_log"):
                value = self.service.session.get(key)
                if value and Path(value).is_file():
                    with open(value, "rb") as file:
                        file.seek(max(0, Path(value).stat().st_size - 128_000))
                        chunks.append(Path(value).name + "\n" + file.read().decode("utf-8", "replace"))
            return "\n\n".join(chunks)
        def show(contents):
            dialog = QDialog(self.window)
            dialog.setWindowTitle("GDL session logs")
            dialog.resize(900, 600)
            layout = QVBoxLayout(dialog)
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText(contents)
            layout.addWidget(text)
            layout.addWidget(Button("Close", dialog.accept))
            dialog.exec()
        self.window.work(read, show, self.fail)

    def import_zip(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import GDL analysis package", self.service.registry.config.get("package_source", ""), "GDL ZIP (*.zip)")
        if not path:
            return
        self.install_zip(path)

    def install_zip(self, path):
        if QMessageBox.question(self, "Activate this GDL package?", "This ZIP contains executable analysis code. Import a package from your trusted project source. It will be checked and activated only if compatible; the previous engine stays available for rollback.") != QMessageBox.Yes:
            return
        self.busy = True
        self.import_button.set_loading(True, "Checking package…")
        def done(manifest):
            self.busy = False
            self.import_button.set_loading(False)
            self.package_status.set_message("GDL v" + manifest["version"] + " installed. Previous engine retained for rollback.", "success")
            self.install_available.hide()
            self.refresh()
            self.window.render_software()
            self.window.render_activity()
            self.window.gdl_settings.reload()
            self.validate()
            notify(self.window, "GDL engine updated to v" + manifest["version"], "success")
        self.window.work(lambda: self.service.install_package(path), done, self.fail)

    def check_zip(self):
        if self.busy:
            return
        self.busy = True
        self.check_button.set_loading(True, "Checking…")
        def done(message):
            self.busy = False
            self.check_button.set_loading(False)
            self.package_status.set_message(message, "info")
            self.install_available.setVisible(bool(self.service.available_update))
        self.window.work(self.service.check_package, done, self.fail)

    def update_available(self):
        if not self.busy and self.service.available_update:
            self.install_zip(self.service.available_update["path"])

    def rollback(self):
        if self.busy or QMessageBox.question(self, "Roll back GDL engine?", "Switch to the previous engine? Your configured data folders will be kept.") != QMessageBox.Yes:
            return
        self.busy = True
        def done(_):
            self.busy = False
            self.refresh()
            self.window.render_software()
            self.window.render_activity()
            self.window.gdl_settings.reload()
            self.validate()
            notify(self.window, "Previous GDL engine restored", "success")
        self.window.work(self.service.rollback_package, done, self.fail)

    def import_legacy(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose legacy GDL package")
        if not folder:
            return
        candidates = self.service.registry.legacy_candidates(folder)
        roots = self.service.registry.legacy_roots(folder)
        if not candidates and not roots:
            self.package_status.set_message("No valid unconfigured paths found in startup_paths.ini. Existing Hub settings were kept.", "info")
            return
        names = [FIELDS[k] for k in candidates] + (["Additional search roots"] if roots else [])
        if QMessageBox.question(self, "Import legacy paths?", "Import valid local overrides for: " + ", ".join(names) + "? The legacy file and current Hub overrides will be kept.") != QMessageBox.Yes:
            return
        self.window.guard(lambda: self.service.registry.save_paths(candidates, extra_roots=roots or None))
        self.window.gdl_settings.reload()
        self.validate()
