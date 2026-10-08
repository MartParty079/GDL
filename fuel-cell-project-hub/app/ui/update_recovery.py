"""Local recovery of unapplied settings and editor drafts during an update."""
import json
import uuid
from PySide6.QtCore import QObject, QEvent, QDate
from PySide6.QtWidgets import QDialog, QLineEdit, QTextEdit, QComboBox, QCheckBox, QSpinBox, QDateEdit, QTableWidget, QTableWidgetItem
from app.services.storage import read_json, write_json

TYPES = (QLineEdit, QTextEdit, QComboBox, QCheckBox, QSpinBox, QDateEdit, QTableWidget)


def capture(root):
    values = []
    for widget in root.findChildren(QObject):
        if isinstance(widget, QLineEdit) and widget.echoMode() != QLineEdit.Normal:
            continue
        if isinstance(widget, QTableWidget):
            value = [[widget.item(r, c).text() if widget.item(r, c) else '' for c in range(widget.columnCount())] for r in range(widget.rowCount())]
        elif isinstance(widget, QTextEdit): value = widget.toPlainText()
        elif isinstance(widget, QLineEdit): value = widget.text()
        elif isinstance(widget, QComboBox): value = widget.currentText()
        elif isinstance(widget, QCheckBox): value = widget.isChecked()
        elif isinstance(widget, QSpinBox): value = widget.value()
        elif isinstance(widget, QDateEdit): value = widget.date().toString('yyyy-MM-dd')
        else: continue
        values.append((widget.metaObject().className(), value))
    return values


def restore(root, values):
    widgets = [w for w in root.findChildren(QObject) if isinstance(w, TYPES) and not (isinstance(w, QLineEdit) and w.echoMode() != QLineEdit.Normal)]
    # A changed editor topology keeps the recovery file for manual recovery.
    if len(widgets) != len(values) or any(w.metaObject().className() != row[0] for w, row in zip(widgets, values)):
        return False
    for widget, (_, value) in zip(widgets, values):
        widget.blockSignals(True)
        try:
            if isinstance(widget, QTableWidget):
                widget.setRowCount(len(value))
                for r, row in enumerate(value):
                    for c, text in enumerate(row):
                        if not widget.cellWidget(r,c): widget.setItem(r,c,QTableWidgetItem(text))
            elif isinstance(widget, QTextEdit): widget.setPlainText(value)
            elif isinstance(widget, QLineEdit): widget.setText(value)
            elif isinstance(widget, QComboBox):
                index=widget.findText(value)
                if index >= 0: widget.setCurrentIndex(index)
                elif widget.isEditable(): widget.setEditText(value)
            elif isinstance(widget, QCheckBox): widget.setChecked(value)
            elif isinstance(widget, QSpinBox): widget.setValue(value)
            elif isinstance(widget, QDateEdit): widget.setDate(QDate.fromString(value,'yyyy-MM-dd'))
        finally: widget.blockSignals(False)
    return True


class UpdateRecovery(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        store = window.store
        install_id = store.local.setdefault('install_id', uuid.uuid4().hex)
        self.path = store.project_data('metadata/drafts/' + install_id + '.json') if store.shared_index else store.local_dir / 'update-drafts.local.json'
        try: self.rows = read_json(self.path, {})
        except ValueError: self.rows = {}
        window.installEventFilter(self)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def key(self, dialog):
        account = getattr(self.window.store, 'accounts', None)
        user = (getattr(account,'profile',None) or {}).get('id','local')
        identity = getattr(dialog,'row',None) or getattr(dialog,'obj',None) or {}
        ids = [r.get('id','') for r in getattr(dialog,'rows',[])]
        return json.dumps([user,type(dialog).__name__,getattr(dialog,'kind',''),identity.get('id','new'),ids])

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Show and isinstance(watched,QDialog) and self.window.isAncestorOf(watched):
            key=self.key(watched)
            if key in self.rows and restore(watched,self.rows[key]['widgets']):
                self.rows.pop(key)
                write_json(self.path,self.rows)
        return False

    def save(self):
        self.rows['settings'] = {key: field.toPlainText() if isinstance(field,QTextEdit) else field.text() for key,field in self.window.fields.items()}
        self.rows['lifecycle'] = {key: field.currentText() for key,field in self.window.lifecycle_fields.items()}
        for name in ('research_panel','gdl_settings'):
            root=getattr(self.window,name,None)
            if root is not None:self.rows[name]=capture(root)
        for dialog in self.window.findChildren(QDialog):
            if dialog.isVisible() and hasattr(dialog,'fields'):
                self.rows[self.key(dialog)]={'widgets':capture(dialog)}
        write_json(self.path,self.rows)

    def restore_settings(self):
        for name in ('research_panel','gdl_settings'):
            root=getattr(self.window,name,None)
            if root is not None and name in self.rows and restore(root,self.rows[name]):self.rows.pop(name)
        for key,value in self.rows.get('settings',{}).items():
            field=self.window.fields.get(key)
            if field is not None:
                field.setPlainText(value) if isinstance(field,QTextEdit) else field.setText(value)
        for key,value in self.rows.get('lifecycle',{}).items():
            field=self.window.lifecycle_fields.get(key)
            if field is not None:field.setCurrentText(value)
        self.rows.pop('settings',None);self.rows.pop('lifecycle',None)
        if self.path.exists():write_json(self.path,self.rows)
