"""Desktop icon and Windows taskbar identity shared by startup and windows."""
import os
from PySide6.QtGui import QIcon
from app.services.resources import resource_path

APP_ID = 'FuelCellProjectHub.Desktop'


def application_icon():
    return QIcon(str(resource_path('assets/app_icon.ico')))


def set_taskbar_identity():
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
