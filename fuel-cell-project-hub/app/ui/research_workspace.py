"""Full-height research navigation, objects, database-paged files and details."""

import json
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSplitter,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTextEdit,
    QTabWidget,
    QFileDialog,
    QApplication,
    QMessageBox,
    QCheckBox,
    QScrollArea,
    QSizePolicy,
)
from app.services.research_workspace import (
    ResearchWorkspace,
    SAMPLE_FIELDS,
    EXPERIMENT_FIELDS,
    EXPERIMENT_TYPES,
)
from app.indexing.search import SORTS, FAMILIES
from app.services.project_locations import RESEARCH_CATEGORIES
from app.services import file_launcher, previews
from app.services.resources import resource_path
from app import __version__
from app.ui.research_viewers import Tasks, PreviewPanel, ImageViewer, ImageComparison
from app.ui.components import icon

COLORS = {
    "Overview": "#0071e3",
    "Samples": "#0f766e",
    "Experiments": "#7c3aed",
    "Images": "#0071e3",
    "Data": "#4338ca",
    "Reports": "#0f766e",
    "Timeline": "#7c3aed",
    "Files": "#0071e3",
    "Legacy": "#a16207",
    "Favorites": "#a16207",
    "Recent": "#0f766e",
    "Needs review": "#a16207",
    "Folders": "#5f6b7a",
    "Settings": "#5f6b7a",
    "Analysis tools": "#5f6b7a",
    "Resources": "#5f6b7a",
    "Software": "#5f6b7a",
}


def control(title, action, layout):
    button = QPushButton(title)
    if title.startswith(("New ", "Save ", "Accept ")) or title == "Open":
        button.setStyleSheet(
            "QPushButton {background:#0071e3;color:white;border:1px solid #0071e3;} QPushButton:hover {background:#0062c4;} QPushButton:disabled {background:#d5dae1;color:#667181;}"
        )
    button.clicked.connect(action)
    layout.addWidget(button)
    return button


def version_dialog(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("About GDL Research Hub")
    dialog.resize(700, 550)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("GDL Research Hub " + __version__))
    view = QTextEdit()
    view.setReadOnly(True)
    try:
        view.setMarkdown(resource_path("CHANGELOG.md").read_text(encoding="utf-8"))
    except OSError:
        view.setPlainText("Version history is unavailable in this installation.")
    layout.addWidget(view)
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


class ObjectEditor(QDialog):
    def __init__(self, repository, kind, obj=None, origin="current", parent=None):
        super().__init__(parent)
        self.repository = repository
        self.kind = kind
        self.obj = obj
        self.origin = origin
        self.setWindowTitle(("Edit " if obj else "New ") + kind)
        self.resize(680, 700)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        form = QFormLayout(page)
        scroll.setWidget(page)
        layout.addWidget(scroll)
        self.fields = {}
        identity = QLineEdit(obj["id"] if obj else "")
        identity.setReadOnly(bool(obj))
        identity.setPlaceholderText(
            "Optional ID, e.g. GDL-003; leave blank to generate"
        )
        self.fields["id"] = identity
        form.addRow("ID", identity)
        for name in SAMPLE_FIELDS if kind == "sample" else EXPERIMENT_FIELDS:
            if name in ("description", "notes", "procedure", "results_summary"):
                field = QTextEdit()
                field.setMaximumHeight(100)
                field.setPlainText(str((obj or {}).get(name, "")))
            elif name == "type":
                field = QComboBox()
                field.setEditable(True)
                field.addItems(list(EXPERIMENT_TYPES))
                field.setCurrentText((obj or {}).get(name, "Other"))
            elif name == "sample_id":
                field = QComboBox()
                field.addItem("Unassigned", "")
                for sample in repository.objects("sample", origin):
                    field.addItem(sample["id"] + " | " + sample["name"], sample["id"])
                field.setCurrentIndex(max(0, field.findData((obj or {}).get(name, ""))))
            else:
                field = QLineEdit(str((obj or {}).get(name, "")))
                if "date" in name:
                    field.setPlaceholderText("YYYY-MM-DD, if known")
                if name == "thickness":
                    field.setPlaceholderText("Value and unit, if known")
            self.fields[name] = field
            form.addRow(name.replace("_", " ").title(), field)
        self.metrics = {}
        if kind == "experiment":
            for name in ("conditions", "results"):
                table = QTableWidget(0, 4)
                table.setHorizontalHeaderLabels(["Name", "Value", "Unit", "Notes"])
                table.setMinimumHeight(170)
                for row in (obj or {}).get(name, []):
                    self.add_metric(table, row)
                form.addRow(name.title(), table)
                bar = QHBoxLayout()
                control(
                    "Add " + name.rstrip("s"),
                    lambda checked=False, t=table: self.add_metric(t, {}),
                    bar,
                )
                control(
                    "Remove row",
                    lambda checked=False, t=table: t.removeRow(t.currentRow()),
                    bar,
                )
                form.addRow(bar)
                self.metrics[name] = table
        self.favorite = QCheckBox("Favorite")
        self.favorite.setChecked((obj or {}).get("favorite", False))
        form.addRow(self.favorite)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color:#d92d20")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_metric(self, table, values):
        row = table.rowCount()
        table.insertRow(row)
        for column, key in enumerate(("name", "value", "unit", "notes")):
            table.setItem(row, column, QTableWidgetItem(str(values.get(key, ""))))

    def save(self):
        values = {}
        for key, field in self.fields.items():
            values[key] = (
                field.toPlainText()
                if isinstance(field, QTextEdit)
                else (
                    field.currentData()
                    if key == "sample_id"
                    else (
                        field.currentText()
                        if isinstance(field, QComboBox)
                        else field.text()
                    )
                )
            )
        for key, table in self.metrics.items():
            values[key] = [
                {
                    name: (
                        table.item(row, column).text()
                        if table.item(row, column)
                        else ""
                    )
                    for column, name in enumerate(("name", "value", "unit", "notes"))
                }
                for row in range(table.rowCount())
            ]
        values["favorite"] = self.favorite.isChecked()
        try:
            if not self.obj and values.get("id") and self.repository.get(values["id"]):
                raise ValueError(
                    "That ID already exists. Choose another ID or edit the existing object."
                )
            self.saved = self.repository.save(
                self.kind, values, values.pop("id") or None, self.origin
            )
            self.accept()
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))


