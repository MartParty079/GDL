"""Provider-backed storage setup and file browsing surfaces."""
import copy
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QMessageBox, QWizard, QWizardPage,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QApplication, QDialog, QTextEdit, QCheckBox, QGridLayout, QProgressBar, QCompleter, QInputDialog)

from app.services.project_storage import LocalOneDriveProvider, IndexCancelled, search_items
from app.services.software import open_resource
from app.ui.components import (label, button, Button, AppCard, EmptyState, SectionHeader, InlineMessage,
    StatusPill, SearchField, SkeletonTable, ErrorBanner, local_datetime, notify, friendly_error)
from app.ui.theme import repolish


def text(value):
    return label(value)


def action(caption, callback):
    return Button(caption, callback)


from app.services.formatting import format_file_size as size_text


class IndexWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(int)
    cancelled_result = Signal(str)

    def __init__(self, provider, rebuild, parent):
        super().__init__(parent)
        self.provider, self.rebuild = provider, rebuild
        self.cancelled = threading.Event()

    def run(self):
        try:
            result = self.provider.refresh(self.rebuild, self.cancelled.is_set, self.progress.emit)
            self.completed.emit(result)
        except IndexCancelled as exc:
            self.cancelled_result.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class RootWizard(QWizard):
    """Validate without writes; accepting the wizard is the setup commit point."""
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.provider = None
        self.allow_unmarked = False
        self.setWindowTitle("Connect synced project storage")
        self.resize(680, 480)
        page = QWizardPage()
        page.setTitle("Choose your locally synced project folder")
        layout = QVBoxLayout(page)
        layout.addWidget(text("Sync the project library with OneDrive first, then select its project folder. The Hub will not move, copy, or reorganize your files."))
        form = QFormLayout()
        self.project_name = QLineEdit(store.project.get("storage", {}).get("project_name", "Fuel Cell Capstone"))
        self.root_field = QLineEdit(store.local.get("local_project_root", ""))
        self.online_field = QLineEdit(store.project.get("storage", {}).get("online_url", ""))
        self.validation_error = InlineMessage()
        self.validation_error.hide()
        form.addRow("Shared project name", self.project_name)
        form.addRow("Local synced folder", self.root_field)
        form.addRow("Online SharePoint / OneDrive URL", self.online_field)
        layout.addLayout(form)
        layout.addWidget(action("Locate Synced Folder", self.locate))
        layout.addWidget(self.validation_error)
        self.addPage(page)
        validation = QWizardPage()
        validation.setTitle("Check access and project structure")
        validation_layout = QVBoxLayout(validation)
        self.validation_message = text("")
        validation_layout.addWidget(self.validation_message)
        self.create_folders = QCheckBox("Create missing standard folders when I finish setup")
        validation_layout.addWidget(self.create_folders)
        validation_layout.addWidget(text("Finish creates only the project marker if needed, saves this root in your local profile, and builds the initial index. Missing standard folders can be created afterward with Create Missing Folders. Cancel leaves storage unchanged."))
        self.addPage(validation)

    def locate(self):
        chosen = QFileDialog.getExistingDirectory(self, "Locate synced project folder", self.root_field.text())
        if chosen:
            self.root_field.setText(chosen)

    def validateCurrentPage(self):
        if self.currentId() != 0:
            return True
        try:
            self.allow_unmarked = False
            if hasattr(self.store, 'storage_settings'):
                self.store.storage_settings.protect_research_source(self.root_field.text())
            provider = LocalOneDriveProvider(self.root_field.text(), self.store.local_dir / "index")
            if not self.root_field.text().strip():
                raise ValueError("Select a synced project folder.")
            try:
                marker = provider.validate_root(require_marker=False)
            except ValueError as exc:
                if "no project marker or known project folders" not in str(exc):
                    raise
                if QMessageBox.question(self, "Confirm project library", "This folder has no project marker or known project folders. Is it the intended fuel-cell project library?\n\n" + self.root_field.text()) != QMessageBox.Yes:
                    return False
                self.allow_unmarked = True
                marker = provider.validate_root(require_marker=False, allow_unmarked=True)
            from app.services.project_storage import STANDARD_FOLDERS, validate_shared_settings
            validate_shared_settings({"storage": {"online_url": self.online_field.text().strip()}})
            if not self.project_name.text().strip():
                raise ValueError("Enter the shared project name.")
            missing = [name for name in STANDARD_FOLDERS if not provider.exists(name)]
            self.validation_message.setText("Folder access: available\nProject marker: " + ("valid" if marker else "will be created on Finish") + "\n\nMissing folders:\n" + ("\n".join(missing) if missing else "None") + "\n\nIf marker creation is not writable, setup reports the error and leaves your current root selected.")
            self.provider = provider
            return True
        except (OSError, ValueError) as exc:
            self.validation_error.set_message(friendly_error(exc), "error")
            return False

    def accept(self):
        try:
            if self.store.shared_required:
                raise ValueError('Use verified shared project setup; independent library initialization is disabled.')
            settings = copy.deepcopy(self.store.project)
            settings.setdefault('storage', {}).update(project_name=self.project_name.text().strip(), online_url=self.online_field.text().strip())
            self.provider.accept_root(self.project_name.text(), settings, self.allow_unmarked)
            self.store.connect_storage(str(self.provider.root))
            if self.create_folders.isChecked():
                created = self.store.provider.create_missing_folders()
                self.store.record("Storage", "Project structure folders created: " + ", ".join(created))
        except (OSError, ValueError) as exc:
            self.validation_message.setText("Storage could not be connected. " + friendly_error(exc))
            return
        super().accept()


