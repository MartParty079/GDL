import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from app.services.storage import Store
from app.ui.window import HubWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("FuelCellProjectHub")
    app.setOrganizationName("FuelCellCapstone")
    try:
        window = HubWindow(Store())
    except Exception as exc:
        QMessageBox.critical(None, "Hub could not start", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