class FileBrowser(QWidget):
    selected = Signal(object)

    def __init__(self, workspace, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.catalog = workspace.catalog
        self.repository = workspace.repository
        self.tasks = Tasks(self)
        self.request = 0
        self.rows = []
        self.offset = 0
        self.total = 0
        self.base = {}
        self.folder_history = []
        self.history_position = -1
        self.thumb_pending = set()
        self.loaded_thumbs = {}
        self.family = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        layout.addLayout(bar)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search names, paths, content, tags and notes")
        bar.addWidget(self.search, 1)
        self.scope = QComboBox()
        self.scope.addItems(
            [
                "Current view",
                "Current sample",
                "Current experiment",
                "Current project",
                "All indexed",
                "Legacy",
            ]
        )
        bar.addWidget(self.scope)
        self.view = QComboBox()
        self.view.addItems(["List", "Grid", "Compact"])
        bar.addWidget(self.view)
        self.sort = QComboBox()
        self.sort.addItems(list(SORTS))
        self.sort.setCurrentText("Modified newest")
        bar.addWidget(self.sort)
        filterbar = QHBoxLayout()
        layout.addLayout(filterbar)
        self.origin = QComboBox()
        self.origin.addItem("Current", "current")
        self.origin.addItem("Legacy", "legacy")
        self.origin.addItem("All origins", "")
        filterbar.addWidget(self.origin)
        self.sample = QComboBox()
        self.experiment = QComboBox()
        self.category = QComboBox()
        self.category.addItem("All categories", "")
        for category in RESEARCH_CATEGORIES:
            self.category.addItem(category, category)
        for field in (self.sample, self.experiment, self.category):
            filterbar.addWidget(field)
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("Modified from YYYY-MM-DD")
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("to YYYY-MM-DD")
        filterbar.addWidget(self.date_from)
        filterbar.addWidget(self.date_to)
        self.quick = {}
        quickbar = QHBoxLayout()
        layout.addLayout(quickbar)
        for title in (
            "All",
            "Images",
            "Reports",
            "Data",
            "Code",
            "Current",
            "Legacy",
            "Favorites",
            "Recent",
        ):
            button = control(
                title, lambda checked=False, t=title: self.quick_filter(t), quickbar
            )
            button.setCheckable(True)
            self.quick[title] = button
        self.quick["All"].setChecked(True)
        self.breadcrumb = QLabel()
        self.breadcrumb.setWordWrap(True)
        self.breadcrumb.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.breadcrumb.setTextFormat(Qt.RichText)
        self.breadcrumb.linkActivated.connect(self.navigate_link)
        layout.addWidget(self.breadcrumb)
        self.folderbar = QWidget()
        folderbar = QHBoxLayout(self.folderbar)
        layout.addWidget(self.folderbar)
        self.back = control("Back", lambda: self.history_move(-1), folderbar)
        self.forward = control("Forward", lambda: self.history_move(1), folderbar)
        self.folder_sources = QComboBox()
        folderbar.addWidget(self.folder_sources)
        control(
            "Source root",
            lambda: self.navigate_folder(self.folder_sources.currentData(), "."),
            folderbar,
        )
        self.folders = QListWidget()
        self.folders.setMaximumHeight(95)
        self.folders.itemDoubleClicked.connect(
            lambda item: self.navigate_folder(*item.data(Qt.UserRole))
        )
        layout.addWidget(self.folders)
        self.folders.hide()
        self.folderbar.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "Type",
                "Sample",
                "Experiment",
                "Category",
                "Modified",
                "Status",
                "Source",
                "Size",
                "Tags",
                "Origin",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 240)
        self.table.setMinimumHeight(180)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            lambda point: self.context(self.table.viewport().mapToGlobal(point))
        )
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.itemDoubleClicked.connect(lambda item: self.action("open"))
        self.stack.addWidget(self.table)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setIconSize(QSize(180, 180))
        self.grid.setGridSize(QSize(210, 235))
        self.grid.setWordWrap(True)
        self.grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(
            lambda point: self.context(self.grid.viewport().mapToGlobal(point))
        )
        self.grid.itemSelectionChanged.connect(self.selection_changed)
        self.grid.itemDoubleClicked.connect(lambda item: self.action("preview"))
        self.grid.verticalScrollBar().valueChanged.connect(self.lazy_thumbnails)
        self.stack.addWidget(self.grid)
        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        control("Previous", lambda: self.page(-1), bottom)
        control("Next", lambda: self.page(1), bottom)
        self.thumb_size = QComboBox()
        self.thumb_size.addItems(
            ["Small thumbnails", "Medium thumbnails", "Large thumbnails"]
        )
        self.thumb_size.setCurrentIndex(1)
        bottom.addWidget(self.thumb_size)
        self.thumb_size.currentIndexChanged.connect(self.resize_thumbs)
        for title, key in [
            ("Open", "open"),
            ("Show", "show"),
            ("Edit metadata", "edit"),
            ("Favorite", "favorite"),
            ("Compare", "compare"),
        ]:
            control(title, lambda checked=False, k=key: self.action(k), bottom)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.reset_reload)
        for field in (self.search, self.date_from, self.date_to):
            field.textChanged.connect(lambda: self.timer.start())
        for combo in (
            self.origin,
            self.sample,
            self.experiment,
            self.category,
            self.scope,
            self.sort,
        ):
            combo.currentIndexChanged.connect(self.reset_reload)
        self.view.currentIndexChanged.connect(self.change_view)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumContentsLength(7)
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumWidth(60)
            combo.setMaximumWidth(145)
        for field in (self.search, self.date_from, self.date_to):
            field.setMinimumWidth(50)
        self.setStyleSheet(
            "FileBrowser QPushButton {padding:5px 7px;font-size:12px;} FileBrowser QComboBox, FileBrowser QLineEdit {padding:5px;font-size:12px;}"
        )
        self.refresh_objects()

    def refresh_objects(self):
        for combo, kind in ((self.sample, "sample"), (self.experiment, "experiment")):
            old = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("All " + kind + "s", "")
            for obj in self.repository.objects(kind, origin=""):
                combo.addItem(
                    obj["id"] + " | " + obj["name"] + " | " + obj["origin"], obj["id"]
                )
            combo.setCurrentIndex(max(0, combo.findData(old)))
            combo.blockSignals(False)
        self.folder_sources.clear()
        for source in self.catalog.locations.sources():
            self.folder_sources.addItem(
                source.get("source_label", source["name"]), source["id"]
            )

    def configure(self, **filters):
        self.base = filters
        self.offset = 0
        self.family = ""
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        for combo in (self.sample, self.experiment, self.category, self.scope):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.origin.blockSignals(True)
        self.origin.setCurrentIndex(
            max(0, self.origin.findData(filters.get("origin", "current")))
        )
        self.origin.blockSignals(False)
        self.quick_filter("All", reload=False)
        self.reload()

    def filters(self):
        result = dict(self.base)
        if self.scope.currentText() == "All indexed":
            result = {"origin": ""}
        elif self.scope.currentText() == "Legacy":
            result = {"origin": "legacy"}
        elif self.scope.currentText() == "Current project":
            result = {"origin": "current"}
        elif self.scope.currentText() in ("Current sample", "Current experiment"):
            obj = self.workspace.object or {}
            key = (
                "sample"
                if self.scope.currentText() == "Current sample"
                else "experiment"
            )
            identity = (
                obj.get("id", "")
                if obj.get("kind") == key
                else obj.get("sample_id", "") if key == "sample" else ""
            )
            result = {
                "origin": obj.get("origin", "current"),
                key: identity,
                "empty_context": not bool(identity),
            }
        else:
            result["origin"] = self.origin.currentData()
        for key, field in (
            ("sample", self.sample),
            ("experiment", self.experiment),
            ("category", self.category),
        ):
            if field.currentData():
                result[key] = field.currentData()
        if result.get("sample") or result.get("experiment"):
            result["explicit"] = True
        result.update(
            date_from=self.date_from.text().strip(),
            date_to=self.date_to.text().strip(),
            sort=self.sort.currentText(),
        )
        if self.family in FAMILIES:
            result["family"] = self.family
        if self.family == "Favorites":
            result["favorite"] = True
        if self.family == "Recent":
            result["recent"] = True
        if self.family in ("Current", "Legacy"):
            result["origin"] = self.family.lower()
        return result

    def quick_filter(self, title, reload=True):
        self.family = title if title != "All" else ""
        for name, button in self.quick.items():
            button.setChecked(name == title)
        if reload:
            self.reset_reload()

    def reset_reload(self):
        self.offset = 0
        self.reload()

    def reload(self):
        self.request += 1
        request = self.request
        query = self.search.text()
        filters = self.filters()
        offset = self.offset
        self.status.setText("Loading indexed files...")
        self.table.setEnabled(False)
        self.grid.setEnabled(False)
        self.tasks.start(
            lambda: self.catalog.query(query, offset=offset, limit=200, **filters),
            lambda result: self.loaded(request, result),
            lambda msg: self.failed(request, msg),
        )
        self.folderbar.setVisible("exact_folder" in filters)
        if "exact_folder" in filters:
            self.load_folders(filters)
        else:
            self.folders.hide()
            self.breadcrumb.setText("Logical research view")

    def failed(self, request, msg):
        if request == self.request:
            self.status.setText(msg)
            self.table.setEnabled(True)
            self.grid.setEnabled(True)

    def loaded(self, request, result):
        if request != self.request:
            return
        selected_ids = {r["id"] for r in self.selected_rows()}
        self.rows, self.total = result
        self.table.blockSignals(True)
        self.grid.blockSignals(True)
        self.table.setEnabled(True)
        self.grid.setEnabled(True)
        self.table.setRowCount(len(self.rows))
        self.grid.clear()
        for i, row in enumerate(self.rows):
            family = self.filters().get("family")
            fields = (
                "name",
                "extension",
                "sample_id",
                "experiment_id",
                "category",
                "modified",
                "availability",
                "source_name",
                "size",
                "tags",
                "data_origin",
            )
            headers = [
                "Name",
                "Type",
                "Sample",
                "Experiment",
                "Category",
                "Modified",
                "Status",
                "Source",
                "Size",
                "Tags",
                "Origin",
            ]
            if family == "Reports":
                fields = (
                    "name",
                    "title",
                    "sample_id",
                    "experiment_id",
                    "category",
                    "modified",
                    "report_status",
                    "source_name",
                    "report_version",
                    "tags",
                    "data_origin",
                )
                headers = [
                    "Name",
                    "Title",
                    "Sample",
                    "Experiment",
                    "Category",
                    "Modified",
                    "Report status",
                    "Source",
                    "Version",
                    "Tags",
                    "Origin",
                ]
            elif family == "Data":
                fields = (
                    "name",
                    "extension",
                    "sample_id",
                    "experiment_id",
                    "category",
                    "modified",
                    "data_stage",
                    "source_name",
                    "size",
                    "tags",
                    "data_origin",
                )
                headers = [
                    "Name",
                    "Type",
                    "Sample",
                    "Experiment",
                    "Category",
                    "Modified",
                    "Raw / processed stage",
                    "Source",
                    "Size",
                    "Tags",
                    "Origin",
                ]
            self.table.setHorizontalHeaderLabels(headers)
            values = [row.get(k, "") for k in fields]
            for j, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row["id"])
                item.setToolTip(row["relative_path"])
                if j == 6:
                    status = str(value).casefold()
                    if any(
                        word in status for word in ("unavailable", "deleted", "failed")
                    ):
                        item.setForeground(QColor("#d92d20"))
                    elif "online" in status or "draft" in status:
                        item.setForeground(QColor("#a16207"))
                    elif "local" in status or "approved" in status:
                        item.setForeground(QColor("#137a40"))
                if j == 10:
                    item.setForeground(
                        QColor(
                            "#a16207" if row["data_origin"] == "legacy" else "#0f766e"
                        )
                    )
                self.table.setItem(i, j, item)
            tile = QListWidgetItem(
                row["name"]
                + "\n"
                + row["data_origin"]
                + " | "
                + row.get("sample_id", "")
            )
            tile.setData(Qt.UserRole, row["id"])
            tile.setToolTip(row["relative_path"] + " | " + row.get("availability", ""))
            tile.setIcon(icon("files"))
            self.grid.addItem(tile)
            if row["id"] in selected_ids:
                tile.setSelected(True)
                for j in range(self.table.columnCount()):
                    self.table.item(i, j).setSelected(True)
        self.table.blockSignals(False)
        self.grid.blockSignals(False)
        self.status.setText(
            f"{self.total:,} matches | {self.offset+1 if self.rows else 0}–{self.offset+len(self.rows)} | Database-wide sort: {self.sort.currentText()}"
            if self.rows
            else "No matching files. Adjust filters or index this source under Settings > Storage."
        )
        if hasattr(self, "restore_state"):
            state = self.restore_state
            del self.restore_state
            self.table.clearSelection()
            self.grid.clearSelection()
            for i, row in enumerate(self.rows):
                if row["id"] in state.get("selection", []):
                    self.grid.item(i).setSelected(True)
                    for j in range(self.table.columnCount()):
                        self.table.item(i, j).setSelected(True)
            self.table.verticalScrollBar().setValue(state.get("scroll", 0))
        if self.selected_rows():
            self.selection_changed()
        self.lazy_thumbnails()
        QTimer.singleShot(0, self.lazy_thumbnails)

    def page(self, delta):
        offset = self.offset + delta * 200
        if 0 <= offset < self.total:
            self.offset = offset
            self.reload()

    def selected_rows(self):
        ids = (
            {item.data(Qt.UserRole) for item in self.grid.selectedItems()}
            if self.stack.currentWidget() == self.grid
            else {
                self.table.item(index.row(), 0).data(Qt.UserRole)
                for index in self.table.selectionModel().selectedRows()
                if self.table.item(index.row(), 0)
            }
        )
        return [row for row in self.rows if row["id"] in ids]

    def selection_changed(self):
        rows = self.selected_rows()
        if rows:
            self.selected.emit(rows[0])

    def change_view(self):
        QTimer.singleShot(0, self.lazy_thumbnails)
        self.stack.setCurrentWidget(
            self.grid if self.view.currentText() == "Grid" else self.table
        )
        self.table.verticalHeader().setDefaultSectionSize(
            24 if self.view.currentText() == "Compact" else 36
        )
        self.lazy_thumbnails()

    def resize_thumbs(self):
        size = (110, 180, 260)[self.thumb_size.currentIndex()]
        self.grid.setIconSize(QSize(size, size))
        self.grid.setGridSize(QSize(size + 30, size + 55))
        self.lazy_thumbnails()

    def lazy_thumbnails(self, *args):
        if getattr(self.workspace.window, "closing", False):
            return
        if self.stack.currentWidget() != self.grid:
            return
        request = self.request
        size = self.grid.iconSize().width()
        candidates = []
        for i, row in enumerate(self.rows):
            item = self.grid.item(i)
            key = (row["id"], size, str(row.get("signature")))
            if not item or not self.grid.visualItemRect(item).intersects(
                self.grid.viewport().rect()
            ):
                continue
            if row.get("extension") not in FAMILIES["Images"]:
                continue
            if key in self.loaded_thumbs:
                if self.loaded_thumbs[key]:
                    item.setIcon(QIcon(self.loaded_thumbs[key]))
                continue
            if key in self.thumb_pending:
                continue
            self.thumb_pending.add(key)
            candidates.append((key, row))
            if len(candidates) >= 24:
                break
        if not candidates:
            return

        def generate():
            result = []
            for key, row in candidates:
                try:
                    result.append((key, previews.thumbnail(self.catalog, row, size)))
                except Exception:
                    result.append((key, None))
            return result

        self.tasks.start(
            generate,
            lambda result: self.thumbnails_ready(request, result),
            lambda msg: None,
        )

    def thumbnails_ready(self, request, result):
        for key, path in result:
            self.loaded_thumbs[key] = path or ""
            self.thumb_pending.discard(key)
        if request != self.request:
            return
        for i, row in enumerate(self.rows):
            key = (row["id"], self.grid.iconSize().width(), str(row.get("signature")))
            if self.loaded_thumbs.get(key):
                self.grid.item(i).setIcon(QIcon(self.loaded_thumbs[key]))

    def context(self, point):
        menu = QMenu(self)
        for title, key in [
            ("Open File", "open"),
            ("Preview", "preview"),
            ("Show in Explorer", "show"),
            ("Open containing folder", "folder"),
            ("Copy Path", "copy"),
            ("Copy file ID", "copy_id"),
            ("Assign sample / experiment, tags, category", "edit"),
            ("Toggle favorite", "favorite"),
            ("Association suggestions", "suggest"),
            ("Related files / versions", "related"),
            ("Locate missing file", "locate"),
            ("Hide record from workspace", "hide"),
            ("Keep record", "keep"),
        ]:
            menu.addAction(title, lambda k=key: self.action(k))
        menu.exec(point)

    def action(self, key):
        rows = self.selected_rows()
        if rows:
            self.workspace.file_action(key, rows[0], rows, self)

    def navigate_link(self, target):
        if target.isdigit():
            parts = self.base.get("exact_folder", ".").split("/")
            self.navigate_folder(
                self.base.get("source_id"), "/".join(parts[: int(target)]) or "."
            )

    def capture_state(self):
        return {
            "base": dict(self.base),
            "offset": self.offset,
            "search": self.search.text(),
            "sort": self.sort.currentText(),
            "family": self.family,
            "scope": self.scope.currentIndex(),
            "origin": self.origin.currentIndex(),
            "sample": self.sample.currentIndex(),
            "experiment": self.experiment.currentIndex(),
            "category": self.category.currentIndex(),
            "date_from": self.date_from.text(),
            "date_to": self.date_to.text(),
            "selection": [r["id"] for r in self.selected_rows()],
            "scroll": self.table.verticalScrollBar().value(),
        }

    def navigate_folder(self, source_id, path, record=True):
        if not source_id:
            return
        if record:
            if self.history_position < 0 and "exact_folder" in self.base:
                self.folder_history = [self.capture_state()]
                self.history_position = 0
            if self.history_position >= 0:
                self.folder_history[self.history_position] = self.capture_state()
            self.folder_history = self.folder_history[: self.history_position + 1]
            self.folder_history.append(
                {
                    "base": {
                        "source_id": source_id,
                        "exact_folder": path,
                        "origin": "",
                    },
                    "offset": 0,
                }
            )
            self.history_position = len(self.folder_history) - 1
        self.configure(source_id=source_id, exact_folder=path, origin="")
        self.back.setEnabled(self.history_position > 0)
        self.forward.setEnabled(self.history_position < len(self.folder_history) - 1)

    def history_move(self, delta):
        position = self.history_position + delta
        if 0 <= position < len(self.folder_history):
            self.folder_history[self.history_position] = self.capture_state()
            self.history_position = position
            state = self.folder_history[position]
            self.configure(**state["base"])
            self.offset = state.get("offset", 0)
            for name in ("scope", "origin", "sample", "experiment", "category"):
                if name in state:
                    combo = getattr(self, name)
                    combo.blockSignals(True)
                    combo.setCurrentIndex(state[name])
                    combo.blockSignals(False)
            for name in ("search", "date_from", "date_to"):
                if name in state:
                    getattr(self, name).setText(state[name])
            if "sort" in state:
                self.sort.setCurrentText(state["sort"])
            self.family = state.get("family", "")
            for name, button in self.quick.items():
                button.setChecked(name == (self.family or "All"))
            self.restore_state = state
            self.reload()
            self.back.setEnabled(position > 0)
            self.forward.setEnabled(position < len(self.folder_history) - 1)

    def load_folders(self, filters):
        source = filters.get("source_id") or self.folder_sources.currentData()
        path = filters.get("exact_folder", ".")
        self.folders.show()
        self.folders.clear()
        self.breadcrumb.setText(
            '<a href="0">Root</a> / '
            + " / ".join(
                '<a href="'
                + str(i + 1)
                + '">'
                + part.replace("&", "&amp;").replace("<", "&lt;")
                + "</a>"
                for i, part in enumerate(path.split("/"))
                if part != "."
            )
        )
        with self.catalog.connect() as db:
            children = db.execute(
                "SELECT path FROM directories WHERE source=? AND parent=? AND path<>? ORDER BY path COLLATE NOCASE LIMIT 500",
                (source, path, path),
            ).fetchall()
        for (child,) in children:
            item = QListWidgetItem("Folder: " + Path(child).name)
            item.setData(Qt.UserRole, (source, child))
            self.folders.addItem(item)
        if not children:
            self.folders.hide()