class StoragePanel(QWidget):
    changed = Signal()
    busy_changed = Signal(bool)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.worker = None
        self.indexing = False
        self.index_error = ""
        self.initial_index = False
        self.last_message = ""
        self.previous_status = ""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(SectionHeader("Shared storage", "OneDrive / SharePoint owns your files. The Hub keeps a local index."))
        frame = AppCard("Project library", icon_name="storage")
        layout.addWidget(frame)
        form = QFormLayout()
        self.name = QLineEdit()
        self.online = QLineEdit()
        self.root = QLineEdit()
        self.root.setPlaceholderText('Select or enter your locally synced project folder')
        self.status_label = StatusPill()
        self.last = text("")
        self.count = text("")
        self.size = text("")
        for caption, widget in (("Shared project name", self.name), ("Local synced folder", self.root),
                ("Online SharePoint / OneDrive URL", self.online)):
            form.addRow(caption, widget)
        form.setSpacing(12)
        frame.layout().addLayout(form)
        root_controls = QHBoxLayout()
        for caption, callback in (('Browse', self.browse_root), ('Change folder', self.change_root), ('Validate', self.validate_root), ('Open folder', lambda: self.run(lambda p: p.open_folder())), ('Reset local mapping', self.reset_root)):
            control = action(caption, callback)
            root_controls.addWidget(control)
        frame.layout().addLayout(root_controls)
        frame.layout().addWidget(label('This path is saved only on this computer. Changing it leaves files in place.', 'muted'))
        related = QHBoxLayout()
        for title in ('Analysis Tools',):
            related.addWidget(action(title, lambda checked=False, name=title: self.window().open_settings(next(i for i in range(self.window().settings_tabs.count()) if self.window().settings_tabs.tabText(i) == name))))
        frame.layout().addLayout(related)
        metrics = QHBoxLayout()
        for caption, widget in (("Storage status", self.status_label), ("Last indexed", self.last), ("Files indexed", self.count), ("Indexed size", self.size)):
            column = QVBoxLayout()
            column.addWidget(label(caption, "muted"))
            column.addWidget(widget)
            metrics.addLayout(column, 1)
        frame.layout().addLayout(metrics)
        self.apply = action("Apply shared storage settings", self.apply_settings)
        frame.layout().addWidget(self.apply, alignment=Qt.AlignLeft)
        self.locate_button = action("Locate Synced Folder", self.setup)
        self.refresh_button = action("Refresh Index", lambda: self.start_index(False))
        self.rebuild_button = action("Rebuild Index", lambda: self.start_index(True))
        self.create_button = action("Create Missing Folders", self.create_folders)
        self.cancel_button = action("Cancel indexing", self.cancel_index)
        self.refresh_button.setProperty("primary", True)
        for widgets in ((action("Open Local Folder", lambda: self.run(lambda p: p.open_folder())), action("Open Online", self.open_online), self.refresh_button, self.cancel_button),):
            row = QHBoxLayout()
            for widget in widgets:
                row.addWidget(widget)
            layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.advanced = Button("Show advanced actions", self.toggle_advanced, variant="quiet")
        layout.addWidget(self.advanced, alignment=Qt.AlignLeft)
        self.advanced_box = AppCard("Advanced storage actions")
        for control in (self.locate_button, self.rebuild_button, self.create_button, action("Open OneDrive", self.open_onedrive), action("View index warnings", self.show_warnings)):
            self.advanced_box.layout().addWidget(control)
        self.advanced_box.hide()
        layout.addWidget(self.advanced_box)
        self.structure = text("")
        self.notice = InlineMessage()
        layout.addWidget(self.structure)
        layout.addWidget(self.notice)
        self.error = ErrorBanner()
        layout.addWidget(self.error)
        self.setup_state = EmptyState("Connect your project library", "Select the folder you synced with OneDrive. Files and datasets stay in the library.", "Connect storage", self.setup, "storage")
        layout.addWidget(self.setup_state)
        layout.addStretch()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.refresh_status)
        self.poll.start(5000)
        self.reload_fields()

    def reload_fields(self):
        settings = self.store.project.get("storage", {})
        self.name.setText(settings.get("project_name", "Fuel Cell Capstone"))
        self.online.setText(settings.get("online_url", ""))
        self.root.setText(self.store.local.get("local_project_root", ""))
        self.refresh_status()

    def run(self, callback):
        try:
            if not self.store.provider:
                raise ValueError("Shared project folder unavailable. Locate the synced folder first.")
            return callback(self.store.provider)
        except (OSError, ValueError) as exc:
            self.error.show_error("Storage action unavailable", exc)

    def toggle_advanced(self):
        visible = not self.advanced_box.isVisible()
        self.advanced_box.setVisible(visible)
        self.advanced.setText("Hide advanced actions" if visible else "Show advanced actions")

    def refresh_status(self):
        provider = self.store.provider
        status = "Indexing" if self.indexing else provider.status() if provider else "Unavailable" if self.store.local.get("local_project_root") else "Needs Setup"
        if self.index_error and status == "Connected":
            status = "Index Error"
        if self.previous_status and status != self.previous_status and not self.indexing:
            if status == "Unavailable":
                self.store.record("Storage", "Shared storage unavailable")
            elif self.previous_status == "Unavailable" and status == "Connected":
                self.store.record("Storage", "Shared storage restored")
        self.previous_status = status
        self.status_label.set_status(status + (" · Shared project folder unavailable" if status == "Unavailable" else ""),
            "success" if status == "Connected" else "error" if status == "Index Error" else "info" if status == "Indexing" else "warning")
        self.locate_button.setText("Locate Again" if status == "Unavailable" else "Locate Synced Folder")
        for widget in (self.locate_button, self.refresh_button, self.rebuild_button, self.create_button, self.apply):
            widget.setEnabled(not self.indexing)
        self.cancel_button.setEnabled(self.indexing)
        self.refresh_button.set_loading(self.indexing, "Refreshing…")
        self.progress.setVisible(self.indexing)
        self.setup_state.setVisible(status in ("Needs Setup", "Unavailable"))
        if status == "Unavailable":
            self.advanced_box.show()
        self.notice.set_message(self.last_message or "Local availability is shown; OneDrive sync completion is not measured.", "info")
        if self.index_error or self.store.storage_error:
            self.error.show_error("Index unavailable", self.index_error or self.store.storage_error)
        else:
            self.error.hide()
        if provider and status in ("Connected", "Index Error", "Indexing"):
            try:
                summary = provider.summary()
                self.last.setText(local_datetime(summary["last_index_time"]) if summary["last_index_time"] else "Not indexed yet")
                self.count.setText(f"{summary['files']:,}" + (f" · {summary['unavailable']:,} unavailable records retained" if summary["unavailable"] else ""))
                self.size.setText(size_text(summary["size"]))
                self.structure.setText("Missing standard folders: " + ", ".join(provider.missing_folders()) if provider.missing_folders() else "Standard project folders are present.")
            except (OSError, ValueError) as exc:
                self.error.show_error("Storage summary unavailable", exc)
        else:
            self.last.setText("Unavailable")
            self.count.setText("—")
            self.size.setText("—")
            self.structure.setText("Select your synced project library to connect.")

    def setup(self):
        wizard = RootWizard(self.store, self)
        if wizard.exec():
            self.index_error = ""
            self.reload_fields()
            self.changed.emit()
            self.start_index(False)

    def browse_root(self):
        chosen = QFileDialog.getExistingDirectory(self, 'Choose local synced project folder', self.root.text())
        if chosen:
            self.root.setText(chosen)

    def validate_root(self):
        try:
            self.store.storage_settings.validate_root(self.root.text().strip())
            self.notice.set_message('Folder is readable and has a project marker or recognized project structure.', 'success')
        except (OSError, ValueError) as exc:
            self.error.show_error('Folder validation failed', exc)

    def change_root(self):
        if self.indexing:
            self.notice.set_message('Wait for indexing to finish before changing the root.', 'warning')
            return
        root = self.root.text().strip()
        if not root:
            self.error.show_error('Choose a folder', 'Enter a local project folder or use Browse.')
            return
        try:
            provider = LocalOneDriveProvider(root, self.store.local_dir / 'index')
            marker = provider.validate_root(require_marker=False, allow_unmarked=True)
            initialize = not bool(marker)
            prompt = ('Initialize a project marker in this folder and use it as the local mapping?' if initialize else 'Change this computer’s project mapping to this folder?') + '\n\n' + str(provider.root) + '\n\nExisting files stay in place. The index will refresh for this mapping.'
            if QMessageBox.question(self, 'Change project folder', prompt) != QMessageBox.Yes:
                return
            self.store.storage_settings.change_root(root, initialize)
            self.reload_fields()
            self.changed.emit()
            self.start_index(False)
        except (OSError, ValueError) as exc:
            self.error.show_error('Project mapping could not be changed', exc)

    def reset_root(self):
        if self.indexing:
            self.notice.set_message('Wait for indexing before resetting the mapping.', 'warning')
            return
        if QMessageBox.question(self, 'Reset local mapping?', 'Clear only this computer’s local project mapping? Cloud connections, historical definitions and files will be preserved.') != QMessageBox.Yes:
            return
        try:
            self.store.storage_settings.reset_root()
            self.reload_fields()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.error.show_error('Local mapping could not be reset', exc)

    def apply_settings(self):
        value = copy.deepcopy(self.store.project)
        value.setdefault('storage', {}).update(project_name=self.name.text().strip(), online_url=self.online.text().strip())
        if not value["storage"]["project_name"]:
            self.notice.set_message("Enter the shared project name.", "warning")
            return
        if QMessageBox.question(self, "Apply storage settings?", "Apply these project-wide storage settings? The local synced root is kept only in your profile.") != QMessageBox.Yes:
            return
        try:
            self.store.save_project(value, "Shared storage settings changed")
            self.changed.emit()
            notify(self, "Storage settings saved", "success")
        except (OSError, ValueError) as exc:
            self.error.show_error("Storage settings could not be saved", exc)

    def create_folders(self):
        def create(provider):
            missing = provider.missing_folders()
            if not missing:
                return
            if QMessageBox.question(self, "Create missing folders?", "Create only these missing folders? Existing files and folders will remain in place.\n\n" + "\n".join(missing)) == QMessageBox.Yes:
                created = provider.create_missing_folders()
                self.store.record("Storage", "Project structure folders created: " + ", ".join(created))
                self.refresh_status()
                self.changed.emit()
                notify(self, "Missing project folders created", "success")
        self.run(create)

    def start_index(self, rebuild=False):
        if self.indexing:
            return
        provider = self.store.provider
        if not provider or provider.status() == "Unavailable":
            self.notice.set_message("Connect your synced project folder before indexing.", "warning")
            self.setup_state.show()
            return
        self.indexing = True
        self.index_error = ""
        self.last_message = ""
        self.worker = IndexWorker(provider, rebuild, self)
        self.initial_index = not provider.summary()["last_index_time"]
        self.worker.completed.connect(self.index_done)
        self.worker.failed.connect(self.index_failed)
        self.worker.cancelled_result.connect(self.index_cancelled)
        self.worker.progress.connect(lambda count: self.status_label.setText(f"Indexing project files… {count:,} scanned"))
        self.worker.finished.connect(self.index_finished)
        self.refresh_status()
        self.busy_changed.emit(True)
        self.worker.start()

    def index_done(self, summary):
        changes = summary["changes"]
        operation = "Full index rebuilt" if self.worker.rebuild else "Initial index built" if self.initial_index else "Index refreshed"
        self.store.record("Storage", f"{operation}: {summary['files']} files; {changes['added']} added, {changes['modified']} modified, {changes['removed']} removed, {len(summary['warnings'])} warnings")
        self.changed.emit()
        notify(self, f"{operation}: {summary['files']:,} files indexed", "success")

    def index_failed(self, message):
        self.index_error = message
        self.changed.emit()
        notify(self, "The index could not be refreshed. Review Storage for recovery options.", "error")

    def index_cancelled(self, message):
        self.last_message = message
        self.index_error = ""

    def index_finished(self):
        self.indexing = False
        self.worker.deleteLater()
        self.worker = None
        self.refresh_status()
        self.busy_changed.emit(False)
        self.changed.emit()

    def cancel_index(self):
        if self.worker:
            self.worker.cancelled.set()
            self.status_label.setText("Cancelling indexing…")

    def open_online(self):
        try:
            open_resource(self.store.project.get("storage", {}).get("online_url", ""))
        except (OSError, ValueError) as exc:
            self.error.show_error("Online storage could not be opened", exc)

    def open_onedrive(self):
        item = next(i for i in self.store.manifest if i["id"] == "onedrive")
        from app.services.software import detect, launch
        try:
            launch(item, detect(item, self.store.local["paths"].get("onedrive")))
        except (OSError, ValueError) as exc:
            self.error.show_error("OneDrive unavailable", "Configure OneDrive under Software, then retry.")

    def show_warnings(self):
        provider = self.store.provider
        try:
            warnings = provider.summary()["warnings"] if provider else []
        except (OSError, ValueError):
            warnings = []
        dialog = QDialog(self)
        dialog.setWindowTitle("Index warnings")
        dialog.resize(720, 420)
        layout = QVBoxLayout(dialog)
        output = QTextEdit()
        output.setReadOnly(True)
        output.setPlainText("\n\n".join(w["path"] + ": " + w["message"] for w in warnings) or "No index warnings.")
        layout.addWidget(output)
        layout.addWidget(action("Close", dialog.accept))
        dialog.exec()


