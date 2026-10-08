"""Asynchronous login and administration. Database roles never come from UI input."""

import time
from urllib.parse import urlparse, parse_qs
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QInputDialog,
    QWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QMessageBox,
    QMenu,
)
from app import __version__
from app.ui.branding import application_icon
from app.ui.theme import apply_theme
from app.ui.research_viewers import Tasks
from app.services.accounts import AccountError, ConnectionUnavailable


class LoginDialog(QDialog):
    def __init__(self, accounts):
        super().__init__()
        self.accounts = accounts
        self.setWindowTitle("GDL Research Hub — Sign in")
        self.setWindowIcon(application_icon())
        self.setMinimumWidth(430)
        self.tasks = Tasks(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        logo = QLabel()
        logo.setPixmap(application_icon().pixmap(64, 64))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)
        title = QLabel("GDL Research Hub")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:24px;font-weight:600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Sign in with your research team account."))
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password")
        form = QFormLayout()
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        layout.addLayout(form)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.signin = QPushButton("Sign In")
        self.signin.clicked.connect(self.sign_in)
        self.password.returnPressed.connect(self.sign_in)
        layout.addWidget(self.signin)
        reset = QPushButton("Forgot Password")
        reset.clicked.connect(self.reset)
        layout.addWidget(reset)
        invite = QPushButton("Use Invitation / Reset Link")
        invite.clicked.connect(self.redeem)
        layout.addWidget(invite)
        self.controls = [self.signin, reset, invite]
        layout.addWidget(QLabel("v" + __version__))
        apply_theme(self)
        QTimer.singleShot(0, self.restore)

    def run(self, action, done):
        if self.tasks.busy():
            return
        for control in self.controls:
            control.setEnabled(False)
        self.status.setText("Connecting…")
        self.tasks.start(
            action, lambda result: self.done_action(result, done), self.failed
        )

    def done_action(self, result, done):
        for control in self.controls:
            control.setEnabled(True)
        self.status.clear()
        done(result)

    def failed(self, message):
        for control in self.controls:
            control.setEnabled(True)
        # Tasks emits text; only our controlled AccountError messages are used.
        safe = (
            "Unable to connect",
            "This GDL",
            "This account",
            "Too many",
            "Access unavailable",
            "Unable to complete",
            "Use a password",
            "Connect to the account",
            "Saved sign-in",
        )
        self.status.setText(
            message
            if message.startswith(safe)
            else "Unable to sign in. Check your email and password, then try again."
        )

    def restore(self):
        self.run(
            self.accounts.restore, lambda profile: self.accept() if profile else None
        )

    def sign_in(self):
        if not self.signin.isEnabled():
            return
        email, password = self.email.text(), self.password.text()
        self.password.clear()
        self.run(
            lambda: self.accounts.sign_in(email, password), lambda _: self.accept()
        )

    def reset(self):
        if not self.email.text().strip():
            self.status.setText("Enter your email first.")
            return
        email = self.email.text()
        self.run(
            lambda: self.accounts.reset_password(email),
            lambda _: self.status.setText(
                "If the account exists, a password reset email will arrive. Use its link here."
            ),
        )

    def redeem(self):
        link, ok = QInputDialog.getText(
            self,
            "Invitation or Password Reset",
            "Paste the link from your account email:",
        )
        if not ok or not link:
            return
        parsed = urlparse(link.strip())
        query = parse_qs(parsed.query)
        if (
            parsed.scheme != "https"
            or parsed.netloc != urlparse(self.accounts.url).netloc
            or parsed.path != "/auth/v1/verify"
        ):
            self.status.setText(
                "Use the original invitation or reset link from your account email."
            )
            return
        kind = query.get("type", [""])[0]
        token = query.get("token", query.get("token_hash", [""]))[0]
        if kind not in ("invite", "recovery") or not token:
            self.status.setText("This invitation or reset link is unavailable.")
            return
        password, ok = QInputDialog.getText(
            self,
            "Set Password",
            "New password (at least 12 characters):",
            QLineEdit.Password,
        )
        if not ok:
            return

        def action():
            self.accounts.session = self.accounts.request(
                "POST", "/auth/v1/verify", {"token_hash": token, "type": kind}, False
            )
            self.accounts.set_password(password)
            self.accounts.load_profile()
            self.accounts.register()
            self.accounts.event("LOGIN")

        self.run(action, lambda _: self.accept())

    def reject(self):
        if self.tasks.busy():
            self.status.setText("Finishing the account check. Please wait a moment.")
            return
        super().reject()


