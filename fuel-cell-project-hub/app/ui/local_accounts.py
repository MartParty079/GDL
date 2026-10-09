"""Offline profile selection, PIN management and measurable team activity."""
from datetime import datetime, timezone
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QCheckBox, QMessageBox, QInputDialog, QWidget, QTableWidget,
    QTableWidgetItem, QDateEdit, QMenu, QApplication)
from app.edition import APP_NAME, CHANNEL
from app.ui.theme import apply_theme
from app.ui.research_viewers import Tasks


class LoginDialog(QDialog):
    def __init__(self, accounts):
        super().__init__()
        self.accounts = accounts
        self.setWindowTitle(APP_NAME + ' · Select user')
        self.setMinimumWidth(460)
        apply_theme(self)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(APP_NAME + '\nSelect your team profile. OneDrive controls research file access.'))
        self.person = QComboBox()
        for user in accounts.users():
            self.person.addItem(user['display_name'] + ' · ' + user['role'].title(), user['id'])
        selected = self.person.findData(accounts.store.local.get('selected_user'))
        if selected >= 0:
            self.person.setCurrentIndex(selected)
        layout.addWidget(self.person)
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setMaxLength(6)
        self.pin.setPlaceholderText('PIN, if configured (Admin required)')
        layout.addWidget(self.pin)
        self.remember = QCheckBox('Remember selected user'); self.remember.setChecked(True)
        self.automatic = QCheckBox('Sign in automatically (Members without a PIN only)')
        layout.addWidget(self.remember); layout.addWidget(self.automatic)
        self.status = QLabel(accounts.warning); self.status.setWordWrap(True); layout.addWidget(self.status)
        login = QPushButton('Open workspace'); login.clicked.connect(self.sign_in); layout.addWidget(login)
        self.pin.returnPressed.connect(self.sign_in)
        self.setup = QPushButton('Set up Admin PIN'); self.setup.clicked.connect(self.setup_admin)
        self.setup.setVisible(not any(p['role'] == 'admin' and p['pin'] for p in accounts.registry['users']))
        layout.addWidget(self.setup)
        recovery = QPushButton('Recover Admin PIN'); recovery.clicked.connect(self.recover); layout.addWidget(recovery)
        if accounts.store.local.get('automatic_user'):
            QTimer.singleShot(0, self.restore)

    def restore(self):
        try:
            if self.accounts.restore():
                self.accept()
        except ValueError as exc:
            self.status.setText(str(exc))

    def sign_in(self):
        try:
            self.accounts.sign_in(self.person.currentData(), self.pin.text(), self.remember.isChecked(), self.automatic.isChecked())
            self.pin.clear()
            self.accept()
        except (ValueError, OSError) as exc:
            self.pin.clear(); self.status.setText(str(exc) if isinstance(exc, ValueError) else 'Profiles could not be saved. Check storage access and retry.')

    def new_pin(self):
        pin, ok = QInputDialog.getText(self, 'Admin PIN', 'Choose four to six digits:', QLineEdit.Password)
        if not ok:
            return None
        confirmation, ok = QInputDialog.getText(self, 'Confirm PIN', 'Enter the PIN again:', QLineEdit.Password)
        if not ok or pin != confirmation:
            self.status.setText('PIN confirmation did not match.'); return None
        return pin

    def show_recovery(self, code):
        box = QMessageBox(self); box.setWindowTitle('Save Admin recovery code')
        box.setText('Store this code privately. It is shown once and replaces any previous code.\n\n' + code)
        box.setTextInteractionFlags(Qt.TextSelectableByMouse); box.exec()
        self.setup.hide(); self.status.setText('Admin PIN saved. Select Matthew Kime and sign in with the PIN.')

    def setup_admin(self):
        pin = self.new_pin()
        if pin is None:
            return
        try:
            self.show_recovery(self.accounts.setup_admin(pin))
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc) if isinstance(exc, ValueError) else 'Admin setup could not save. Retry after checking OneDrive.')

    def recover(self):
        code, ok = QInputDialog.getText(self, 'Admin recovery', 'Private recovery code:', QLineEdit.Password)
        if not ok:
            return
        pin = self.new_pin()
        if pin is None:
            return
        try:
            self.show_recovery(self.accounts.recover_admin(code, pin))
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc) if isinstance(exc, ValueError) else 'Recovery could not save. Existing profiles were preserved.')