class FilesPanel(QWidget):
    connect_requested = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store, self.rows = store, []
        self.page, self.page_size = 0, 200
        self.loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(SectionHeader("Files & Data", "Search the project library without duplicating its files."))
        self.search = SearchField("Search files, paths, or relationship IDs…")
        self.search.setAccessibleName("Search project files")
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.populate)
        self.search.textChanged.connect(lambda: self.search_timer.start() if getattr(self, 'total_matches', len(getattr(self, 'items', []))) > 200 else self.populate())
        layout.addWidget(self.search)
        origins = QHBoxLayout()
        self.origin, self.legacy_filter = QComboBox(), QComboBox()
        for caption, value in (('Current Project', 'current'), ('Legacy Data · Old Test Data', 'legacy'), ('All Files', '')):
            self.origin.addItem(caption, value)
        self.legacy_filter.addItem('All previous projects', '')
        self.origin.currentIndexChanged.connect(self.populate)
        self.legacy_filter.currentIndexChanged.connect(self.populate)
        origins.addWidget(text('Data origin'))
        origins.addWidget(self.origin)
        origins.addWidget(text('Previous project'))
        origins.addWidget(self.legacy_filter)
        filters = QGridLayout()
        self.advanced_filters = QWidget()
        extra = QGridLayout(self.advanced_filters)
        extra.setContentsMargins(0, 0, 0, 0)
        self.advanced_filters.hide()
        self.filters = {}
        for column, (key, name) in enumerate((("category", "File Type"), ("experiment", "Experiment"), ("run", "Run"), ("sample", "Sample"), ("procedure", "Procedure"))):
            control = QComboBox()
            control.setAccessibleName(name)
            control.addItem("All", "")
            control.currentIndexChanged.connect(self.populate)
            self.filters[key] = control
            placement = {"category": 0, "experiment": 1, "sample": 2}
            if key in placement:
                filters.addWidget(text(name), 0, placement[key])
                filters.addWidget(control, 1, placement[key])
                filters.setColumnStretch(placement[key], 1)
            else:
                position = 0 if key == "run" else 1
                extra.addWidget(text(name), 0, position)
                extra.addWidget(control, 1, position)
        self.date_from, self.date_to = QLineEdit(), QLineEdit()
        self.date_from.setPlaceholderText("YYYY-MM-DD · modified from")
        self.date_to.setPlaceholderText("YYYY-MM-DD · modified through")
        self.date_from.textChanged.connect(self.populate)
        self.date_to.textChanged.connect(self.populate)
        extra.addWidget(text("From date"), 0, 2)
        extra.addWidget(self.date_from, 1, 2)
        extra.addWidget(text("Through date"), 0, 3)
        extra.addWidget(self.date_to, 1, 3)
        for column, (key, caption) in enumerate((('extension', 'Extension'), ('document_type', 'Document type'), ('source', 'Source'), ('duplicate', 'Duplicates'))):
            control = QComboBox()
            control.addItem('All', '')
            control.currentIndexChanged.connect(self.populate)
            self.filters[key] = control
            extra.addWidget(text(caption), 2, column)
            extra.addWidget(control, 3, column)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText('Filter tags')
        self.tags.textChanged.connect(self.populate)
        extra.addWidget(self.tags, 4, 0, 1, 2)
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('Filter folder')
        self.folder.textChanged.connect(self.populate)
        extra.addWidget(self.folder, 4, 2, 1, 2)
        for column, (key, caption) in enumerate((('availability', 'Availability'), ('project', 'Project'))):
            control = QComboBox()
            control.addItem('All', '')
            control.currentIndexChanged.connect(self.populate)
            self.filters[key] = control
            extra.addWidget(text(caption), 5, column)
            extra.addWidget(control, 6, column)
        self.archive = QComboBox()
        for name, key in (("Active only", "active"), ("Include Archived", "all"), ("Archived only", "archived")):
            self.archive.addItem(name, key)
        self.archive.currentIndexChanged.connect(self.populate)
        filters.addWidget(text("Archive status"), 0, 3)
        filters.addWidget(self.archive, 1, 3)
        filters.setColumnStretch(3, 1)
        layout.addLayout(filters)
        self.clear_button = Button("Clear filters", self.clear_filters, variant="quiet")
        self.more_filters = Button("More filters", self.toggle_filters, variant="quiet")
        filter_actions = QHBoxLayout()
        filter_actions.addWidget(self.more_filters)
        filter_actions.addWidget(self.clear_button)
        filter_actions.addWidget(self.origin)
        filter_actions.addWidget(self.legacy_filter)
        filter_actions.addStretch()
        layout.addLayout(filter_actions)
        layout.addWidget(self.advanced_filters)
        self.notice = InlineMessage()
        layout.addWidget(self.notice)
        self.skeleton = SkeletonTable()
        self.skeleton.hide()
        layout.addWidget(self.skeleton)
        self.empty_state = EmptyState("No indexed files", "Connect project storage and refresh the index to begin.", "Connect storage", self.connect_requested.emit)
        layout.addWidget(self.empty_state)
        self.error = ErrorBanner()
        layout.addWidget(self.error)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Name", "Category", "Experiment", "Sample", "Modified", "Size", 'Source / project', 'Availability', 'Duplicates'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFixedHeight(160)
        for column, width in enumerate((180, 100, 145, 110, 195, 80)):
            self.table.setColumnWidth(column, width)
        self.table.itemDoubleClicked.connect(lambda _: self.open_selected())
        layout.addWidget(self.table)
        self.pagination = QWidget()
        pagination = QHBoxLayout(self.pagination)
        pagination.setContentsMargins(0, 0, 0, 0)
        pagination.addWidget(Button('Previous page', lambda: self.change_page(-1)))
        self.page_label = label('')
        pagination.addWidget(self.page_label)
        pagination.addWidget(Button('Next page', lambda: self.change_page(1)))
        pagination.addStretch()
        layout.addWidget(self.pagination)
        self.file_actions = QWidget()
        row = QGridLayout(self.file_actions)
        row.setContentsMargins(0, 0, 0, 0)
        for column, (name, callback) in enumerate((("Open", self.open_selected), ("Open Folder", self.open_parent), ("Copy Path", self.copy_path), ("Metadata", self.view_metadata), ('Edit Metadata', self.edit_classification), ('Import into Current Project', self.import_current))):
            control = action(name, callback)
            if name == 'Import into Current Project':
                self.import_button = control
                row.addWidget(control, 1, 0, 1, 5, Qt.AlignLeft)
            else:
                row.addWidget(control, 0, column)
        self.related_button = action('Find related', self.find_related)
        row.addWidget(self.related_button, 2, 0, 1, 2)
        self.favorite_button = action('Toggle favorite', self.toggle_favorite)
        row.addWidget(self.favorite_button, 2, 2, 1, 2)
        layout.addWidget(self.file_actions)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.AscendingOrder)
        self.reload()

    def set_loading(self, loading):
        self.loading = loading
        self.populate()

    def toggle_filters(self):
        visible = not self.advanced_filters.isVisible()
        self.advanced_filters.setVisible(visible)
        self.more_filters.setText("Fewer filters" if visible else "More filters")

    def clear_filters(self):
        self.search.clear()
        for control in self.filters.values():
            control.setCurrentIndex(0)
        self.date_from.clear()
        self.date_to.clear()
        self.tags.clear()
        self.folder.clear()
        self.archive.setCurrentIndex(0)
        self.origin.setCurrentIndex(0)
        self.legacy_filter.setCurrentIndex(0)
        self.populate()

    def reload(self):
        provider = self.store.provider
        self.native_catalog = getattr(getattr(self.store, 'storage_settings', None), 'catalog', None)
        try:
            self.items = [] if self.native_catalog else self.store.storage_settings.files() if hasattr(self.store, 'storage_settings') else provider.list_items() if provider else []
        except (OSError, ValueError):
            self.items = []
        selected = self.legacy_filter.currentData()
        self.legacy_filter.blockSignals(True)
        self.legacy_filter.clear()
        self.legacy_filter.addItem('All previous projects', '')
        if hasattr(self.store, 'storage_settings') and self.store.storage_settings.catalog:
            for project in self.store.storage_settings.locations.value['legacy']:
                self.legacy_filter.addItem(project['name'], project['id'])
        self.legacy_filter.setCurrentIndex(max(0, self.legacy_filter.findData(selected)))
        self.legacy_filter.blockSignals(False)
        facets = self.native_catalog.facets() if self.native_catalog else {}
        for key, field in self.filters.items():
            selected = field.currentData()
            field.blockSignals(True)
            field.clear()
            field.addItem("All", "")
            record_key = {'category': 'category', 'extension': 'extension', 'document_type': 'document_type', 'source': 'source_name', 'duplicate': 'duplicate_status', 'availability': 'availability', 'project': 'project_name'}.get(key, key + '_id')
            for value in facets.get(record_key, []) if self.native_catalog else sorted({i.get(record_key, "") for i in self.items} - {""}):
                field.addItem(value, value)
            index = field.findData(selected)
            if selected and index < 0:
                field.addItem(selected, selected)
                index = field.findData(selected)
            field.setCurrentIndex(max(0, index))
            field.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            field.setMinimumContentsLength(8)
            field.setMinimumWidth(80)
            if field.count() > 15:
                field.setEditable(True)
                field.setInsertPolicy(QComboBox.NoInsert)
                field.completer().setCaseSensitivity(Qt.CaseInsensitive)
                field.completer().setFilterMode(Qt.MatchContains)
            field.blockSignals(False)
        self.populate()

    def change_page(self, direction):
        self.page = max(0, min(self.page + direction, max(0, (getattr(self, 'total_matches', len(self.rows)) - 1) // self.page_size)))
        self.populate(preserve_page=True)

    def populate(self, *args, preserve_page=False):
        if not hasattr(self, "table") or not hasattr(self, "items"):
            return
        for field in (self.date_from, self.date_to):
            value = field.text()
            field.setProperty("state", "normal")
            repolish(field)
            if value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                    if len(value) != 10:
                        raise ValueError()
                except ValueError:
                    field.setProperty("state", "error")
                    repolish(field)
                    self.notice.set_message("Use YYYY-MM-DD for date filters.", "warning")
                    return
        if not preserve_page:
            self.page = 0
        values = dict(query=self.search.text(), archive=self.archive.currentData(), origin=self.origin.currentData(),
            legacy_project=self.legacy_filter.currentData(), date_from=self.date_from.text(), date_to=self.date_to.text(),
            tags=self.tags.text(), **{key: field.currentData() for key, field in self.filters.items()})
        catalog = getattr(self, 'native_catalog', None)
        if catalog:
            self.rows, self.total_matches = catalog.query(offset=self.page * self.page_size, limit=self.page_size, folder=self.folder.text(), **values)
            self.items = self.rows
            visible_rows = self.rows
        else:
            values.pop('availability', None)
            values.pop('project', None)
            self.rows = search_items(self.items, **values)
            self.total_matches = len(self.rows)
            visible_rows = self.rows[self.page * self.page_size:(self.page + 1) * self.page_size]
        self.pagination.setVisible(self.total_matches > self.page_size)
        self.related_button.setVisible(bool(catalog))
        self.favorite_button.setVisible(bool(catalog))
        self.import_button.setVisible(bool(getattr(getattr(self.store, 'storage_settings', None), 'catalog', None)) and any(i.get('data_origin') == 'legacy' for i in visible_rows))
        self.page_label.setText(f'Page {self.page + 1} / {max(1, (self.total_matches + self.page_size - 1) // self.page_size)} · {self.total_matches:,} matches')
        active_filters = self.search.text() or any(control.currentIndex() > 0 for control in self.filters.values()) or self.date_from.text() or self.date_to.text() or self.archive.currentIndex() > 0
        self.clear_button.setVisible(bool(active_filters))
        self.skeleton.setVisible(self.loading and not self.items)
        self.empty_state.setVisible(not self.rows and not self.loading)
        self.table.setVisible(bool(self.rows))
        self.file_actions.setEnabled(bool(self.rows))
        self.file_actions.setVisible(bool(self.rows))
        if not self.rows and not self.loading:
            catalog = getattr(getattr(self.store, 'storage_settings', None), 'catalog', None)
            if not catalog and (not self.store.provider or self.store.provider.status() == "Unavailable"):
                title, description, caption, callback = "Connect project storage", "Select your synced OneDrive folder before browsing project files.", "Connect storage", self.connect_requested.emit
            elif active_filters:
                title, description, caption, callback = "No matching files", "Try another search or clear the current filters.", "Clear filters", self.clear_filters
            else:
                title, description, caption, callback = "No indexed files", "Refresh the index under Storage to discover project files.", "Open storage", self.connect_requested.emit
            self.empty_state.set_state(title, description, caption, callback)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible_rows))
        for row_number, item in enumerate(visible_rows):
            origin = ('Old Test Data · ' + item.get('legacy_project_name', '') + ' · ' + item.get('legacy_project_id', '')) if item.get('data_origin') == 'legacy' else item.get('data_origin', 'current').title()
            if item.get('data_origin') != 'legacy':
                origin += ' · ' + item.get('source_name', '')
            values = [item["name"], item["category"], item["experiment_id"], item["sample_id"], local_datetime(item["modified"]), size_text(item["size"]), origin, item.get('availability', ''), item.get('duplicate_status', '')]
            for column, value in enumerate(values):
                cell = SortableItem(str(value))
                cell.setData(Qt.UserRole, item["relative_path"])
                cell.setData(Qt.UserRole + 2, item['id'])
                if item.get('data_origin') == 'legacy':
                    from PySide6.QtGui import QColor
                    cell.setForeground(QColor('#A77832'))
                cell.setData(Qt.UserRole + 1, item["size"] if column == 5 else item["modified"] if column == 4 else str(value).casefold())
                cell.setToolTip(str(value) + "\n" + item["relative_path"] + "\nContent: " + item.get("content_status", "Metadata only"))
                self.table.setItem(row_number, column, cell)
        self.table.setSortingEnabled(not (catalog and self.search.text()))
        self.notice.set_message("Refreshing index… Showing last known files." if self.loading and self.items else "Loading project files…" if self.loading else f"{self.total_matches:,} matching {'file' if self.total_matches == 1 else 'files'}.")

    def selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            self.notice.set_message("Select a file in the list first.", "info")
            return None
        identity = self.table.item(row, 0).data(Qt.UserRole + 2)
        return next((item for item in self.rows if item['id'] == identity), None)

    def perform(self, callback):
        item = self.selected()
        if item:
            try:
                callback(self.store.provider, item)
            except (OSError, ValueError) as exc:
                self.error.show_error("File action unavailable", exc)

    def open_selected(self):
        self.perform(lambda p, i: self.store.storage_settings.open_item(i) if hasattr(self.store, 'storage_settings') else p.open_item(i['relative_path']))

    def open_parent(self):
        from pathlib import PurePosixPath
        self.perform(lambda p, i: self.store.storage_settings.open_item(i, parent=True) if hasattr(self.store, 'storage_settings') else p.open_folder(PurePosixPath(i['relative_path']).parent.as_posix()))

    def copy_path(self):
        self.perform(lambda p, i: QApplication.clipboard().setText(i.get("full_path", i["relative_path"])))
        if self.table.currentRow() >= 0:
            notify(self, "File path copied", "success")

    def view_metadata(self):
        def show(provider, item):
            import json
            dialog = QDialog(self)
            dialog.setWindowTitle(item["name"] + " · metadata")
            dialog.resize(660, 460)
            layout = QVBoxLayout(dialog)
            output = QTextEdit()
            output.setReadOnly(True)
            layout.addWidget(label('Origin: ' + item.get('data_origin', 'current') + '\nPrevious project: ' + item.get('legacy_project_name', '') + '\nReference note: ' + item.get('legacy_note', '') + '\nClassification: ' + item.get('classification_source', '') + ' · ' + item.get('classification_confidence', '') + '\nSubcategory: ' + item.get('subcategory', '')))
            output.setPlainText("\n".join(("File: " + item["name"], "Relative path: " + item["relative_path"], "Type: " + item["category"], "Experiment: " + (item["experiment_id"] or "None"), "Run: " + (item["run_id"] or "None"), "Sample: " + (item["sample_id"] or "None"), "Procedure: " + (item["procedure_id"] or "None"), "Modified: " + local_datetime(item["modified"]), "Size: " + size_text(item["size"]), "Archived: " + ("Yes" if item["archived"] else "No"), "Modified after initial indexing: " + ("Yes" if item.get("modified_after_initial_index") else "No"))))
            details = dict(item)
            if self.native_catalog:
                details['content'] = self.native_catalog.content_preview(item['id'])
                details['relationships'] = self.native_catalog.related(item['id'])
            output.setPlainText(json.dumps(details, indent=2, ensure_ascii=False))
            layout.addWidget(output)
            layout.addWidget(action("Close", dialog.accept))
            dialog.exec()
        self.perform(show)

    def edit_classification(self):
        item = self.selected()
        if not item or not hasattr(self.store, 'storage_settings'):
            return
        from app.services.file_classifier import CATEGORIES
        from app.services.research_catalog import RESEARCH_CATEGORIES
        dialog = QDialog(self)
        dialog.setWindowTitle('Edit file metadata · ' + item['name'])
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('These metadata overrides leave the file and its permanent origin unchanged.'))
        form = QFormLayout()
        category = QComboBox()
        category.addItems(list(dict.fromkeys((*CATEGORIES, *RESEARCH_CATEGORIES))))
        category.setCurrentText(item['category'])
        form.addRow('Category', category)
        fields = {}
        keys = ('subcategory', 'experiment_id', 'sample_id', 'procedure_id', 'legacy_note')
        if self.store.storage_settings.catalog:
            keys += ('run_id', 'tags', 'title', 'description', 'notes')
        for key in keys:
            fields[key] = QLineEdit(item.get(key, ''))
            form.addRow(key.replace('_', ' ').title(), fields[key])
        layout.addLayout(form)
        layout.addWidget(action('Save metadata', dialog.accept))
        layout.addWidget(action('Cancel', dialog.reject))
        if dialog.exec():
            try:
                self.store.storage_settings.set_override(item, {'category': category.currentText(), **{k: f.text().strip() for k, f in fields.items()}})
                self.reload()
            except (OSError, ValueError) as exc:
                self.error.show_error('Metadata could not be saved', exc)

    def toggle_favorite(self):
        item = self.selected()
        if item and self.native_catalog:
            self.native_catalog.set_override(item, {'favorite': not item.get('favorite', False)})
            self.reload()
            notify(self, 'Favorite updated', 'success')

    def find_related(self):
        item = self.selected()
        if not item or not self.native_catalog:
            return
        links = self.native_catalog.related(item['id'])
        dialog = QDialog(self)
        dialog.setWindowTitle('Related files · ' + item['name'])
        dialog.resize(640, 400)
        layout = QVBoxLayout(dialog)
        output = QTextEdit()
        output.setReadOnly(True)
        import json
        output.setPlainText(json.dumps(links, indent=2) if links else 'No relationships recorded. Add a relationship to another indexed file.')
        layout.addWidget(output)
        def add_relation():
            query, okay = QInputDialog.getText(dialog, 'Find related file', 'Search filename or content')
            if not okay or not query.strip():
                return
            matches, total = self.native_catalog.query(query=query, limit=100)
            matches = [r for r in matches if r['id'] != item['id']]
            if not matches:
                output.setPlainText('No other matching files. Try a different query.')
                return
            choices = {r['name'] + ' · ' + r['relative_path'] + ' · ' + r['id']: r for r in matches}
            label, okay = QInputDialog.getItem(dialog, 'Choose file', f'{total} matches (first 100)', list(choices), 0, False)
            if not okay:
                return
            kind, okay = QInputDialog.getItem(dialog, 'Relationship', 'Type', ['related_to', 'derived_from', 'supersedes', 'previous_version', 'references'], 0, False)
            if okay:
                self.native_catalog.relate(item['id'], choices[label]['id'], kind)
                output.setPlainText(json.dumps(self.native_catalog.related(item['id']), indent=2))
        layout.addWidget(action('Add relationship', add_relation))
        layout.addWidget(action('Close', dialog.accept))
        dialog.exec()

    def import_current(self):
        item = self.selected()
        settings = getattr(self.store, 'storage_settings', None)
        if not item or not settings or not settings.catalog:
            return
        if item.get('provider') != 'ResearchLocal' or item.get('data_origin') != 'legacy':
            self.notice.set_message('Select a locally indexed legacy reference to import.', 'info')
            return
        if QMessageBox.question(self, 'Copy legacy reference?', 'Copy this file into the current project? The legacy original will remain unchanged.') != QMessageBox.Yes:
            return
        try:
            destination = settings.catalog.import_current(item)
            settings.catalog.refresh(quick=True, source_ids=[settings.locations.value['active']['id']])
            self.reload()
            notify(self, 'Copied to Current Project: ' + destination.name, 'success')
        except (OSError, ValueError) as exc:
            self.error.show_error('Import unavailable', exc)


class SortableItem(QTableWidgetItem):
    def __lt__(self, other):
        return self.data(Qt.UserRole + 1) < other.data(Qt.UserRole + 1)
