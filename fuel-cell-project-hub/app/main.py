from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from app.services.storage import Store
from app.ui.window import HubWindow
from app.ui.components import friendly_error
from app.ui.branding import application_icon, set_taskbar_identity
from app.edition import APP_NAME, PROFILE_NAME, PROTOCOL, BETA


def main():
    set_taskbar_identity()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(PROFILE_NAME)
    app.setOrganizationName("FuelCellCapstone")
    app.setWindowIcon(application_icon())
    try:
        from app.services.accounts import Accounts
        from app.ui.accounts import LoginDialog, attach_account_ui

        store = Store()
        from app.services.desktop_oauth import CallbackBroker

        broker = CallbackBroker(store.local_dir, app)
        callback = next(
            (value for value in sys.argv[1:] if value.startswith(PROTOCOL + ":")),
            None,
        )
        if callback and broker.forward(callback):
            return 0
        if not broker.listen():
            QMessageBox.information(
                None,
                "GDL Research Hub",
                "GDL Research Hub is already open. Return to its window to sign in.",
            )
            return 0
        from app.services.diagnostics import configure

        configure(store.local_dir / 'cache' if BETA else store.local_dir)
        from app.ui.update_installation import pending_update_at_startup
        if pending_update_at_startup(store):return 0
        if store.shared_required:
            from app.ui.shared_project_setup import connect_shared_project
            if not connect_shared_project(store):
                broker.server.close()
                return 0
            from PySide6.QtWidgets import QProgressDialog
            progress = QProgressDialog('Verifying the shared project index. Research files will not be scanned.', '', 0, 0)
            progress.setCancelButton(None)
            progress.show()
            app.processEvents()
            try:
                store.shared_index.load()
            finally:
                progress.close()
        try:accounts = Accounts(store)
        except ValueError:
            if not BETA:raise
            # No production endpoint or role is inherited by offline Beta.
            window=HubWindow(store)
            authority = 'Configured indexing authority' if store.shared_index.authority else 'Published index reader'
            window.banner.setText('BETA · Shared OneDrive project · ' + authority + ' · Backend unconfigured · No backend administrator privileges')
            window.show();app.aboutToQuit.connect(broker.server.close)
            return app.exec()
        app.setQuitOnLastWindowClosed(False)
        windows = []
        active_login = [None]

        def receive_callback(uri):
            if active_login[0] is not None and active_login[0].isVisible():
                active_login[0].microsoft_return(uri)

        broker.received.connect(receive_callback)

        def login():
            dialog = LoginDialog(accounts)
            active_login[0] = dialog
            windows.append(dialog)
            if callback:
                QTimer.singleShot(100, lambda: receive_callback(callback))
            if dialog.exec() != QDialog.DialogCode.Accepted:
                app.quit()
                return
            from app.services.project_locations import ProjectLocations
            from PySide6.QtWidgets import QFileDialog

            locations = ProjectLocations(store)
            if not locations.value.get("enabled"):
                value = locations.value
                folder = Path(value["active"]["root_path"])
                if not folder.is_dir():
                    selected = QFileDialog.getExistingDirectory(
                        dialog, "Locate Research Folder"
                    )
                    if selected:
                        value["active"]["root_path"] = selected
                        value["shared_storage"] = selected
                        folder = Path(selected)
                if folder.is_dir():
                    locations.save(value)
            try:
                window = HubWindow(store)
            except Exception:
                QMessageBox.critical(
                    dialog,
                    "Workspace Unavailable",
                    "The research workspace could not open. Your index and research files were preserved. Check the local log folder.",
                )
                app.exit(1)
                return
            active_login[0] = None
            windows.append(window)

            def sign_out():
                from PySide6.QtCore import QTimer

                if getattr(window, "signout_pending", False):
                    return
                window.signout_pending = True
                window.setEnabled(False)
                window.account_timer.stop()
                window.session_presence.stop()
                window.storage_panel.cancel_index()
                window.research_panel.cancel_index()

                def wait_for_work():
                    busy = (
                        window.workers
                        or window.research_panel.indexing
                        or window.storage_panel.indexing
                        or window.research_workspace.busy()
                        or window.account_tasks.busy()
                        or window.meetings_panel.busy()
                        or window.weekly_panel.tasks.busy()
                        or (
                            hasattr(window, "admin_workspace")
                            and window.admin_workspace.tasks.busy()
                        )
                    )
                    if busy:
                        window.banner.setText(
                            "Finishing background work before signing out."
                        )
                        QTimer.singleShot(100, wait_for_work)
                        return

                    def finished(_):
                        def close_and_login():
                            if window.account_tasks.busy():
                                QTimer.singleShot(30, close_and_login)
                                return
                            window.signing_out = True
                            window.close()
                            login()

                        QTimer.singleShot(0, close_and_login)

                    window.account_tasks.start(accounts.sign_out, finished, finished)

                wait_for_work()

            attach_account_ui(window, accounts, sign_out)
            store.accounts = accounts
            window.show()
            window.research_workspace.navigate("Overview")
            # Reconcile changes after showing the workspace, using its existing
            # cancellable worker. Never block login on a full content rebuild.
            window.startup_reconciliation = QTimer(window)
            window.startup_reconciliation.setSingleShot(True)
            window.startup_reconciliation.timeout.connect(
                lambda: window.research_panel.start_index(quick=True)
                if window.storage_settings.catalog and window.isVisible()
                else None
            )
            window.startup_reconciliation.start(300)

        from PySide6.QtCore import QTimer

        app.aboutToQuit.connect(
            lambda: accounts.executor.shutdown(wait=False, cancel_futures=True)
        )
        app.aboutToQuit.connect(broker.server.close)
        QTimer.singleShot(0, login)
    except Exception as exc:
        box = QMessageBox(
            QMessageBox.Critical, "Hub could not start", friendly_error(exc)
        )
        box.setInformativeText(
            "Your existing files have been preserved. Check the app configuration or restore a valid version before retrying."
        )
        box.setDetailedText(str(exc))
        box.exec()
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
