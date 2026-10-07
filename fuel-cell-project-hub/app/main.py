import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from app.services.storage import Store
from app.ui.window import HubWindow
from app.ui.components import friendly_error
from app.ui.branding import application_icon, set_taskbar_identity


def main():
    set_taskbar_identity()
    app = QApplication(sys.argv)
    app.setApplicationName("FuelCellProjectHub")
    app.setOrganizationName("FuelCellCapstone")
    app.setWindowIcon(application_icon())
    try:
        window = HubWindow(Store())
    except Exception as exc:
        box = QMessageBox(QMessageBox.Critical, "Hub could not start", friendly_error(exc))
        box.setInformativeText("Your existing files have been preserved. Check the app configuration or restore a valid version before retrying.")
        box.setDetailedText(str(exc))
        box.exec()
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
