"""Optional account setup, async Graph browsing and historical reference controls."""
import copy
import threading
from pathlib import Path

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QDialog, QMessageBox, QFileDialog, QInputDialog)
from PySide6.QtCore import Qt
from app.ui.components import Button, AppCard, SectionHeader, InlineMessage, ErrorBanner, label, notify
from app.services.storage_settings import FOLDERS, LEGACY_NOTE
from app.services.project_storage import IndexCancelled


class Task(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.cancelled = threading.Event()

    def run(self):
        try:
            self.completed.emit(self.action())
        except Exception as exc:
            self.failed.emit(str(exc))


class AsyncPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = []
        self.error = ErrorBanner()
        self.status = InlineMessage()

    def work(self, action, done):
        if self.tasks:
            self.status.set_message('Wait for the current operation to finish.', 'info')
            return
        self.error.hide()
        self.status.set_message('Working…', 'info')
        task = Task(action, self)
        self.tasks.append(task)
        task.completed.connect(done)
        task.failed.connect(lambda message: self.error.show_error('Operation could not finish', message))
        task.finished.connect(lambda: self.finished(task))
        task.start()

    def finished(self, task):
        self.tasks.remove(task)
        task.deleteLater()
        self.status.set_message('')

    def run(self, action):
        try:
            result = action()
            self.changed.emit()
            return result
        except (OSError, ValueError) as exc:
            self.error.show_error('Settings could not be changed', exc)


class MicrosoftAccountPanel(AsyncPanel):
    def __init__(self, auth, graph, parent=None):
        super().__init__(parent)
        self.auth, self.graph = auth, graph
        layout = QVBoxLayout(self)
        layout.addWidget(SectionHeader('Microsoft account', 'University sign-in opens your browser. Local storage works without an account.'))
        card = AppCard('Public client registration')
        layout.addWidget(card)
        form = QFormLayout()
        config = auth.registration()
        self.client = QLineEdit(config.get('client_id', ''))
        self.tenant = QLineEdit(config.get('tenant_id', 'organizations'))
        form.addRow('Application (client) ID', self.client)
        form.addRow('Directory (tenant) ID', self.tenant)
        card.layout().addLayout(form)
        card.layout().addWidget(label('Basic login requests User.Read only. Own-file access is optional; SharePoint permissions are requested only when you connect SharePoint storage.', 'muted'))
        card.layout().addWidget(Button('Save registration', lambda: self.run(lambda: auth.configure(self.client.text().strip(), self.tenant.text().strip() or 'organizations'))))
        self.identity = label('Signed out')
        layout.addWidget(self.identity)
        self.permissions = label('')
        layout.addWidget(self.permissions)
        row = QHBoxLayout()
        for caption, callback in (('Sign in', self.sign_in), ('Test connection', self.test), ('Reconnect', self.sign_in), ('Sign out / clear cache', self.sign_out)):
            row.addWidget(Button(caption, callback))
        layout.addLayout(row)
        layout.addWidget(self.status)
        layout.addWidget(self.error)
        layout.addStretch()
        layout.removeWidget(self.identity)
        layout.removeWidget(self.permissions)
        layout.removeItem(row)
        layout.insertWidget(1, self.identity)
        layout.insertWidget(2, self.permissions)
        layout.insertLayout(3, row)
        self.update_identity()

    def update_identity(self, me=None):
        account = self.auth.get_account()
        if me:
            account.update(display_name=me.get('displayName', ''), username=me.get('userPrincipalName', ''), id=me.get('id', ''))
            self.auth.account = account
        self.identity.setText('\n'.join([self.auth.connection_status()] + [str(account[k]) for k in ('display_name', 'username', 'tenant_id', 'id') if account.get(k)]))
        self.update_permissions()
        self.changed.emit()

    def update_permissions(self):
        states = self.auth.permission_status()
        connected = 'Connected' if self.auth.get_account() and self.auth.connection_status() == 'Connected' else self.auth.connection_status()
        self.permissions.setText('Microsoft account: ' + connected + '\nBasic Graph access: ' + states['basic'] +
            '\nOwn-file Graph access: ' + states['files'] + '\nSharePoint cloud indexing: ' +
            ('Unavailable — connect SharePoint storage to enable' if states['sharepoint'] == 'Not enabled' else states['sharepoint']) +
            '\nLocal OneDrive / Files On-Demand indexing remains available.')

    def finished(self, task):
        super().finished(task)
        self.update_identity()

    def sign_in(self):
        self.identity.setText('Signing in… Complete the Microsoft prompt in your browser.')
        self.work(self.auth.sign_in, lambda _: self.update_identity())

    def test(self):
        self.work(self.graph.get_me, self.update_identity)

    def sign_out(self):
        self.work(self.auth.sign_out, lambda _: self.update_identity())


class CloudFolderPicker(QDialog):
    """Browse by names; IDs remain internal. All requests run outside the UI thread."""
    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.graph, self.tasks = graph, []
        self.selection = None
        self.site_id, self.drive_id = '', ''
        self.folder_id = 'root'
        self.parents = []
        self.setWindowTitle('Choose a Microsoft project folder')
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        self.caption = label('Browse your OneDrive or search university SharePoint sites.')
        layout.addWidget(self.caption)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('SharePoint site name…')
        row.addWidget(self.search)
        row.addWidget(Button('Connect SharePoint / search sites', self.sites))
        row.addWidget(Button('My OneDrive', self.drives))
        layout.addLayout(row)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.enter)
        layout.addWidget(self.list)
        self.error = ErrorBanner()
        layout.addWidget(self.error)
        layout.addWidget(label('If university approval is required, continue with Local OneDrive / Files On-Demand in Storage settings.', 'muted'))
        controls = QHBoxLayout()
        controls.addWidget(Button('Up', self.up))
        self.choose_button = Button('Use this folder', self.choose)
        self.choose_button.setEnabled(False)
        controls.addWidget(self.choose_button)
        controls.addWidget(Button('Cancel', self.reject))
        layout.addLayout(controls)
        # Opening the picker does not trigger consent. Permission requests follow
        # an explicit My OneDrive or Connect SharePoint action.

    def load(self, action, kind):
        if self.tasks:
            return
        self.kind = kind
        self.list.setEnabled(False)
        self.choose_button.setEnabled(False)
        self.caption.setText('Loading Microsoft folders…')
        task = Task(action, self)
        self.tasks.append(task)
        task.completed.connect(self.loaded)
        task.failed.connect(lambda message: self.error.show_error('Cloud browsing unavailable', message))
        task.finished.connect(lambda: self.finished(task))
        task.start()

    def finished(self, task):
        self.tasks.remove(task)
        task.deleteLater()
        self.list.setEnabled(True)

    def loaded(self, rows):
        self.error.hide()
        self.list.clear()
        for value in rows:
            if self.kind == 'folders' and 'folder' not in value:
                continue
            item = QListWidgetItem(value.get('name', value.get('displayName', 'Unnamed')))
            item.setData(Qt.UserRole, value)
            self.list.addItem(item)
        self.caption.setText('Double-click to browse. Use this folder selects the folder currently displayed.' if self.kind == 'folders' else 'Double-click a site or document library.')
        self.choose_button.setEnabled(self.kind == 'folders')

    def drives(self):
        self.site_id, self.drive_id, self.parents = '', '', []
        def action():
            self.graph.auth.enable_access('files')
            return self.graph.list_drives()
        self.load(action, 'drives')

    def sites(self):
        query = self.search.text().strip()
        def action():
            self.graph.auth.enable_access('sharepoint')
            return self.graph.list_sites(query)
        self.load(action, 'sites')

    def enter(self, item):
        if self.tasks:
            return
        data = item.data(Qt.UserRole)
        if self.kind == 'sites':
            self.site_id = data['id']
            self.load(lambda: self.graph.list_document_libraries(self.site_id), 'drives')
        elif self.kind == 'drives':
            self.drive_id, self.folder_id, self.parents = data['id'], 'root', []
            self.load(lambda: self.graph.list_children(self.drive_id), 'folders')
        else:
            self.parents.append(self.folder_id)
            self.folder_id = data['id']
            self.load(lambda: self.graph.list_children(self.drive_id, self.folder_id), 'folders')

    def up(self):
        if self.tasks:
            return
        if self.parents:
            self.folder_id = self.parents.pop()
            self.load(lambda: self.graph.list_children(self.drive_id, self.folder_id), 'folders')
        else:
            self.drives()

    def choose(self):
        if self.kind == 'folders' and not self.tasks:
            self.selection = {'site_id': self.site_id, 'drive_id': self.drive_id, 'root_item_id': self.folder_id}
            self.accept()

    def reject(self):
        if self.tasks:
            self.error.show_error('Please wait', 'The current metadata request must finish before closing this picker.')
            return
        super().reject()

    def closeEvent(self, event):
        if self.tasks:
            event.ignore()
        else:
            event.accept()