class MetadataEditor(QDialog):
    def __init__(self, repository, rows, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.rows = rows
        self.setWindowTitle(
            "Edit file metadata"
            if len(rows) == 1
            else "Bulk edit " + str(len(rows)) + " files"
        )
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.fields = {}
        self.apply = {}
        layout.addWidget(
            QLabel("Check the fields to apply. Changes stay in the Hub database.")
        )
        for key in (
            "sample_id",
            "experiment_id",
            "category",
            "tags",
            "title",
            "notes",
            "description",
            "report_version",
            "report_status",
            "data_stage",
        ):
            checkbox = QCheckBox(key.replace("_", " ").title())
            self.apply[key] = checkbox
            if key in ("sample_id", "experiment_id", "category"):
                field = QComboBox()
                field.addItem("Unassigned", "")
                if key == "category":
                    for category in RESEARCH_CATEGORIES:
                        field.addItem(category, category)
                else:
                    kind = "sample" if key == "sample_id" else "experiment"
                    for obj in repository.objects(kind, origin=rows[0]["data_origin"]):
                        field.addItem(obj["id"] + " | " + obj["name"], obj["id"])
                field.setCurrentIndex(max(0, field.findData(rows[0].get(key, ""))))
            else:
                field = QLineEdit(str(rows[0].get(key, "")) if len(rows) == 1 else "")
            form.addRow(checkbox, field)
            self.fields[key] = field
        self.add_tags = QCheckBox("Append tags instead of replacing")
        layout.addWidget(self.add_tags)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        values = {
            k: (f.currentData() if isinstance(f, QComboBox) else f.text())
            for k, f in self.fields.items()
            if self.apply[k].isChecked()
        }
        try:
            self.repository.annotate(
                self.rows, values, append_tags=self.add_tags.isChecked()
            )
            self.accept()
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))