class AdminWorkspace(QWidget):
    def __init__(self, accounts, window):
        super().__init__(window)
        self.accounts, self.window = accounts, window
        self.tasks = Tasks(self)
        self.rows = []
        self.offset = 0
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tables = {}
        self.statuses = {}
        for title in ("Overview", "Users", "Activity", "Installations", "System"):
            page = QWidget()
            column = QVBoxLayout(page)
            status = QLabel("")
            status.setWordWrap(True)
            column.addWidget(status)
            self.statuses[title] = status
            if title != "System":
                table = QTableWidget()
                table.setEditTriggers(QTableWidget.NoEditTriggers)
                table.setSelectionBehavior(QTableWidget.SelectRows)
                column.addWidget(table)
                self.tables[title] = table
            self.tabs.addTab(page, title)
        self.filters = {}
        form = QHBoxLayout()
        for field, title in [
            ("user_id", "User ID"),
            ("event_type", "Event"),
            ("date_from", "Date from (YYYY-MM-DD)"),
            ("entity_type", "Entity type"),
            ("app_version", "Version"),
        ]:
            edit = QLineEdit()
            edit.setPlaceholderText(title)
            edit.returnPressed.connect(self.reload)
            self.filters[field] = edit
            form.addWidget(edit)
        layout.addLayout(form)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        for title, callback in [
            ("Refresh", self.reload),
            ("Previous", lambda: self.page(-100)),
            ("Next", lambda: self.page(100)),
            ("Invite User", self.invite),
            ("Enable / Disable", self.active),
            ("Change Role", self.role),
        ]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            actions.addWidget(button)
        self.tabs.currentChanged.connect(lambda _: self.reload(reset=True))
        self.reload()

    def page(self, delta):
        self.offset = max(0, self.offset + delta)
        self.reload(reset=False)

    def reload(self, reset=True):
        if self.tasks.busy():
            return
        if reset:
            self.offset = 0
        title = self.tabs.tabText(self.tabs.currentIndex())
        if title == "System":
            sources = "\n".join(
                x["name"] + ": " + x["status"]
                for x in self.window.storage_settings.locations.status()
            )
            self.statuses[title].setText(
                "Account service: "
                + ("Offline" if self.accounts.offline else "Connected")
                + "\nLocal index: "
                + (
                    "Ready"
                    if self.window.storage_settings.catalog
                    else "Not configured"
                )
                + "\n"
                + sources
                + "\nGitHub updates: "
                + getattr(self.window, "release_status_text", "Not checked")
            )
            return
        self.statuses[title].setText("Loading…")
        action = title.lower()
        filters = (
            {k: v.text().strip() for k, v in self.filters.items() if v.text().strip()}
            if title == "Activity"
            else {}
        )
        self.tasks.start(
            lambda: self.accounts.admin(action, offset=self.offset, **filters),
            lambda result: self.loaded(title, result),
            lambda _: self.statuses[title].setText(
                "Administrator information unavailable. Connect and try again."
            ),
        )

    def loaded(self, title, result):
        if title == "Overview":
            self.statuses[title].setText(
                f"Active users: {result['active_users']}   Logins (7 days): {result['logins_7_days']}   Recent installations: {result['recent_installations']}   Client version: {__version__}"
            )
            rows = result["recent"]
            keys = ["created_at", "user_id", "event_type", "entity_name", "app_version"]
        else:
            rows = result["rows"]
            self.statuses[title].setText(
                f"{result['count']} records · showing {self.offset+1 if rows else 0}–{self.offset+len(rows)}"
            )
            keys = {
                "Users": [
                    "display_name",
                    "email",
                    "role",
                    "active",
                    "last_login",
                    "last_activity",
                    "last_app_version",
                    "installations",
                ],
                "Activity": [
                    "created_at",
                    "user_id",
                    "event_type",
                    "entity_name",
                    "entity_type",
                    "app_version",
                    "install_id",
                ],
                "Installations": [
                    "label",
                    "user_id",
                    "platform",
                    "app_version",
                    "last_seen_at",
                    "install_id",
                ],
            }[title]
        table = self.tables[title]
        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels([x.replace("_", " ").title() for x in keys])
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                value = (
                    ("Active" if row.get("active") else "Disabled")
                    if key == "active"
                    else row.get(key)
                )
                item = QTableWidgetItem(str(value if value is not None else ""))
                item.setData(Qt.UserRole, row)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()
        if title == "Installations":
            latest = (
                getattr(self.window, "latest_release_info", {})
                .get("tag", __version__)
                .lstrip("v")
            )
            self.statuses[title].setText(
                self.statuses[title].text()
                + " · Latest stable/client: "
                + latest
                + " · Versions report last seen, not online presence."
            )

    def selected(self):
        if self.tabs.tabText(self.tabs.currentIndex()) != "Users":
            return None
        table = self.tables["Users"]
        item = table.item(table.currentRow(), 0)
        return item.data(Qt.UserRole) if item else None

    def change(self, action, **values):
        if self.tasks.busy():
            return

        def done(_):
            def refresh():
                if self.tasks.busy():
                    QTimer.singleShot(30, refresh)
                else:
                    self.reload()

            QTimer.singleShot(0, refresh)

        self.tasks.start(
            lambda: self.accounts.admin(action, **values),
            done,
            lambda _: QMessageBox.warning(
                self,
                "Account Change Unavailable",
                "Check your access. At least one active administrator must remain.",
            ),
        )

    def invite(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Invite User")
        layout = QFormLayout(dialog)
        email = QLineEdit()
        name = QLineEdit()
        layout.addRow("Email", email)
        layout.addRow("Display name", name)
        button = QPushButton("Send Invitation")
        button.clicked.connect(dialog.accept)
        layout.addRow(button)
        if dialog.exec() == QDialog.Accepted:
            self.change("invite", email=email.text(), display_name=name.text())

    def active(self):
        row = self.selected()
        if (
            row
            and QMessageBox.question(
                self, "Change Account Status", "Change access for " + row["email"] + "?"
            )
            == QMessageBox.Yes
        ):
            self.change("set_active", user_id=row["id"], active=not row["active"])

    def role(self):
        row = self.selected()
        if not row:
            return
        role, ok = QInputDialog.getItem(
            self,
            "Change Role",
            "Role for " + row["email"],
            ["USER", "ADMIN"],
            editable=False,
        )
        if (
            ok
            and QMessageBox.question(
                self,
                "Change Role",
                "Apply " + role + " access to " + row["email"] + "?",
            )
            == QMessageBox.Yes
        ):
            self.change("set_role", user_id=row["id"], role=role.lower())


def attach_account_ui(window, accounts, sign_out):
    window.account_service = accounts
    window.account_tasks = Tasks(window)
    button = QPushButton(window)
    window.centralWidget().layout().itemAt(0).layout().addWidget(button)
    menu = QMenu(button)
    button.setMenu(menu)

    def update_label():
        p = accounts.profile or {}
        button.setText(
            (p.get("display_name") or p.get("email", "Account"))
            + " · "
            + p.get("role", "").upper()
            + (" · OFFLINE" if accounts.offline else "")
        )
        if hasattr(window, "admin_workspace"):
            window.admin_workspace.setEnabled(not accounts.offline)

    update_label()

    def profile():
        p = accounts.profile
        QMessageBox.information(
            window,
            "Account",
            p["email"]
            + "\nRole: "
            + p["role"].upper()
            + "\nInstall ID: "
            + accounts.install_id
            + "\nActivity records meaningful Hub actions; file contents and full local paths stay local.",
        )

    menu.addAction("Profile / Account", profile)

    def label():
        value, ok = QInputDialog.getText(
            window,
            "Installation Label",
            "Friendly name:",
            text=window.store.local.get("installation_label", "Research workstation"),
        )
        if ok:
            window.store.local["installation_label"] = value[:80]
            window.store.save_local()
            window.account_tasks.start(
                accounts.register, lambda _: None, lambda _: None
            )

    menu.addAction("Installation Label", label)
    menu.addAction("Check for Updates", window.check_updates)
    from app.ui.research_workspace import version_dialog

    menu.addAction("About", lambda: version_dialog(window))
    menu.addAction("Sign Out", sign_out)
    if accounts.profile["role"] == "admin":
        window.admin_workspace = AdminWorkspace(accounts, window)
        window.tabs.addTab(window.admin_workspace, "Admin")

    def recheck():
        if window.account_tasks.busy():
            return

        def action():
            try:
                accounts.refresh()
                accounts.flush()
                return True
            except ConnectionUnavailable:
                if time.time() - accounts.validated_at > 86400:
                    raise AccountError("Connect to sign in again.")
                accounts.offline = True
                return False

        def failed(message):
            # Revoke local UI access immediately, then wait for the worker's
            # finished signal before requesting logout/disposing its parent.
            window.setEnabled(False)
            window.account_timer.stop()

            def finish():
                if window.account_tasks.busy():
                    QTimer.singleShot(30, finish)
                    return
                QMessageBox.information(
                    window,
                    "Account Access Unavailable",
                    (
                        message
                        if message.startswith(("This GDL", "Connect to"))
                        else "Please sign in again. Your research data is preserved."
                    ),
                )
                sign_out()

            QTimer.singleShot(0, finish)

        window.account_tasks.start(action, lambda _: update_label(), failed)

    window.account_timer = QTimer(window)
    window.account_timer.timeout.connect(recheck)
    window.account_timer.start(300000)
