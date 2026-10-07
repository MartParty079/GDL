"""Portable local project folder mappings, independent of cloud authentication."""
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit, QFileDialog
from app.services.storage_settings import FOLDERS
from app.services.project_storage import normalized_relative
from app.services.software import open_resource
from app.ui.components import Button, SectionHeader, ErrorBanner, InlineMessage


class FolderMappingsPanel(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings, self.fields = settings, {}
        layout = QVBoxLayout(self)
        layout.addWidget(SectionHeader('Project folder mappings', 'Relative paths inside the active project. Saving leaves existing files in place.'))
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
        layout.addWidget(Button('Save folder mappings', self.save))
        self.error, self.status = ErrorBanner(), InlineMessage()
        layout.addWidget(self.error); layout.addWidget(self.status)

    def root(self):
        return Path(self.settings.locations.value['active']['root_path']) if self.settings.locations.value.get('enabled') else self.settings.store.provider.root if self.settings.store.provider else None

    def browse(self, name):
        root = self.root()
        if root is None:
            self.error.show_error('Local storage needed', 'Save a research root or connect a shared library first.')
            return
        chosen = QFileDialog.getExistingDirectory(self, 'Select ' + name, str(root))
        if chosen:
            try:
                self.fields[name].setText(Path(chosen).resolve().relative_to(root.resolve()).as_posix())
            except ValueError:
                self.error.show_error('Folder outside project', 'Choose a folder inside the active project.')

    def open_folder(self, name):
        try:
            root = self.root()
            if root is None:
                raise ValueError('Configure local storage first.')
            path = (root / normalized_relative(self.fields[name].text())).resolve()
            path.relative_to(root.resolve())
            if not path.is_dir():
                raise ValueError('The mapped folder is currently unavailable.')
            open_resource(str(path))
        except (OSError, ValueError) as exc:
            self.error.show_error('Folder unavailable', exc)

    def save(self):
        try:
            self.settings.save_folders({k: f.text() for k, f in self.fields.items()})
            self.status.set_message('Mappings saved; research files remain in place.', 'success')
        except (OSError, ValueError) as exc:
            self.error.show_error('Mappings unavailable', exc)