class ResearchHub(QWidget):
    def __init__(self, settings, window):
        super().__init__(window)
        self.settings = settings
        self.window = window
        self.catalog = settings.catalog
        self.repository = ResearchWorkspace(self.catalog) if self.catalog else None
        self.current_page = "Overview"
        self.object = None
        self.dialogs = []
        self.browsers = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        layout.addLayout(header)
        self.title = QLabel("Research workspace")
        self.title.setStyleSheet("font-size:20px;font-weight:600")
        header.addWidget(self.title, 1)
        control(
            "Navigation",
            lambda: (
                self.nav.setVisible(not self.nav.isVisible()) if self.catalog else None
            ),
            header,
        )
        control(
            "Details",
            lambda: (
                self.preview.setVisible(not self.preview.isVisible())
                if self.catalog
                else None
            ),
            header,
        )
        control("Restore hidden records", self.restore_hidden, header)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        if not self.catalog:
            layout.addWidget(
                QLabel(
                    "Configure current research and legacy source folders to use samples, experiments and the file workspace."
                )
            )
            control("Configure storage", lambda: window.open_settings(1), layout)
            layout.addStretch()
            return
        self.splitter = QSplitter()
        layout.addWidget(self.splitter, 1)
        self.nav = QListWidget()
        self.nav.setMinimumWidth(125)
        for name, color in COLORS.items():
            item = QListWidgetItem(name)
            item.setForeground(QColor(color))
            self.nav.addItem(item)
        self.splitter.addWidget(self.nav)
        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)
        self.browser = FileBrowser(self)
        self.browsers.append(self.browser)
        self.stack.addWidget(self.browser)
        self.browser.selected.connect(self.select_file)
        self.objects_page = QWidget()
        objects_layout = QVBoxLayout(self.objects_page)
        objectbar = QHBoxLayout()
        objects_layout.addLayout(objectbar)
        control("New sample", lambda: self.edit_object("sample"), objectbar)
        control("New experiment", lambda: self.edit_object("experiment"), objectbar)
        self.only_favorites = QCheckBox("Favorites only")
        self.only_favorites.toggled.connect(self.show_objects)
        objectbar.addWidget(self.only_favorites)
        self.object_origin = QComboBox()
        self.object_origin.addItems(["Current", "Legacy", "All origins"])
        self.object_origin.currentTextChanged.connect(self.show_objects)
        objectbar.addWidget(self.object_origin)
        self.object_search = QLineEdit()
        self.object_search.setPlaceholderText("Search samples or experiments")
        self.object_search.textChanged.connect(self.show_objects)
        objectbar.addWidget(self.object_search, 1)
        self.object_list = QListWidget()
        self.object_list.itemDoubleClicked.connect(
            lambda item: self.show_object(item.data(Qt.UserRole))
        )
        objects_layout.addWidget(self.object_list, 1)
        self.stack.addWidget(self.objects_page)
        self.detail = QWidget()
        detail_layout = QVBoxLayout(self.detail)
        detailbar = QHBoxLayout()
        detail_layout.addLayout(detailbar)
        self.object_title = QLabel()
        self.object_title.setTextFormat(Qt.PlainText)
        self.object_title.setWordWrap(True)
        self.object_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        detailbar.addWidget(self.object_title, 1)
        control(
            "Edit object",
            lambda: self.edit_object(self.object["kind"], self.object),
            detailbar,
        )
        control("Related files", lambda: self.related_object_files(), detailbar)
        self.object_tabs = QTabWidget()
        detail_layout.addWidget(self.object_tabs, 1)
        self.stack.addWidget(self.detail)
        self.object_browsers = {}
        self.object_tabs.currentChanged.connect(self.object_tab_changed)
        self.favorites_objects = QListWidget()
        self.favorites_objects.setMaximumHeight(150)
        self.favorites_objects.itemDoubleClicked.connect(
            lambda item: self.show_object(item.data(Qt.UserRole))
        )
        self.browser.layout().insertWidget(0, self.favorites_objects)
        self.favorites_objects.hide()
        self.timeline_view = QListWidget()
        self.timeline_view.itemDoubleClicked.connect(self.timeline_open)
        self.stack.addWidget(self.timeline_view)
        timeline_page = QWidget()
        timeline_layout = QVBoxLayout(timeline_page)
        self.stack.removeWidget(self.timeline_view)
        timeline_layout.addWidget(self.timeline_view, 1)
        control("Record research event", self.record_event, timeline_layout)
        self.stack.addWidget(timeline_page)
        self.timeline_page = timeline_page
        self.overview = QTextEdit()
        self.overview.setReadOnly(True)
        self.overview_page = QWidget()
        overview_layout = QVBoxLayout(self.overview_page)
        stats = QHBoxLayout()
        overview_layout.addLayout(stats)
        self.stats = []
        for color, bg in (
            ("#0f766e", "#e6f4ef"),
            ("#7c3aed", "#f1eafa"),
            ("#0071e3", "#eaf4ff"),
            ("#a16207", "#fff6e2"),
        ):
            stat = QLabel()
            stat.setMinimumHeight(95)
            stat.setAlignment(Qt.AlignCenter)
            stat.setStyleSheet(
                "background:"
                + bg
                + ";color:"
                + color
                + ";border-radius:10px;font-size:17px;font-weight:600;"
            )
            stats.addWidget(stat)
            self.stats.append(stat)
        overview_layout.addWidget(self.overview, 1)
        self.stack.addWidget(self.overview_page)
        self.preview = PreviewPanel(
            self.catalog, lambda key, row: self.file_action(key, row)
        )
        self.preview.setMinimumWidth(260)
        self.splitter.addWidget(self.preview)
        self.splitter.setSizes(
            window.store.local.get("research_workspace_sizes", [170, 780, 330])
        )
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(1, False)
        self.nav.currentTextChanged.connect(self.navigate)
        self.nav.setCurrentRow(0)
        self.nav.setVisible(window.store.local.get("research_navigation_visible", True))
        self.preview.setVisible(
            window.store.local.get("research_details_visible", True)
        )

    def restore_hidden(self):
        if self.repository:
            self.repository.restore_hidden()
            self.browser.reload()
            self.message.setText("Hidden records restored to workspace lists.")

    def busy(self):
        preview_busy = self.catalog and any(
            tasks.busy() for tasks in self.preview.findChildren(Tasks)
        )
        return (
            any(browser.tasks.busy() for browser in self.browsers)
            or preview_busy
            or any(getattr(d, "tasks", None) and d.tasks.busy() for d in self.dialogs)
        )

    def save_layout(self):
        if self.catalog:
            self.window.store.local["research_workspace_sizes"] = self.splitter.sizes()
            self.window.store.local["research_navigation_visible"] = (
                self.nav.isVisible()
            )
            self.window.store.local["research_details_visible"] = (
                self.preview.isVisible()
            )
            self.window.store.save_local()

    def reload(self):
        if self.catalog:
            self.browser.refresh_objects()
            self.navigate(self.current_page)

    def navigate(self, page):
        if not hasattr(self, "view_modes"):
            self.view_modes = {}
        self.view_modes[self.current_page] = self.browser.view.currentText()
        for index in range(self.nav.count()):
            if self.nav.item(index).text() == page:
                self.nav.blockSignals(True)
                self.nav.setCurrentRow(index)
                self.nav.blockSignals(False)
                break
        if page == "Settings":
            self.window.open_settings(1)
            return
        if page == "Software":
            self.window.show_page("Software")
            return
        if page in ("Resources", "Analysis tools"):
            self.window.project_tabs.setCurrentIndex(0 if page == "Resources" else 2)
            return
        self.current_page = page
        self.title.setText(page)
        self.message.clear()
        self.favorites_objects.setVisible(page == "Favorites")
        if page == "Favorites":
            self.favorites_objects.clear()
            for kind in ("sample", "experiment"):
                for obj in self.repository.objects(kind, origin="", favorite=True):
                    item = QListWidgetItem(
                        kind.title()
                        + ": "
                        + obj["id"]
                        + " | "
                        + obj["name"]
                        + " | "
                        + obj["origin"]
                    )
                    item.setData(Qt.UserRole, obj["id"])
                    self.favorites_objects.addItem(item)
        if page in ("Samples", "Experiments"):
            self.show_objects()
            self.stack.setCurrentWidget(self.objects_page)
        elif page == "Timeline":
            self.show_timeline()
            self.stack.setCurrentWidget(self.timeline_page)
        elif page == "Overview":
            summary = self.catalog.summary()
            samples = self.repository.objects("sample")
            experiments = self.repository.objects("experiment")
            self.overview.setPlainText(
                "GDL Research Hub\n\n"
                + self.catalog.locations.value["active"]["name"]
                + "\n\n"
                + f"{len(samples)} samples | {len(experiments)} experiments | {summary['current']:,} current files\n{summary['legacy']:,} legacy references | {summary['online_only']:,} online-only files\n\n"
                + "Create samples and experiments to organize related files without moving them.\nUse Images for microscopy galleries, Data for bounded tables, Reports for documents, and Timeline for research activity.\n\nCurrent research is the default. Legacy references remain visibly separate.\n\nLast index: "
                + summary.get("last_indexed", "Not yet indexed")
            )
            for stat, text in zip(
                self.stats,
                [
                    str(len(samples)) + "\nSamples",
                    str(len(experiments)) + "\nExperiments",
                    f"{summary['current']:,}\nCurrent files",
                    f"{summary['legacy']:,}\nLegacy references",
                ],
            ):
                stat.setText(text)
            self.stack.setCurrentWidget(self.overview_page)
        else:
            filters = {"origin": "legacy" if page == "Legacy" else "current"}
            if page in FAMILIES:
                filters["family"] = page
            if page == "Favorites":
                filters.update(favorite=True, origin="")
            if page == "Recent":
                filters.update(recent=True, origin="")
            if page == "Needs review":
                filters["needs_review"] = True
            if page == "Folders":
                filters.update(
                    exact_folder=".",
                    source_id=self.catalog.locations.value["active"]["id"],
                )
            self.browser.configure(**filters)
            self.browser.view.setCurrentText(
                self.view_modes.get(page, "Grid" if page == "Images" else "List")
            )
            if page == "Recent":
                self.browser.sort.setCurrentText("Recently viewed")
            self.stack.setCurrentWidget(self.browser)

    def show_objects(self, *args):
        if not self.repository:
            return
        kind = "experiment" if self.current_page == "Experiments" else "sample"
        origin = {"Current": "current", "Legacy": "legacy", "All origins": ""}[
            self.object_origin.currentText()
        ]
        self.object_list.clear()
        for obj in self.repository.objects(
            kind,
            origin,
            self.object_search.text(),
            favorite=self.only_favorites.isChecked(),
        ):
            filters = {"origin": obj["origin"], kind: obj["id"], "explicit": True}
            _, files = self.catalog.query(limit=1, **filters)
            _, images = self.catalog.query(limit=1, family="Images", **filters)
            _, reports = self.catalog.query(limit=1, family="Reports", **filters)
            label = (
                obj["id"]
                + " | "
                + obj["name"]
                + " | "
                + obj["origin"]
                + (" | Favorite" if obj["favorite"] else "")
                + "\n"
                + f"{files} files | {images} images | {reports} reports | "
                + obj.get("status", "")
                + "\nLast activity: "
                + obj.get("updated_at", "")
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, obj["id"])
            item.setForeground(
                QColor(
                    "#a16207"
                    if obj["origin"] == "legacy"
                    else "#7c3aed" if kind == "experiment" else "#0f766e"
                )
            )
            item.setSizeHint(QSize(300, 92))
            self.object_list.addItem(item)
        if not self.object_list.count():
            self.message.setText(
                "No "
                + kind
                + "s yet. Create one and explicitly associate its research files."
            )

    def edit_object(self, kind, obj=None):
        origin = (
            obj["origin"]
            if obj
            else "legacy" if self.object_origin.currentText() == "Legacy" else "current"
        )
        dialog = ObjectEditor(self.repository, kind, obj, origin, self)
        if dialog.exec() == QDialog.Accepted:
            for browser in self.browsers:
                browser.refresh_objects()
            self.show_object(dialog.saved["id"])

    def show_object(self, identity):
        obj = self.repository.get(identity)
        if not obj:
            return
        self.current_page = "Samples" if obj["kind"] == "sample" else "Experiments"
        self.title.setText(obj["id"] + " / " + obj["name"])
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(1 if obj["kind"] == "sample" else 2)
        self.nav.blockSignals(False)
        self.object = obj
        self.object_title.setText(
            obj["id"] + " | " + obj["name"] + " | " + obj["origin"]
        )
        self.object_tabs.blockSignals(True)
        while self.object_tabs.count():
            page = self.object_tabs.widget(0)
            self.object_tabs.removeTab(0)
            if isinstance(page, FileBrowser):
                page.setParent(self)
            else:
                page.deleteLater()
        self.stack.setCurrentWidget(self.detail)
        overview = QTextEdit()
        overview.setReadOnly(True)
        overview.setPlainText(
            "\n".join(
                k.replace("_", " ").title() + ": " + str(v)
                for k, v in obj.items()
                if k not in ("conditions", "results", "notes")
            )
        )
        _, file_count = self.catalog.query(
            limit=1, origin=obj["origin"], explicit=True, **{obj["kind"]: obj["id"]}
        )
        _, image_count = self.catalog.query(
            limit=1,
            origin=obj["origin"],
            family="Images",
            explicit=True,
            **{obj["kind"]: obj["id"]},
        )
        _, report_count = self.catalog.query(
            limit=1,
            origin=obj["origin"],
            family="Reports",
            explicit=True,
            **{obj["kind"]: obj["id"]},
        )
        overview.append(
            f"\nRelated items: {file_count} files | {image_count} images | {report_count} reports"
        )
        self.object_tabs.addTab(overview, "Overview")
        pages = (
            ("Images", "Experiments", "Data", "Reports", "Timeline", "Notes")
            if obj["kind"] == "sample"
            else ("Files", "Images", "Data", "Results", "Notes", "Timeline")
        )
        for name in pages:
            if name in ("Images", "Data", "Reports", "Files"):
                if name not in self.object_browsers:
                    browser = FileBrowser(self)
                    browser.selected.connect(self.select_file)
                    self.object_browsers[name] = browser
                    self.browsers.append(browser)
                self.object_tabs.addTab(self.object_browsers[name], name)
            elif name == "Experiments":
                listing = QListWidget()
                for exp in self.repository.objects("experiment", obj["origin"]):
                    if exp.get("sample_id") == obj["id"]:
                        item = QListWidgetItem(exp["id"] + " | " + exp["name"])
                        item.setData(Qt.UserRole, exp["id"])
                        listing.addItem(item)
                listing.itemDoubleClicked.connect(
                    lambda item: self.show_object(item.data(Qt.UserRole))
                )
                self.object_tabs.addTab(listing, name)
            elif name == "Timeline":
                listing = QListWidget()
                self.fill_timeline(
                    listing,
                    sample=obj["id"] if obj["kind"] == "sample" else "",
                    experiment=obj["id"] if obj["kind"] == "experiment" else "",
                    origin=obj["origin"],
                )
                listing.itemDoubleClicked.connect(self.timeline_open)
                self.object_tabs.addTab(listing, name)
            elif name == "Results":
                page = QTextEdit()
                page.setReadOnly(True)
                page.setPlainText(
                    obj.get("results_summary", "")
                    + "\n\nConditions\n"
                    + self.metrics_text(obj.get("conditions", []))
                    + "\n\nResults\n"
                    + self.metrics_text(obj.get("results", []))
                )
                self.object_tabs.addTab(page, name)
            else:
                page = QTextEdit()
                page.setReadOnly(True)
                page.setPlainText(
                    obj.get("notes", "")
                    or "No notes yet. Use Edit object to add notes."
                )
                self.object_tabs.addTab(page, name)
        self.object_tabs.blockSignals(False)
        self.object_tabs.setCurrentIndex(0)

    def object_tab_changed(self, index):
        page = self.object_tabs.widget(index)
        if isinstance(page, FileBrowser) and self.object:
            family = self.object_tabs.tabText(index)
            obj = self.object
            page.configure(
                origin=obj["origin"],
                **{obj["kind"]: obj["id"]},
                **({"family": family} if family in FAMILIES else {}),
            )
            page.view.setCurrentText("Grid" if family == "Images" else "List")

    def metrics_text(self, rows):
        return (
            "\n".join(
                r["name"] + ": " + r["value"] + " " + r["unit"] + " | " + r["notes"]
                for r in rows
            )
            or "No metrics recorded."
        )

    def related_object_files(self, family="Files"):
        if not self.object:
            return
        obj = self.object
        self.browser.configure(
            origin=obj["origin"],
            **{obj["kind"]: obj["id"]},
            **({"family": family} if family in FAMILIES else {}),
        )
        self.stack.setCurrentWidget(self.browser)
        self.title.setText(obj["id"] + " / " + family)
        self.message.setText(
            "Scoped to "
            + obj["name"]
            + ". Return to Samples / Experiments to view its other tabs."
        )

    def record_event(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Record research activity")
        layout = QVBoxLayout(dialog)
        kind = QComboBox()
        kind.addItems(
            [
                "Note added",
                "Experiment started",
                "Experiment completed",
                "Analysis performed",
                "Report revised",
                "Sample status changed",
            ]
        )
        layout.addWidget(kind)
        scope = QComboBox()
        scope.addItem("Current project", None)
        for object_kind in ("sample", "experiment"):
            for obj in self.repository.objects(object_kind, origin=""):
                scope.addItem(
                    obj["id"] + " | " + obj["name"] + " | " + obj["origin"], obj
                )
        layout.addWidget(scope)
        detail = QTextEdit()
        detail.setPlaceholderText(
            "Describe the observation or activity. Recorded now; do not infer an experiment date from file timestamps."
        )
        layout.addWidget(detail)
        error = QLabel()
        error.setWordWrap(True)
        layout.addWidget(error)

        def save():
            obj = scope.currentData()
            try:
                self.repository.record_event(
                    kind.currentText(),
                    detail.toPlainText(),
                    **({obj["kind"]: obj["id"]} if obj else {}),
                )
                dialog.accept()
                self.show_timeline()
            except ValueError as exc:
                error.setText(str(exc))

        control("Save event", save, layout)
        dialog.exec()

    def fill_timeline(self, listing, **filters):
        listing.clear()
        for event in self.repository.timeline(**filters):
            item = QListWidgetItem(
                event["at"]
                + " | "
                + event["kind"]
                + " | "
                + event["origin"]
                + "\n"
                + event["detail"]
            )
            item.setData(Qt.UserRole, event)
            item.setForeground(
                QColor(
                    "#a16207"
                    if event["origin"] == "legacy"
                    else "#7c3aed" if event["experiment_id"] else "#0f766e"
                )
            )
            listing.addItem(item)
        if not listing.count():
            listing.addItem(
                "No recorded research activity yet. Filesystem timestamps do not imply experiment dates."
            )

    def show_timeline(self):
        self.fill_timeline(self.timeline_view, origin="")

    def timeline_open(self, item):
        event = item.data(Qt.UserRole)
        if not event:
            return
        if event["file_id"]:
            with self.catalog.connect() as db:
                row = db.execute(
                    "SELECT payload FROM files WHERE id=?", (event["file_id"],)
                ).fetchone()
            if row:
                self.select_file(json.loads(row[0]))
        elif event["experiment_id"] or event["sample_id"]:
            self.show_object(event["experiment_id"] or event["sample_id"])

    def select_file(self, row):
        self.preview.select(row)
        self.repository.viewed(row)

    def global_search(self, text):
        if not self.catalog:
            return
        self.navigate("Files")
        self.browser.scope.setCurrentText("All indexed")
        self.browser.search.setText(text)

    def file_action(self, key, row, rows=None, browser=None):
        if not row:
            return
        rows = rows or [row]
        browser = browser or self.browser
        try:
            path = self.catalog.safe_path(row)
            if key == "open":
                file_launcher.open_file(
                    path, self.window.store.local.get("code_editor")
                )
                self.repository.viewed(row)
            elif key == "folder":
                file_launcher.open_folder(path.parent)
            elif key == "show":
                file_launcher.show_in_folder(path)
            elif key == "copy_id":
                QApplication.clipboard().setText(row["id"])
                self.message.setText("File identity copied.")
            elif key == "copy":
                QApplication.clipboard().setText(str(path))
                self.message.setText("Full file path copied.")
            elif key == "preview":
                if row.get("extension") in FAMILIES["Images"]:
                    images = [
                        r
                        for r in browser.rows
                        if r.get("extension") in FAMILIES["Images"]
                    ]
                    images = images if row in images else [row]
                    dialog = ImageViewer(
                        self.catalog,
                        images,
                        images.index(row),
                        lambda k, r: self.file_action(k, r),
                        self,
                    )
                    dialog.show()
                    self.dialogs.append(dialog)
                    dialog.destroyed.connect(
                        lambda _object=None, d=dialog: (
                            self.dialogs.remove(d) if d in self.dialogs else None
                        )
                    )
                else:
                    self.preview.show()
                    self.select_file(row)
            elif key == "compare":
                images = [r for r in rows if r.get("extension") in FAMILIES["Images"]]
                if len(images) != 2:
                    raise ValueError("Select exactly two images to compare.")
                dialog = ImageComparison(self.catalog, images, self)
                dialog.show()
                self.dialogs.append(dialog)
                dialog.destroyed.connect(
                    lambda _object=None, d=dialog: (
                        self.dialogs.remove(d) if d in self.dialogs else None
                    )
                )
            elif key == "edit":
                if (
                    MetadataEditor(self.repository, rows, self).exec()
                    == QDialog.Accepted
                ):
                    browser.reload()
            elif key == "favorite":
                self.repository.annotate(
                    rows, {"favorite": not row.get("favorite", False)}
                )
                browser.reload()
            elif key == "suggest":
                self.suggestions(row, browser)
            elif key == "related":
                self.related_dialog(row)
            elif key == "locate":
                filename, _ = QFileDialog.getOpenFileName(
                    self, "Locate file within its original source", str(path.parent)
                )
                if filename:
                    self.repository.locate(row, filename)
                    browser.reload()
            elif key == "hide":
                if (
                    QMessageBox.question(
                        self,
                        "Hide indexed record",
                        "Hide this record from workspace lists? Its file and index metadata remain preserved.",
                    )
                    == QMessageBox.Yes
                ):
                    self.repository.hide(row)
                    browser.reload()
            elif key == "keep":
                self.message.setText("Record retained. No source file was changed.")
        except (ValueError, OSError) as exc:
            self.message.setText(
                str(exc)
                if isinstance(exc, ValueError)
                else "File action unavailable. Check the file location and its Windows application association."
            )

    def suggestions(self, row, browser):
        candidates = self.repository.suggestions(row)
        dialog = QDialog(self)
        dialog.setWindowTitle("Review association suggestions")
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Suggestions based on matching IDs or names in the file path. Choose explicitly."
            )
        )
        combo = QComboBox()
        combo.addItem("Choose a suggestion", None)
        for obj in candidates:
            combo.addItem(obj["kind"] + " | " + obj["id"] + " | " + obj["name"], obj)
        layout.addWidget(combo)
        error = QLabel()
        layout.addWidget(error)

        def accept():
            obj = combo.currentData()
            if not obj:
                return
            try:
                self.repository.annotate([row], {obj["kind"] + "_id": obj["id"]})
                dialog.accept()
                browser.reload()
            except ValueError as exc:
                error.setText(str(exc))

        control("Accept selected suggestion", accept, layout)
        control(
            "Change manually",
            lambda: (dialog.reject(), self.file_action("edit", row, browser=browser)),
            layout,
        )
        dialog.exec()

    def related_dialog(self, row):
        dialog = QDialog(self)
        dialog.setWindowTitle("Relationships and metadata history")
        dialog.resize(700, 600)
        layout = QVBoxLayout(dialog)
        view = QTextEdit()
        view.setReadOnly(True)
        relationships = self.catalog.related(row["id"])
        lines = ["File: " + row["name"], "Identity: " + row["id"], "", "Relationships"]
        for relation in relationships:
            other = (
                relation["to_id"]
                if relation["from_id"] == row["id"]
                else relation["from_id"]
            )
            with self.catalog.connect() as db:
                found = db.execute(
                    "SELECT payload FROM files WHERE id=?", (other,)
                ).fetchone()
            other_row = json.loads(found[0]) if found else {}
            lines.append(
                relation["type"]
                + ": "
                + other_row.get("name", other)
                + " | "
                + other_row.get("data_origin", "")
                + " | "
                + other
            )
        lines.extend(["", "Metadata revision comparison (source files are not copied)"])
        current = row
        for revision in self.repository.revisions(row):
            previous = revision["metadata"]
            changes = []
            for key in (
                "sample_id",
                "experiment_id",
                "category",
                "tags",
                "title",
                "notes",
                "description",
                "favorite",
                "report_version",
                "report_status",
                "data_stage",
            ):
                if previous.get(key) != current.get(key):
                    changes.append(
                        key.replace("_", " ")
                        + ": "
                        + str(previous.get(key, ""))
                        + " -> "
                        + str(current.get(key, ""))
                    )
            lines.append(
                revision["at"]
                + "\n"
                + (
                    "\n".join(changes)
                    if changes
                    else "No editable metadata difference."
                )
            )
            current = previous
        view.setPlainText("\n".join(lines))
        layout.addWidget(view)
        target = QLineEdit()
        target.setPlaceholderText("Related indexed file ID")
        layout.addWidget(target)
        kind = QComboBox()
        kind.addItems(
            [
                "related_to",
                "derived_from",
                "supersedes",
                "previous_version",
                "references",
            ]
        )
        layout.addWidget(kind)

        def relate():
            try:
                self.catalog.relate(
                    row["id"], target.text().strip(), kind.currentText()
                )
                dialog.accept()
            except ValueError as exc:
                self.message.setText(str(exc))

        control("Add relationship", relate, layout)
        dialog.exec()
