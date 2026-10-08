"""Bounded local diagnostics without credentials or exception payloads."""

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler


def configure(directory):
    folder = directory / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gdlhub")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            folder / "application.log",
            maxBytes=1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.info("Application startup")

    def unexpected(kind, value, tb):
        frames = "; ".join(
            f"{frame.name}:{frame.lineno}" for frame in traceback.extract_tb(tb)[-20:]
        )
        logger.error("Unhandled %s at %s", kind.__name__, frames)
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(
            QMessageBox.Critical,
            "GDL Research Hub Error",
            "GDL Research Hub encountered an error. Your research files were preserved.",
        )
        logs = box.addButton("Open Log Folder", QMessageBox.ActionRole)
        box.addButton("Close", QMessageBox.AcceptRole)
        box.setDetailedText(kind.__name__ + "\n" + frames)
        box.exec()
        if box.clickedButton() == logs:
            from app.services.file_launcher import open_folder

            open_folder(folder)

    sys.excepthook = unexpected
    return logger