class CloudStoragePanel(AsyncPanel):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings, self.store = settings, settings.store
        layout = QVBoxLayout(self)
        layout.addWidget(SectionHeader('Cloud and historical sources', 'Cloud indexing reads metadata. Historical projects stay separate from current work.'))
        self.mode = QComboBox()
        self.mode.addItems(['LocalOnly', 'CloudOnly', 'Hybrid'])
        self.mode.setCurrentText(self.store.local.get('storage_mode', 'LocalOnly'))
        self.mode.currentTextChanged.connect(lambda mode: self.run(lambda: settings.set_mode(mode)))
        form = QFormLayout()
        form.addRow('Storage mode on this computer', self.mode)
        self.cache = QLineEdit(str(settings.cache_dir()))
        form.addRow('Local legacy cache folder', self.cache)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(Button('Browse cache', self.browse_cache))
        row.addWidget(Button('Use new cache location', lambda: self.run(lambda: settings.set_legacy_cache(self.cache.text()))))
        row.addWidget(Button('Reset cache location', lambda: self.run(lambda: settings.set_legacy_cache(str(self.store.local_dir / 'legacy')))))
        layout.addLayout(row)
        layout.addWidget(label('Changing the cache location preserves old caches and does not move files.', 'muted'))
        self.connection = label('')
        layout.addWidget(self.connection)
        self.permissions = label('')
        layout.addWidget(self.permissions)
        row = QHBoxLayout()
        for caption, callback in (('Connect / change current cloud folder', lambda: self.connect(False)), ('Refresh current cloud index', lambda: self.refresh(False)), ('Disconnect current cloud', self.disconnect), ('Add previous project', lambda: self.connect(True))):
            row.addWidget(Button(caption, callback))
        layout.addLayout(row)
        layout.addWidget(label('Old Test Data', 'heading'))
        self.projects = QListWidget()
        self.projects.setMinimumHeight(160)
        layout.addWidget(self.projects)
        row = QHBoxLayout()
        for caption, callback in (('Browse files', self.browse_legacy), ('Refresh selected legacy index', lambda: self.refresh(True)), ('Open online', self.open_legacy), ('Edit note', self.edit_note), ('Cancel refresh', self.cancel)):
            row.addWidget(Button(caption, callback))
        layout.addLayout(row)
        layout.addWidget(self.status)
        layout.addWidget(self.error)
        self.reload()

    def reload(self):
        states = self.settings.graph.auth.permission_status()
        self.permissions.setText('Basic Graph access: ' + states['basic'] + '\nSharePoint cloud indexing: ' +
            ('Unavailable — connect SharePoint storage to enable' if states['sharepoint'] == 'Not enabled' else states['sharepoint']) +
            '\nLocal OneDrive indexing is available when cloud access is blocked.')
        current = self.store.project.get('current_cloud_connection', {})
        if current:
            try:
                summary = self.settings.provider(current).summary()
                self.connection.setText(f"Current cloud: {current['web_url']}\n{summary['files']:,} files · Last indexed: {summary['last_index_time'] or 'Never'} · {summary['status']}")
            except (OSError, ValueError):
                self.connection.setText('Current cloud cache unavailable. Its existing file has been preserved.')
        else:
            self.connection.setText('No current cloud folder connected.')
        self.projects.clear()
        for project in self.store.project.get('legacy_projects', []):
            try:
                summary = self.settings.provider(project).summary()
                detail = f"{summary['files']:,} files · {summary['total_size']:,} bytes · {summary['status']}"
            except (OSError, ValueError):
                detail = 'Cache unavailable; refresh to retry'
            item = QListWidgetItem(project['name'] + ' · ' + project['legacy_project_id'] + '\n' + detail + '\n' + project['note'])
            item.setData(Qt.UserRole, project)
            item.setToolTip('Imported: ' + project['imported_on'] + '\n' + project['web_url'])
            self.projects.addItem(item)

    def browse_cache(self):
        path = QFileDialog.getExistingDirectory(self, 'Select local legacy cache folder', self.cache.text())
        if path:
            self.cache.setText(path)

    def selected_project(self):
        item = self.projects.currentItem()
        if not item:
            self.status.set_message('Select a previous project first.', 'info')
            return None
        return item.data(Qt.UserRole)

    def connect(self, legacy):
        if self.tasks:
            return
        picker = CloudFolderPicker(self.settings.graph, self)
        accepted = picker.exec()
        self.reload()
        self.changed.emit()
        if not accepted:
            return
        name, note = '', LEGACY_NOTE
        if legacy:
            name, accepted = QInputDialog.getText(self, 'Previous project name', 'Name for this historical project:')
            if not accepted:
                return
            note, accepted = QInputDialog.getMultiLineText(self, 'Historical project note', 'Reference note:', LEGACY_NOTE)
            if not accepted:
                return
        if QMessageBox.question(self, 'Confirm historical reference' if legacy else 'Change current cloud connection',
                'Add this folder as Old Test Data, excluded from current work?' if legacy else 'Use this cloud folder for current project metadata? Files will remain in place.') != QMessageBox.Yes:
            return
        self.work(lambda: self.settings.connect_cloud(picker.selection, legacy, name, note), self.saved)

    def saved(self, _):
        self.reload()
        self.changed.emit()
        notify(self, 'Storage metadata saved', 'success')

    def finished(self, task):
        super().finished(task)
        self.reload()
        self.changed.emit()

    def disconnect(self):
        if QMessageBox.question(self, 'Disconnect current cloud?', 'Remove only the current cloud connection? Local storage, legacy references and files remain in place.') == QMessageBox.Yes:
            self.run(self.settings.disconnect_cloud)
            self.reload()

    def refresh(self, legacy):
        connection = self.selected_project() if legacy else self.store.project.get('current_cloud_connection')
        if not connection:
            self.status.set_message('Connect a current cloud folder first.' if not legacy else 'Select a previous project.', 'info')
            return
        provider = self.settings.provider(connection)
        # Capture this particular task's cancellation signal.
        self.work(lambda: provider.refresh(cancel=lambda: bool(self.tasks and self.tasks[0].cancelled.is_set())), self.saved)

    def cancel(self):
        if self.tasks:
            self.tasks[0].cancelled.set()

    def browse_legacy(self):
        project = self.selected_project()
        window = self.window()
        if project and hasattr(window, 'files_panel'):
            window.files_panel.origin.setCurrentIndex(window.files_panel.origin.findData('legacy'))
            window.files_panel.legacy_filter.setCurrentIndex(window.files_panel.legacy_filter.findData(project['legacy_project_id']))
            window.open_workspace('Files & Data')

    def open_legacy(self):
        project = self.selected_project()
        if project:
            from app.services.software import open_resource
            self.run(lambda: open_resource(project['web_url']))

    def edit_note(self):
        project = self.selected_project()
        if project:
            note, accepted = QInputDialog.getMultiLineText(self, 'Edit historical reference note', 'Note:', project['note'])
            if accepted:
                self.run(lambda: self.settings.edit_note(project['legacy_project_id'], note))
                self.reload()


