"""Personal locations and read-only indexing controls, separate from shared setup."""
import copy
import threading
import uuid
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QFileDialog, QTabWidget, QTextEdit, QScrollArea, QCheckBox, QSpinBox, QInputDialog)
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
            self.failed.emit('Index cancelled. The previous published index is preserved; pending work will be reconciled on the next refresh.' if self.catalog.shared else 'Index cancelled. Completed batches are saved; unfinished sources will be reconciled on the next refresh.')
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
        layout.addWidget(label('Sources stay in place. Shared project clients read verified published revisions.', 'muted'))
        if settings.store.shared_index:
            layout.addWidget(Button('Choose synchronized copy for next launch', self.remap_shared))
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
        self.additional = QTextEdit()
        self.additional.setMaximumHeight(80)
        self.additional.setPlainText('\n'.join(s['root_path'] for s in settings.locations.value.get('additional', [])))
        self.additional.setPlaceholderText('One additional source folder per line; use Add source to choose its type')
        form.addRow('Additional sources', self.additional)
        form.addRow(Button('Add current / reference / archive source', self.add_source))
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
            ('Full Scan', {}), ('Quick Refresh', {'quick': True}), ('Rebuild Entire Index', {'rebuild': True}),
            ('Rebuild Search Index', {'mode': 'search'}),
            ('Index Selected Folder', {'choose': True})]:
            control = Button(title, lambda checked=False, values=options: self.start_index(**values))
            self.controls.append(control)
            index_layout.addWidget(control)
        index_layout.addWidget(Button('Cancel indexing', self.cancel_index))
        index_layout.addWidget(label('Quick refresh reprocesses changed resident documents. Online-only files receive metadata. Rebuilds back up the index and retain manual metadata.', 'muted'))
        options = settings.store.local.get('native_indexing', {})
        self.auto_refresh = QCheckBox('Automatic reconciliation')
        self.auto_refresh.setChecked(options.get('automatic', False))
        self.watching = QCheckBox('Watch current folders for changes')
        self.watching.setChecked(options.get('watching', False))
        index_layout.addWidget(self.auto_refresh)
        index_layout.addWidget(self.watching)
        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setValue(options.get('minutes', 10))
        index_layout.addWidget(label('Reconciliation interval (minutes)'))
        index_layout.addWidget(self.interval)
        from app.indexing.extractor import DEFAULT_LIMITS
        limits = {**DEFAULT_LIMITS, **options.get('limits', {})}
        self.extraction = QCheckBox('Extract locally available document content')
        self.extraction.setChecked(limits['enabled'])
        index_layout.addWidget(self.extraction)
        self.limit_fields = {}
        limits_form = QFormLayout()
        for key, caption in (('max_file_bytes', 'Maximum content file size (MB)'), ('max_text_chars', 'Maximum extracted text (characters)'), ('max_cells', 'Maximum spreadsheet cells'), ('max_pages', 'Maximum PDF pages / slides')):
            control = QSpinBox()
            control.setRange(1, 10000000)
            control.setValue(limits[key] // (1024 * 1024) if key == 'max_file_bytes' else limits[key])
            self.limit_fields[key] = control
            limits_form.addRow(caption, control)
        index_layout.addLayout(limits_form)
        index_scroll = QScrollArea()
        index_scroll.setWidgetResizable(True)
        index_scroll.setWidget(indexing)
        tabs.addTab(index_scroll, 'Indexing')
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
        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        for caption, callback in (('Backup Index', self.backup), ('Restore Index', self.restore), ('Index Run History', self.history), ('Edit Classification Rules', self.edit_rules)):
            advanced_layout.addWidget(Button(caption, callback))
        from app.ui.folder_mappings import FolderMappingsPanel
        mappings = QScrollArea()
        mappings.setWidgetResizable(True)
        mappings.setWidget(FolderMappingsPanel(settings, self))
        advanced_layout.addWidget(mappings)
        advanced_layout.addStretch()
        tabs.addTab(advanced, 'Advanced')
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
        from app.indexing.watcher import IndexWatcher
        self.watcher = IndexWatcher(self)
        self.watcher.refresh_requested.connect(self.request_reconciliation)
        self.configure_watcher()
        if settings.store.shared_index:
            for field in [self.name, self.active, self.legacy, self.additional, *self.paths.values()]:
                field.setReadOnly(True)
            self.shared_poll = QTimer(self)
            self.shared_poll.timeout.connect(self.poll_shared)
            self.shared_poll.start(30000)
        if options.get('automatic', False):
            QTimer.singleShot(1500, self.automatic_refresh)

    def add_path(self, form, name, field):
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(Button('Browse', lambda: self.browse(field)))
        row.addWidget(Button('Open', lambda: self.open_path(field)))
        form.addRow(name, row)

    def remap_shared(self):
        if self.indexing:
            self.status.set_message('Finish indexing before changing the next-launch mapping.', 'warning')
            return
        root = QFileDialog.getExistingDirectory(self, 'Select a synchronized copy of this shared project')
        if not root:
            return
        try:
            from app.services.shared_index import SharedIndex
            candidate = SharedIndex(self.settings.store, root, self.settings.store.shared_index.identity['project_id'])
            self.settings.store.local.update(shared_root=str(candidate.root), project_locations=candidate.locations())
            self.settings.store.save_local()
            self.status.set_message('Verified mapping saved. Reopen Beta to use this synchronized copy. Current operations can finish normally.')
        except (OSError, ValueError):
            self.status.set_message('Select an accessible synchronized copy with this project identity.', 'warning')

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

    def add_source(self):
        path = QFileDialog.getExistingDirectory(self, 'Add a research source')
        if not path:
            return
        kind, okay = QInputDialog.getItem(self, 'Source type', 'Dataset source type', ['active', 'reference', 'archive'], 0, False)
        if okay:
            if not hasattr(self, 'pending_sources'):
                self.pending_sources = {}
            self.pending_sources[path] = kind
            self.additional.append(path)

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
                source.update(id=str(uuid.uuid4()), name=Path(path).name, source_label=Path(path).name, root_path=path)
            value['legacy'].append(source)
        old_additional = {s['root_path']: s for s in value.get('additional', [])}
        value['additional'] = []
        for path in dict.fromkeys(p.strip() for p in self.additional.toPlainText().splitlines() if p.strip()):
            source = copy.deepcopy(old_additional.get(path) or value['active'])
            if path not in old_additional:
                source.update(id=str(uuid.uuid4()), name=Path(path).name, source_label=Path(path).name, root_path=path)
            kind = getattr(self, 'pending_sources', {}).get(path, source.get('source_type', 'active'))
            source.update(source_type=kind, project_type=kind, dataset_status='current' if kind == 'active' else kind, read_only=kind != 'active')
            value['additional'].append(source)
        value.update({k: f.text().strip() for k, f in self.paths.items()})
        return value

    def save(self):
        if self.indexing:
            return False
        try:
            self.settings.save_locations(self.settings.locations.value if self.settings.store.shared_index else self.values())
            from app.indexing.extractor import DEFAULT_LIMITS
            limits = dict(DEFAULT_LIMITS)
            limits['enabled'] = self.extraction.isChecked()
            for key, control in self.limit_fields.items():
                limits[key] = control.value() * (1024 * 1024) if key == 'max_file_bytes' else control.value()
            self.settings.store.local['native_indexing'] = {'automatic': self.auto_refresh.isChecked(),
                'watching': self.watching.isChecked(), 'minutes': self.interval.value(), 'limits': limits}
            self.settings.store.save_local()
            self.configure_watcher()
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
        self.additional.clear()
        for key, field in self.paths.items():
            field.setText(value[key])
        self.status.set_message('Default fields restored. Save locations to apply; source files and previous catalogs are preserved.')

    def refresh_status(self):
        value = self.settings.locations.value
        message = '\n'.join(s['name'] + ': ' + s['status'] for s in self.settings.locations.status())
        shared = self.settings.store.shared_index
        if shared:
            message += '\n' + ('Configured indexing authority' if shared.authority else 'Published index reader')
            message += ' · Revision ' + (shared.revision or 'not published')
        if self.settings.catalog:
            summary = self.settings.catalog.summary()
            message += f"\nCurrent: {summary['current']:,} · Legacy: {summary['legacy']:,} · Last indexed: {local_datetime(summary['last_indexed']) if summary['last_indexed'] else 'Not indexed'}"
        else:
            message += '\n' + (getattr(self.settings, 'catalog_error', '') or 'Save locations to enable the research catalog.')
        self.status.set_message(message)

    def start_index(self, tier=None, choose=False, apply_settings=True, **options):
        accounts = getattr(self.settings.store, 'accounts', None)
        if accounts and not accounts.admin_unlocked:
            self.status.set_message('Select Admin and enter its PIN to manage indexing.', 'warning')
            return
        shared = self.settings.store.shared_index
        if shared and not shared.authority:
            shared.submit('refresh', {})
            self.status.set_message('Index request queued. The configured authority will publish the update; no local rebuild is required.')
            return
        if self.indexing or (apply_settings and not self.save()):
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
        if getattr(self.settings.store, "accounts", None): self.settings.store.accounts.event("INDEX_STARTED")
        self.busy_changed.emit(True)
        self.save_button.setEnabled(False)
        for control in self.controls:
            control.setEnabled(False)
        self.worker = CatalogWorker(self.settings.catalog, options, self)
        self.worker.completed.connect(self.completed)
        self.worker.failed.connect(self.index_failed)
        self.worker.progress.connect(lambda count: self.status.set_message(f'{self.settings.catalog.phase}… {count:,} files scanned'))
        self.worker.finished.connect(self.finished)
        self.status.set_message('Indexing research sources…')
        self.worker.start()

    def completed(self, summary):
        if getattr(self.settings.store, "accounts", None): self.settings.store.accounts.event("INDEX_COMPLETED", details={"count":summary.get("current",0)+summary.get("legacy",0)})
        counts = {k: v for k, v in summary.items() if isinstance(v, (int, float))}
        self.status.set_message(' · '.join(f'{k}: {v:,}' for k, v in counts.items()), 'success' if not summary.get('errors', 0) else 'warning')
        self.changed.emit()

    def index_failed(self, message):
        self.status.set_message(message, "warning")
        if getattr(self.settings.store, "accounts", None): self.settings.store.accounts.event("INDEX_FAILED")

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

    def configure_watcher(self):
        if not hasattr(self, 'watcher'):
            return
        settings = self.settings.store.local.get('native_indexing', {})
        roots = [s['root_path'] for s in self.settings.locations.sources() if s['source_type'] == 'active']
        self.watcher.configure(roots, settings.get('watching', False), settings.get('automatic', False), settings.get('minutes', 10))

    def automatic_refresh(self):
        if self.settings.store.shared_index and not self.settings.store.shared_index.authority:
            self.poll_shared()
            return
        if not self.indexing and self.settings.catalog:
            self.start_index(tier='active', quick=True, apply_settings=False)

    def request_reconciliation(self):
        shared = self.settings.store.shared_index
        if shared and not shared.authority:
            shared.submit('refresh', {})
            self.poll_shared()
        else:
            self.automatic_refresh()

    def poll_shared(self):
        shared = self.settings.store.shared_index
        previous = shared.revision
        shared.load()
        if shared.path and not self.settings.catalog:
            self.settings.connect_catalog()
            self.changed.emit()
        elif previous != shared.revision:
            self.changed.emit()
        self.status.set_message(shared.status)

    def backup(self):
        if self.indexing or not self.settings.catalog:
            return
        try:
            self.settings.catalog.backup('manual-backup')
            self.status.set_message('Index backup saved to the configured Backups folder.', 'success')
        except (OSError, ValueError) as exc:
            self.error.show_error('Backup unavailable', exc)

    def restore(self):
        if self.indexing or not self.settings.catalog:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Restore a research index backup', self.settings.locations.value['backups'], 'SQLite (*.sqlite3)')
        if not path:
            return
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, 'Restore Index?', 'Back up the current index and restore this backup? Research files will remain unchanged.') != QMessageBox.Yes:
            return
        try:
            self.settings.catalog.restore(path)
            self.changed.emit()
            self.refresh_status()
        except Exception:
            self.error.show_error('Restore unavailable', 'The existing index was preserved. Choose a valid index backup.')

    def history(self):
        if not self.settings.catalog:
            return
        import json
        from PySide6.QtWidgets import QDialog
        dialog = QDialog(self)
        dialog.setWindowTitle('Index Run History')
        dialog.resize(720, 480)
        layout = QVBoxLayout(dialog)
        output = QTextEdit()
        output.setReadOnly(True)
        output.setPlainText(json.dumps({'runs': self.settings.catalog.history(), 'recent_errors': self.settings.catalog.errors()}, indent=2))
        layout.addWidget(output)
        layout.addWidget(Button('Close', dialog.accept))
        dialog.exec()

    def edit_rules(self):
        import json
        from app.services.storage import read_json
        from PySide6.QtWidgets import QDialog
        dialog = QDialog(self)
        dialog.setWindowTitle('Classification keyword rules')
        layout = QVBoxLayout(dialog)
        output = QTextEdit()
        template = read_json(self.settings.store.config_dir / 'indexing_rules.json', {}).get('keywords', {})
        output.setPlainText(json.dumps(self.settings.store.local.get('native_category_rules', template), indent=2))
        layout.addWidget(output)
        layout.addWidget(Button('Save rules', dialog.accept))
        if dialog.exec():
            try:
                rules = json.loads(output.toPlainText())
                if not isinstance(rules, dict) or any(not isinstance(k, str) or not k.strip() or v not in RESEARCH_CATEGORIES for k, v in rules.items()):
                    raise ValueError('Use keyword strings mapped to supported research categories.')
                self.settings.store.local['native_category_rules'] = rules
                self.settings.store.save_local()
            except (ValueError, TypeError) as exc:
                self.error.show_error('Invalid category rules', exc)
