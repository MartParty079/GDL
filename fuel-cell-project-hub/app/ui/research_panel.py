"""Personal locations and read-only indexing controls, separate from shared setup."""
import copy
import threading
import uuid
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QFileDialog, QTabWidget, QTextEdit, QScrollArea)
from app.services.research_catalog import PATH_LABELS, RESEARCH_CATEGORIES
from app.services.project_storage import IndexCancelled
from app.services.software import open_resource
from app.ui.components import label, Button, InlineMessage, ErrorBanner, local_datetime


class CatalogWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, catalog, options, parent):
        super().__init__(parent)
        self.catalog, self.options = catalog, options
        self.cancelled = threading.Event()

    def run(self):
        try:
            self.completed.emit(self.catalog.refresh(cancel=self.cancelled.is_set,
                                progress=self.progress.emit, **self.options))
        except IndexCancelled:
            self.catalog.log('index_cancelled', action='previous index preserved')
            self.failed.emit('Index cancelled. The previous catalog was preserved.')
        except Exception:
            self.catalog.log('index_failed', action='existing index preserved')
            self.failed.emit('Index unavailable. Your existing catalog and source files were preserved. Check storage access and retry.')


class ResearchPanel(QWidget):
    changed = Signal()
    busy_changed = Signal(bool)

    def __init__(self, settings, parent=None, shared_panel=None):
        super().__init__(parent)
        self.settings, self.worker = settings, None
        self.indexing = False
        self.controls = []
        layout = QVBoxLayout(self)
        layout.addWidget(label('Research storage · Current Project and Legacy Data'))
        layout.addWidget(label('Index and reference existing folders. Sources stay in place; no project marker is created.', 'muted'))
        tabs = QTabWidget()
        layout.addWidget(tabs)
        project = QWidget()
        form = QFormLayout(project)
        form.setFormAlignment(Qt.AlignTop)
        self.project_selector = QComboBox()
        self.project_selector.addItem('Configured active project', '')
        for value in settings.locations.value.get('projects', []):
            self.project_selector.addItem(value['name'], value['id'])
        self.project_selector.currentIndexChanged.connect(self.select_project)
        form.addRow('Project selection', self.project_selector)
        self.name = QLineEdit(settings.locations.value['active']['name'])
        form.addRow('Active project name', self.name)
        self.active = QLineEdit(settings.locations.value['active']['root_path'])
        self.add_path(form, 'Active Project Root', self.active)
        self.legacy = QTextEdit()
        self.legacy.setMaximumHeight(100)
        self.legacy.setPlaceholderText('One legacy source folder per line')
        self.legacy.setPlainText('\n'.join(s['root_path'] for s in settings.locations.value['legacy']))
        form.addRow('Legacy Roots · read-only Old Test Data', self.legacy)
        form.addRow(Button('Add legacy folder', self.add_legacy))
        tabs.addTab(project, 'Project')
        storage = QWidget()
        storage_form = QFormLayout(storage)
        storage_form.setFormAlignment(Qt.AlignTop)
        self.paths = {}
        for key, title in PATH_LABELS.items():
            field = QLineEdit(settings.locations.value[key])
            self.paths[key] = field
            self.add_path(storage_form, title, field)
        tabs.addTab(storage, 'Storage')
        indexing = QWidget()
        index_layout = QVBoxLayout(indexing)
        for title, options in [('Index Current Project', {'tier': 'active'}), ('Index Legacy Data', {'tier': 'legacy'}),
            ('Index Everything', {}), ('Quick Refresh', {'quick': True}), ('Rebuild Index', {'rebuild': True}),
            ('Index Selected Folder', {'choose': True})]:
            control = Button(title, lambda checked=False, values=options: self.start_index(**values))
            self.controls.append(control)
            index_layout.addWidget(control)
        index_layout.addWidget(Button('Cancel indexing', self.cancel_index))
        index_layout.addWidget(label('Quick refresh compares metadata. Full indexing hashes resident files up to 1 MB, at most 32 MB per run. Rebuild backs up the catalog and retains manual metadata.', 'muted'))
        tabs.addTab(indexing, 'Indexing')
        categories = QWidget()
        categories_layout = QVBoxLayout(categories)
        categories_layout.addWidget(label('Categories describe research without moving its files. Edit classification, tags, title and notes from Project Files. Manual metadata takes priority.', 'muted'))
        category_list = QTextEdit()
        category_list.setReadOnly(True)
        category_list.setPlainText('\n'.join(RESEARCH_CATEGORIES))
        category_list.setMaximumHeight(180)
        categories_layout.addWidget(category_list)
        categories_layout.addStretch()
        tabs.addTab(categories, 'Categories')
        if shared_panel:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(shared_panel)
            tabs.addTab(scroll, 'Advanced shared setup')
        actions = QHBoxLayout()
        self.save_button = Button('Save locations', self.save)
        actions.addWidget(self.save_button)
        actions.addWidget(Button('Validate paths', self.validate_paths))
        actions.addWidget(Button('Reset fields to defaults', self.reset_defaults))
        layout.addLayout(actions)
        self.status = InlineMessage()
        layout.addWidget(self.status)
        self.error = ErrorBanner()
        layout.addWidget(self.error)
        layout.addStretch()
        self.refresh_status()

    def add_path(self, form, name, field):
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(Button('Browse', lambda: self.browse(field)))
        row.addWidget(Button('Open', lambda: self.open_path(field)))
        form.addRow(name, row)

    def browse(self, field):
        value = QFileDialog.getExistingDirectory(self, 'Select storage folder', field.text())
        if value:
            field.setText(value)

    def open_path(self, field):
        try:
            path = Path(field.text())
            if not path.is_dir():
                raise ValueError('This folder is disconnected or has not been created yet.')
            open_resource(str(path))
        except (OSError, ValueError) as exc:
            self.error.show_error('Folder unavailable', exc)

    def add_legacy(self):
        value = QFileDialog.getExistingDirectory(self, 'Add read-only legacy source')
        if value:
            self.legacy.append(value)

    def select_project(self):
        identity = self.project_selector.currentData()
        project = next((s for s in self.settings.locations.value.get('projects', []) if s['id'] == identity), None)
        if project:
            self.name.setText(project['name'])
            self.active.setText(project['root_path'])

    def values(self):
        value = copy.deepcopy(self.settings.locations.value)
        selected = next((s for s in value.get('projects', []) if s['id'] == self.project_selector.currentData()), None)
        if selected:
            value['active'] = copy.deepcopy(selected)
        value['active'].update(name=self.name.text().strip() or 'Research Project', root_path=self.active.text().strip())
        old = {s['root_path']: s for s in value['legacy']}
        value['legacy'] = []
        for path in dict.fromkeys(p.strip() for p in self.legacy.toPlainText().splitlines() if p.strip()):
            source = copy.deepcopy(old.get(path) or value['active'])
            if path not in old:
                source.update(id=str(uuid.uuid4()), name=Path(path).name, root_path=path)
            value['legacy'].append(source)
        value.update({k: f.text().strip() for k, f in self.paths.items()})
        return value

    def save(self):
        if self.indexing:
            return False
        try:
            self.settings.save_locations(self.values())
            self.project_selector.blockSignals(True)
            self.project_selector.clear()
            self.project_selector.addItem('Configured active project', '')
            for source in self.settings.locations.value.get('projects', []):
                self.project_selector.addItem(source['name'], source['id'])
            self.project_selector.blockSignals(False)
            self.refresh_status()
            self.changed.emit()
            return True
        except (OSError, ValueError) as exc:
            self.error.show_error('Locations could not be saved', exc)
            return False

    def validate_paths(self):
        try:
            self.settings.locations.validate(self.values())
            self.status.set_message('\n'.join(f"{key}: {'Available' if Path(path).is_dir() else 'Disconnected / will be created when needed'}" for key, path in
                [('Current', self.active.text()), *[('Legacy', p) for p in self.legacy.toPlainText().splitlines()],
                 *[(k, f.text()) for k, f in self.paths.items()]]))
        except (OSError, ValueError) as exc:
            self.error.show_error('Path validation failed', exc)

    def reset_defaults(self):
        if self.indexing:
            return
        value = self.settings.locations.defaults()
        self.project_selector.setCurrentIndex(0)
        self.name.setText(value['active']['name'])
        self.active.setText(value['active']['root_path'])
        self.legacy.setPlainText('\n'.join(s['root_path'] for s in value['legacy']))
        for key, field in self.paths.items():
            field.setText(value[key])
        self.status.set_message('Default fields restored. Save locations to apply; source files and previous catalogs are preserved.')

    def refresh_status(self):
        value = self.settings.locations.value
        message = '\n'.join(s['name'] + ': ' + s['status'] for s in self.settings.locations.status())
        if self.settings.catalog:
            summary = self.settings.catalog.summary()
            message += f"\nCurrent: {summary['current']:,} · Legacy: {summary['legacy']:,} · Last indexed: {local_datetime(summary['last_indexed']) if summary['last_indexed'] else 'Not indexed'}"
        else:
            message += '\n' + (getattr(self.settings, 'catalog_error', '') or 'Save locations to enable the research catalog.')
        self.status.set_message(message)

    def start_index(self, tier=None, choose=False, **options):
        if self.indexing or not self.save():
            return
        if not self.settings.catalog:
            self.status.set_message(self.settings.catalog_error, 'warning')
            return
        if tier:
            options['source_ids'] = [s['id'] for s in self.settings.locations.sources() if s['source_type'] == tier]
        if choose:
            source = self.settings.locations.value['active']
            path = QFileDialog.getExistingDirectory(self, 'Index a current project subfolder', source['root_path'])
            if not path:
                return
            try:
                options.update(selected=Path(path).resolve().relative_to(Path(source['root_path']).resolve()).as_posix(), source_ids=[source['id']])
            except ValueError:
                self.error.show_error('Choose a project subfolder', 'The selected folder must be inside the active project.')
                return
        self.indexing = True
        self.busy_changed.emit(True)
        self.save_button.setEnabled(False)
        for control in self.controls:
            control.setEnabled(False)
        self.worker = CatalogWorker(self.settings.catalog, options, self)
        self.worker.completed.connect(self.completed)
        self.worker.failed.connect(lambda message: self.status.set_message(message, 'warning'))
        self.worker.progress.connect(lambda count: self.status.set_message(f'Indexing… {count:,} files scanned'))
        self.worker.finished.connect(self.finished)
        self.status.set_message('Indexing research sources…')
        self.worker.start()

    def completed(self, summary):
        self.status.set_message(' · '.join(f'{k}: {v:,}' for k, v in summary.items()), 'success' if not summary['errors'] else 'warning')
        self.changed.emit()

    def finished(self):
        self.indexing = False
        self.save_button.setEnabled(True)
        for control in self.controls:
            control.setEnabled(True)
        self.worker.deleteLater()
        self.worker = None
        self.busy_changed.emit(False)
        self.changed.emit()

    def cancel_index(self):
        if self.worker:
            self.worker.cancelled.set()
