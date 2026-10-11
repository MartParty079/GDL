"""Local appearance choices; no shared configuration or data migration."""
from PySide6.QtWidgets import QGroupBox, QFormLayout, QComboBox, QCheckBox, QPushButton, QLabel


def appearance_controls(window, parent):
    group = QGroupBox('Appearance & Accessibility', parent); form = QFormLayout(group)
    appearance = QComboBox(); appearance.setAccessibleName('Appearance')
    for name, value in (('Follow Windows', 'system'), ('Light', 'light'), ('Dark', 'dark')): appearance.addItem(name, value)
    appearance.setCurrentIndex(max(0, appearance.findData(window.store.local.get('appearance', 'system'))))
    scale = QComboBox(); scale.setAccessibleName('Text size')
    for value in (100, 125, 150, 200): scale.addItem(str(value) + '%', value)
    scale.setCurrentIndex(max(0, scale.findData(window.store.local.get('text_scale', 100))))
    form.addRow('Appearance', appearance); form.addRow('Text size', scale)
    hint = QLabel('Windows high contrast takes priority. Navigation and filtering use immediate feedback with no movement animations.')
    hint.setWordWrap(True); form.addRow(hint)
    apply = QPushButton('Apply Appearance')
    def save():
        window.store.local.update(appearance=appearance.currentData(), text_scale=scale.currentData())
        window.store.save_local(); window.apply_theme(); window.home_panel.reload()
        apply.setText('Appearance Saved')
    apply.clicked.connect(save); form.addRow(apply)
    return group
