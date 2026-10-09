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
    owns_application = QApplication.instance() is None
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(PROFILE_NAME)
    app.setOrganizationName("FuelCellCapstone")
    app.setWindowIcon(application_icon())
    try:
        from app.services.local_accounts import LocalAccounts as Accounts
        from app.ui.local_accounts import LoginDialog, attach_account_ui

        store = Store()
        from PySide6.QtCore import QLockFile
        instance_lock = QLockFile(str(store.local_dir / 'application.lock'))
        if not instance_lock.tryLock(0):
            QMessageBox.information(None, APP_NAME, 'This edition is already open. Return to its workspace.')
            return 0
        from app.services.diagnostics import configure

        configure(store.local_dir / 'cache' if BETA else store.local_dir)
        from app.ui.update_installation import pending_update_at_startup
        if pending_update_at_startup(store):return 0
        accounts = Accounts(store)
        app.setQuitOnLastWindowClosed(False)
        windows = []
        active_login = [None]

        def login():
            dialog = LoginDialog(accounts)
            active_login[0] = dialog
            windows.append(dialog)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                app.quit()
                return
            store.accounts = accounts
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
                if hasattr(window, 'startup_reconciliation'):
                    window.startup_reconciliation.stop()
                window.session_presence.stop()
                window.research_panel.watcher.stop()
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
                if accounts.admin_unlocked and window.storage_settings.catalog and window.isVisible()
                else None
            )
            window.startup_reconciliation.start(300)

        from PySide6.QtCore import QTimer

        app.aboutToQuit.connect(accounts.close)
        app.aboutToQuit.connect(instance_lock.unlock)
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
    result = app.exec()
    # Dispose our windows while Qt still exists, rather than relying on Python's
    # interpreter teardown order after a sign-out/login sequence.
    from PySide6.QtCore import QCoreApplication, QEvent
    for window in windows:
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    windows.clear()
    import gc
    gc.collect()
    if owns_application:
        app.shutdown()
    return result


if __name__ == "__main__":
    sys.exit(main())