class ActivityPanel(QWidget):
    def __init__(self, accounts, window):
        super().__init__(window)
        self.accounts = accounts
        self.tasks = Tasks(self)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout(); layout.addLayout(bar)
        self.person = QComboBox()
        if accounts.admin_unlocked:
            self.person.addItem('All team members', '')
        for person in (accounts.registry['users'] if accounts.admin_unlocked else [accounts.profile]):
            self.person.addItem(person['display_name'], person['id'])
        bar.addWidget(self.person)
        self.category = QLineEdit(); self.category.setPlaceholderText('Category / action filter'); bar.addWidget(self.category)
        self.begin = QDateEdit(); self.begin.setCalendarPopup(True); self.begin.setDate(datetime.now().date().replace(day=1))
        self.end = QDateEdit(); self.end.setCalendarPopup(True); self.end.setDate(datetime.now().date())
        bar.addWidget(self.begin); bar.addWidget(self.end)
        refresh = QPushButton('Refresh'); refresh.clicked.connect(lambda: self.guard(lambda: None)); bar.addWidget(refresh)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.table = QTableWidget(0, 6); self.table.setHorizontalHeaderLabels(['UTC', 'User', 'Action', 'Entity', 'Status', 'Event ID'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.table)
        self.table.cellDoubleClicked.connect(self.inspect)
        if accounts.admin_unlocked:
            controls = QHBoxLayout(); layout.addLayout(controls)
            for title, action in [('Add Member', self.add), ('Rename', self.rename), ('Deactivate', self.deactivate), ('Reactivate', self.reactivate), ('Reset Member PIN', self.reset_pin), ('Preserved hosted history', self.legacy)]:
                button = QPushButton(title); button.clicked.connect(lambda checked=False, fn=action: self.guard(fn)); controls.addWidget(button)
        self.guard(lambda: None)

    def guard(self, fn):
        try:
            fn(); self.refresh()
        except Exception as exc:
            self.status.setText(str(exc) if isinstance(exc, ValueError) else 'Shared storage could not save this change. Existing data was preserved.')

    def chosen(self):
        identity = self.person.currentData()
        if not identity:
            raise ValueError('Select one team member first.')
        return identity

    def add(self):
        name, ok = QInputDialog.getText(self, 'Add Member', 'Display name:')
        if ok:
            self.accounts.manage_user(name=name)
            p = self.accounts.registry['users'][-1]; self.person.addItem(p['display_name'], p['id'])

    def rename(self):
        identity = self.chosen()
        name, ok = QInputDialog.getText(self, 'Rename profile', 'Display name:', text=self.accounts.find(identity)['display_name'])
        if ok:
            self.accounts.manage_user(identity, name=name); self.person.setItemText(self.person.currentIndex(), name)

    def deactivate(self):
        identity = self.chosen()
        if QMessageBox.question(self, 'Deactivate profile?', 'Existing activity remains associated with this permanent user ID.') == QMessageBox.Yes:
            self.accounts.manage_user(identity, active=False)

    def reset_pin(self):
        identity = self.chosen()
        if QMessageBox.question(self, 'Reset Member PIN?', 'This removes the Member PIN. They can choose a new PIN on the designated profile writer.') == QMessageBox.Yes:
            self.accounts.manage_user(identity, reset_pin=True)

    def reactivate(self):
        self.accounts.manage_user(self.chosen(), active=True)

    def legacy(self):
        self.accounts.require_admin()
        from app.services.storage import read_json
        import json, sqlite3
        from contextlib import closing
        from PySide6.QtWidgets import QTextEdit
        records = {'notice':'Preserved local hosted-account records. Original user IDs are retained; these are excluded from local team metrics. Remote records remain in the original project.'}
        for name in ('pending_activity.local.json', 'pending_sessions.local.json'):
            path = self.accounts.store.local_dir / name
            if path.exists():
                records[name] = read_json(path, {})
        for relative in ('meetings.local.sqlite3', 'cache/meetings.sqlite3'):
            path = self.accounts.store.local_dir / relative
            if path.is_file():
                with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                    records[relative] = [dict(user_id=r[0], id=r[1], record=json.loads(r[2]))
                        for r in db.execute('SELECT user_id,id,payload FROM meeting_cache')
                        if self.accounts.find(r[0]) is None]
        dialog = QDialog(self); dialog.setWindowTitle('Preserved hosted history · read only')
        layout = QVBoxLayout(dialog); text = QTextEdit(); text.setReadOnly(True)
        text.setPlainText(json.dumps(records, indent=2)); layout.addWidget(text)
        dialog.resize(850, 650); dialog.exec()

    def refresh(self):
        from app.services.contributions import WeeklyReports
        from datetime import timedelta
        begin = datetime.combine(self.begin.date().toPython(), datetime.min.time(), timezone.utc)
        end = datetime.combine(self.end.date().toPython() + timedelta(days=1), datetime.min.time(), timezone.utc)
        roster = self.accounts.registry['users'] if self.accounts.admin_unlocked else [self.accounts.profile]
        people = [p for p in roster if not self.person.currentData() or p['id'] == self.person.currentData()]
        reports = [WeeklyReports(self.accounts).load(p, begin, end) for p in people]
        self.rows = [e for r in reports for e in r['events'] if self.category.text().strip().upper() in e['event_type']]
        self.rows.sort(key=lambda e: e['created_at'], reverse=True)
        names = {p['id']: p['display_name'] for p in self.accounts.registry['users']}
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            for j, value in enumerate((row['created_at'], names.get(row['user_id'], row['user_id']), row['event_type'], row.get('entity_name', ''), row['status'], row['id'])):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        totals = '\n'.join(r['person'] + ': ' + ', '.join(f'{k}: {r["metrics"][k]}' for k in ('Logins', 'Sessions', 'Active time', 'Files added (known attribution)', 'Experiments updated', 'Samples updated', 'Procedure revisions')) for r in reports)
        self.status.setText(totals + '\n' + (self.accounts.warning or 'Shared events synchronized when OneDrive is available. Active time is an estimate of focused Hub use.'))

    def inspect(self, row, column):
        import json
        box = QMessageBox(self); box.setWindowTitle('Recorded activity'); box.setText(json.dumps(self.rows[row], indent=2)); box.exec()


def attach_account_ui(window, accounts, sign_out):
    from app.ui.participation import SessionPresence, MeetingsPanel, WeeklyPanel
    window.account_service = accounts
    window.account_tasks = Tasks(window)
    window.session_presence = SessionPresence(window, accounts)
    window.meetings_panel = MeetingsPanel(window, accounts)
    window.weekly_panel = WeeklyPanel(window, accounts)
    window.tabs.addTab(window.meetings_panel, 'Meetings')
    window.tabs.addTab(window.weekly_panel, 'Weekly Activity')
    panel = ActivityPanel(accounts, window)
    window.tabs.addTab(panel, 'Admin · User Activity' if accounts.admin_unlocked else 'My Activity')
    if accounts.admin_unlocked:
        window.admin_workspace = panel
    else:
        # Administrative storage/indexing controls are excluded from Member UI.
        window.tabs.setTabVisible(list(window.pages).index('Settings'), False)
        window.gdl_settings.setEnabled(False)
        window.research_panel.setEnabled(False)
        window.storage_panel.setEnabled(False)
    button = QPushButton(accounts.profile['display_name'] + ' · ' + accounts.profile['role'].upper(), window)
    button.setObjectName('current-user')
    window.centralWidget().layout().itemAt(0).layout().addWidget(button)
    menu = QMenu(button); button.setMenu(menu)

    def change_pin():
        old, ok = QInputDialog.getText(window, 'Change PIN', 'Current PIN (blank if none):', QLineEdit.Password)
        if not ok:
            return
        new, ok = QInputDialog.getText(window, 'Change PIN', 'New four to six digits (Members may leave blank):', QLineEdit.Password)
        if not ok:
            return
        confirm, ok = QInputDialog.getText(window, 'Confirm PIN', 'Enter new PIN again:', QLineEdit.Password)
        if not ok or confirm != new:
            return
        try:
            accounts.change_pin(old, new); QMessageBox.information(window, 'PIN', 'PIN saved.')
        except (ValueError, OSError) as exc:
            QMessageBox.information(window, 'PIN unavailable', str(exc) if isinstance(exc, ValueError) else 'Storage unavailable. Existing PIN was preserved.')

    menu.addAction('Change my PIN', change_pin)
    menu.addAction('Check for Updates', window.check_updates)
    menu.addAction('Switch User / Sign Out', sign_out)
    window.account_timer = QTimer(window)
    def refresh():
        try:
            accounts.refresh()
            button.setText(accounts.profile['display_name'] + ' · ' + accounts.profile['role'].upper())
            accounts.executor.submit(accounts.flush)
        except ValueError as exc:
            window.banner.setText(str(exc)); sign_out()
    window.account_timer.timeout.connect(refresh); window.account_timer.start(60_000)
    window.banner.setText(CHANNEL.upper() + ' · Local team profiles · ' + (accounts.warning or 'OneDrive controls file access'))