class FolderMappingsPanel(AsyncPanel):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.fields = {}
        layout = QVBoxLayout(self)
        layout.addWidget(SectionHeader('Project folder mappings', 'Portable paths inside the project library. Saving a mapping leaves existing files in place.'))
        form = QFormLayout()
        for name, default in FOLDERS.items():
            row = QHBoxLayout()
            field = QLineEdit(settings.store.project.get('project_folders', {}).get(name, default))
            self.fields[name] = field
            row.addWidget(field)
            row.addWidget(Button('Browse', lambda checked=False, n=name: self.browse(n)))
            row.addWidget(Button('Reset', lambda checked=False, n=name, d=default: self.fields[n].setText(d)))
            row.addWidget(Button('Open', lambda checked=False, n=name: self.open_folder(n)))
            form.addRow(name, row)
        layout.addLayout(form)
        layout.addWidget(Button('Save folder mappings', lambda: self.run(lambda: settings.save_folders({k: f.text() for k, f in self.fields.items()}))))
        layout.addWidget(self.error)
        layout.addWidget(self.status)

    def browse(self, name):
        provider = self.settings.store.provider
        if not provider:
            self.error.show_error('Local storage needed', 'Connect your locally synced project folder first.')
            return
        chosen = QFileDialog.getExistingDirectory(self, 'Select ' + name, str(provider.root))
        if chosen:
            try:
                self.fields[name].setText(Path(chosen).resolve().relative_to(provider.root).as_posix())
            except ValueError:
                self.error.show_error('Folder outside project', 'Choose a folder inside the connected project library.')

    def open_folder(self, name):
        provider = self.settings.store.provider
        self.run(lambda: provider.open_folder(self.fields[name].text()) if provider else (_ for _ in ()).throw(ValueError('Connect local storage first.')))
