"""Resident-only research viewers and lifetime-managed background work."""

from PySide6.QtCore import Qt, QThread, Signal, QObject, QPointF
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QDialog,
    QGraphicsView,
    QGraphicsScene,
    QSplitter,
    QSpinBox,
    QSizePolicy,
)
from app.services import previews


class Task(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action

    def run(self):
        try:
            self.ready.emit(self.action())
        except Exception as exc:
            self.failed.emit(
                str(exc)
                if isinstance(exc, ValueError)
                else "Preview unavailable. Open File or check the source folder."
            )


class Tasks(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.active = []

    def start(self, action, done, failed):
        task = Task(action, self)
        self.active.append(task)
        task.ready.connect(done)
        task.failed.connect(failed)
        task.finished.connect(lambda: self.finish(task))
        task.start()

    def finish(self, task):
        if task in self.active:
            self.active.remove(task)
        task.deleteLater()

    def busy(self):
        return bool(self.active)


class ViewerDialog(QDialog):
    """Do not dispose child threads through Close or Escape while work is pending."""

    def pending(self):
        return any(tasks.busy() for tasks in self.findChildren(Tasks))

    def reject(self):
        if not self.pending():
            super().reject()

    def closeEvent(self, event):
        event.ignore() if self.pending() else event.accept()


class ImageCanvas(QGraphicsView):
    zoomed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(Qt.darkGray)

    def load(self, path):
        self.scene().clear()
        image = QPixmap(path)
        if image.isNull():
            raise ValueError(
                "Image preview unavailable. Open File to use its usual application."
            )
        self.scene().addPixmap(image)
        self.fit()

    def fit(self):
        self.fitInView(self.scene().itemsBoundingRect(), Qt.KeepAspectRatio)

    def actual(self):
        self.resetTransform()

    def zoom(self, factor):
        if 0.02 < self.transform().m11() * factor < 100:
            self.scale(factor, factor)
            self.zoomed.emit(self.transform().m11())

    def wheelEvent(self, event):
        self.zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
        event.accept()


class ImageViewer(ViewerDialog):
    def __init__(self, catalog, rows, index, actions, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.rows = rows
        self.index = index
        self.actions = actions
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Research image viewer")
        self.resize(1000, 750)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        layout.addLayout(bar)
        self.title = QLabel()
        bar.addWidget(self.title, 1)
        for title, action in [
            ("Previous", lambda: self.move(-1)),
            ("Next", lambda: self.move(1)),
            ("Fit", lambda: self.canvas.fit()),
            ("100%", lambda: self.canvas.actual()),
            ("+", lambda: self.canvas.zoom(1.2)),
            ("-", lambda: self.canvas.zoom(1 / 1.2)),
            ("Full screen", self.fullscreen),
        ]:
            control = QPushButton(title)
            control.clicked.connect(action)
            bar.addWidget(control)
        self.canvas = ImageCanvas()
        layout.addWidget(self.canvas, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        for title, key in [
            ("Open File", "open"),
            ("Show in Explorer", "show"),
            ("Copy Path", "copy"),
        ]:
            control = QPushButton(title)
            control.clicked.connect(
                lambda checked=False, k=key: self.actions(k, self.rows[self.index])
            )
            bottom.addWidget(control)
        self.tasks = Tasks(self)
        self.request = 0
        self.load()

    def load(self):
        row = self.rows[self.index]
        self.request += 1
        request = self.request
        self.title.setText(row["name"])
        self.details.setText("Loading image...")
        self.tasks.start(
            lambda: previews.image_path(self.catalog, row),
            lambda path: self.loaded(request, path, row),
            lambda msg: self.details.setText(msg) if request == self.request else None,
        )

    def loaded(self, request, path, row):
        if request != self.request:
            return
        try:
            self.canvas.load(path)
        except ValueError as exc:
            self.details.setText(str(exc))
            return
        self.details.setText(
            " | ".join(
                str(row.get(k, ""))
                for k in ("data_origin", "sample_id", "experiment_id", "relative_path")
            )
        )

    def move(self, delta):
        self.index = (self.index + delta) % len(self.rows)
        self.load()

    def fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def closeEvent(self, event):
        if self.tasks.busy():
            event.ignore()
            self.details.setText("Finishing image load. Close again in a moment.")
        else:
            event.accept()


class ImageComparison(ViewerDialog):
    def __init__(self, catalog, rows, parent=None):
        super().__init__(parent)
        self.resize(1200, 750)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Compare images")
        layout = QVBoxLayout(self)
        self.status = QLabel("Loading locally available images...")
        layout.addWidget(self.status)
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        self.canvases = []
        split = QSplitter()
        layout.addWidget(split, 1)
        for row in rows[:2]:
            page = QWidget()
            box = QVBoxLayout(page)
            box.addWidget(QLabel(row["name"] + " | " + row["data_origin"]))
            canvas = ImageCanvas()
            box.addWidget(canvas)
            split.addWidget(page)
            self.canvases.append(canvas)
        for title, action in [
            ("Fit both", lambda: [c.fit() for c in self.canvases]),
            ("100%", lambda: [c.actual() for c in self.canvases]),
            ("Zoom both +", lambda: [c.zoom(1.2) for c in self.canvases]),
            ("Zoom both -", lambda: [c.zoom(1 / 1.2) for c in self.canvases]),
        ]:
            control = QPushButton(title)
            control.clicked.connect(action)
            toolbar.addWidget(control)
        self.tasks = Tasks(self)
        for canvas, row in zip(self.canvases, rows):
            self.tasks.start(
                lambda r=row: previews.image_path(catalog, r),
                lambda path, c=canvas: self.loaded(c, path),
                self.status.setText,
            )

    def loaded(self, canvas, path):
        try:
            canvas.load(path)
            self.status.setText("Drag to pan each image; toolbar zoom applies to both.")
        except ValueError as exc:
            self.status.setText(str(exc))

    def closeEvent(self, event):
        event.ignore() if self.tasks.busy() else event.accept()


class PreviewPanel(QWidget):
    def __init__(self, catalog, actions, parent=None):
        super().__init__(parent)
        self.catalog = catalog
        self.actions = actions
        self.row = None
        self.request = 0
        self.tasks = Tasks(self)
        self.layout_ = QVBoxLayout(self)
        self.heading = QLabel("File details")
        self.heading.setTextFormat(Qt.PlainText)
        self.heading.setWordWrap(True)
        self.heading.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.heading.setStyleSheet("font-size:18px;font-weight:600")
        self.layout_.addWidget(self.heading)
        self.metadata = QLabel("Select a file to view its details and preview.")
        self.metadata.setTextFormat(Qt.PlainText)
        self.metadata.setWordWrap(True)
        self.metadata.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.layout_.addWidget(self.metadata)
        toolbar = QHBoxLayout()
        self.layout_.addLayout(toolbar)
        for title, key in [("Open", "open"), ("Show", "show"), ("Copy path", "copy")]:
            control = QPushButton(title)
            control.clicked.connect(
                lambda checked=False, k=key: (
                    self.actions(k, self.row) if self.row else None
                )
            )
            toolbar.addWidget(control)
        self.locate = QPushButton("Locate file / update reference")
        self.locate.clicked.connect(
            lambda: self.actions("locate", self.row) if self.row else None
        )
        self.layout_.addWidget(self.locate)
        self.locate.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.layout_.addWidget(self.status)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.content, 1)

    def clear_content(self):
        from PySide6.QtPdf import QPdfDocument

        for document in self.content.findChildren(QPdfDocument):
            document.close()
            document.deleteLater()
        while self.content_layout.count():
            widget = self.content_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

    def select(self, row):
        self.row = row
        self.locate.hide()
        self.request += 1
        request = self.request
        self.clear_content()
        self.heading.setText(row["name"])
        with self.catalog.connect() as db:
            links = db.execute(
                "SELECT sample_id,experiment_id FROM research_file_links WHERE file_id=?",
                (row["id"],),
            ).fetchone() or ("", "")
        display = dict(row)
        for key, confirmed in zip(("sample_id", "experiment_id"), links):
            if row.get(key) and row[key] != confirmed:
                display[key] = row[key] + " (inferred; unconfirmed)"

        self.metadata.setText(
            "\n".join(
                f'{k.replace("_"," ").title()}: {display.get(k,"")}'
                for k in (
                    "data_origin",
                    "category",
                    "title",
                    "report_version",
                    "report_status",
                    "data_stage",
                    "sample_id",
                    "experiment_id",
                    "modified",
                    "availability",
                    "size",
                    "tags",
                    "relative_path",
                )
                if row.get(k) not in (None, "")
            )
        )
        self.status.setText("Loading preview...")
        suffix = row.get("extension", "")
        if suffix == ".pdf":
            self.tasks.start(
                lambda: str(previews.resident_path(self.catalog, row)),
                lambda path: self.pdf(request, path),
                lambda msg: self.error(request, msg),
            )
            return
        if suffix in (".csv", ".tsv", ".xlsx"):
            self.tasks.start(
                lambda: (
                    previews.sheets(self.catalog, row) if suffix == ".xlsx" else [],
                    previews.table(self.catalog, row),
                ),
                lambda result: self.tabular(request, result),
                lambda msg: self.error(request, msg),
            )
            return
        if suffix in (
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tif",
            ".tiff",
            ".gif",
            ".webp",
        ):
            self.tasks.start(
                lambda: previews.thumbnail(self.catalog, row, 600),
                lambda path: self.picture(request, path),
                lambda msg: self.error(request, msg),
            )
            return
        self.tasks.start(
            lambda: previews.text(self.catalog, row),
            lambda value: self.textual(request, value, suffix),
            lambda msg: self.error(request, msg),
        )

    def error(self, request, msg):
        if request == self.request:
            self.status.setText(msg)
            try:
                self.locate.setVisible(not self.catalog.safe_path(self.row).is_file())
            except (OSError, ValueError):
                self.locate.show()

    def picture(self, request, path):
        if request != self.request:
            return
        self.status.setText(
            "Cached preview. Double-click an image for the full viewer."
        )
        picture = QLabel()
        picture.setAlignment(Qt.AlignCenter)
        picture.setPixmap(QPixmap(path))
        picture.setScaledContents(False)
        self.content_layout.addWidget(picture, 1)
        control = QPushButton("Open image viewer")
        control.clicked.connect(lambda: self.actions("preview", self.row))
        self.content_layout.addWidget(control)

    def textual(self, request, value, suffix):
        if request != self.request:
            return
        self.status.setText("Bounded text preview; Open shows the complete original.")
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(value)
        if suffix in (
            ".py",
            ".m",
            ".json",
            ".js",
            ".ts",
            ".xml",
            ".yaml",
            ".bat",
            ".ps1",
        ):
            view.setFont(QFont("Consolas", 10))
        self.content_layout.addWidget(view, 1)

    def tabular(self, request, result):
        if request != self.request:
            return
        sheetnames, rows = result
        self.status.setText(
            "Preview: up to 250 rows and 100 columns. Formulas shown as text."
        )
        if sheetnames:
            selector = QComboBox()
            selector.addItems(sheetnames)
            self.content_layout.addWidget(selector)
            selector.currentTextChanged.connect(
                lambda sheet: self.tasks.start(
                    lambda: previews.table(self.catalog, self.row, sheet),
                    lambda data: self.fill_table(request, data),
                    lambda msg: self.error(request, msg),
                )
            )
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.content_layout.addWidget(self.table, 1)
        self.fill_table(request, rows)

    def fill_table(self, request, rows):
        if request != self.request:
            return
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(max((len(r) for r in rows), default=0))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(value))

    def pdf(self, request, path):
        if request != self.request:
            return
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView

        document = QPdfDocument(self.content)
        error = document.load(path)
        if error != QPdfDocument.Error.None_:
            self.error(
                request,
                "PDF preview unavailable. Open File to use its usual application.",
            )
            return
        view = QPdfView()
        view.setDocument(document)
        view.setPageMode(QPdfView.PageMode.SinglePage)
        view.setZoomMode(QPdfView.ZoomMode.FitInView)
        bar = QHBoxLayout()
        barwidget = QWidget()
        barwidget.setLayout(bar)
        self.content_layout.addWidget(barwidget)
        page = QSpinBox()
        page.setRange(1, max(1, document.pageCount()))
        page.setSuffix(" / " + str(document.pageCount()))
        bar.addWidget(page)
        page.valueChanged.connect(
            lambda n: view.pageNavigator().jump(n - 1, QPointF(), 0)
        )
        bar2 = QHBoxLayout()
        barwidget2 = QWidget()
        barwidget2.setLayout(bar2)
        self.content_layout.addWidget(barwidget2)
        for title, action in [
            ("Fit page", lambda: view.setZoomMode(QPdfView.ZoomMode.FitInView)),
            ("Fit width", lambda: view.setZoomMode(QPdfView.ZoomMode.FitToWidth)),
            ("+", lambda: self.pdf_zoom(view, 1.2)),
            ("-", lambda: self.pdf_zoom(view, 1 / 1.2)),
            ("Expand", lambda: self.pdf_dialog(path)),
        ]:
            control = QPushButton(title)
            control.clicked.connect(action)
            control.setToolTip(title)
            (bar if title in ("+", "-") else bar2).addWidget(control)
        self.content_layout.addWidget(view, 1)
        self.status.setText("Rendered PDF | " + str(document.pageCount()) + " pages")

    def pdf_zoom(self, view, factor):
        from PySide6.QtPdfWidgets import QPdfView

        view.setZoomMode(QPdfView.ZoomMode.Custom)
        view.setZoomFactor(view.zoomFactor() * factor)

    def pdf_dialog(self, path):
        dialog = ViewerDialog(self)
        dialog.resize(1100, 800)
        dialog.setWindowTitle("PDF viewer")
        layout = QVBoxLayout(dialog)
        panel = PreviewPanel(self.catalog, self.actions)
        layout.addWidget(panel)
        panel.select(self.row)
        control = QPushButton("Toggle full screen")
        control.clicked.connect(
            lambda: (
                dialog.showNormal()
                if dialog.isFullScreen()
                else dialog.showFullScreen()
            )
        )
        layout.addWidget(control)
        # Loading is bounded; the dialog stays alive until its pending task finishes.
        dialog.finished.connect(lambda: None)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.show()
        self.pdf_window = dialog
        dialog.destroyed.connect(
            lambda: (
                setattr(self, "pdf_window", None) if self.pdf_window is dialog else None
            )
        )
