"""Shared design tokens and Qt stylesheet for all Hub surfaces."""
import os
import re
import ctypes
from types import SimpleNamespace
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QPalette, QColor
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTextBrowser, QTableView


class Theme:
    BACKGROUND_PRIMARY = "#F5F6F8"
    BACKGROUND_SECONDARY = "#FFFFFF"
    BACKGROUND_TERTIARY = "#F1F3F6"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#5F6B7A"
    TEXT_MUTED = "#667181"
    TEXT_DISABLED = "#8A94A3"
    ACCENT_PRIMARY = "#0A84FF"
    ACCENT_BUTTON = "#0071E3"
    ACCENT_HOVER = "#0062C4"
    ACCENT_BUTTON_HOVER = "#0062C4"
    ACCENT_SOFT = "#EAF4FF"
    SUCCESS = "#137A40"
    SUCCESS_SOFT = "#EAF8F0"
    WARNING = "#976000"
    WARNING_SOFT = "#FFF6E2"
    ERROR = "#D92D20"
    ERROR_SOFT = "#FDECEC"
    CURRENT = "#0F766E"
    EXPERIMENT = "#7C3AED"
    DATA = "#4338CA"
    BORDER_LIGHT = "#E4E8ED"
    BORDER_MEDIUM = "#D5DAE1"
    SKELETON = "#E8EBEF"
    SKELETON_HIGHLIGHT = "#F3F5F7"
    SPACE_SMALL = 8
    SPACE_MEDIUM = 16
    SPACE_LARGE = 24
    CARD_RADIUS = 14
    CONTROL_RADIUS = 8
    FONT_BODY = 13
    FONT_CAPTION = 12
    FONT_SECTION = 16
    FONT_HEADING = 24
    FONT_WEIGHT = 600
    MOTION_DURATION = 0


def high_contrast_enabled():
    if os.name != 'nt': return False
    class HighContrast(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint), ('flags', ctypes.c_uint), ('scheme', ctypes.c_void_p)]
    value = HighContrast(); value.size = ctypes.sizeof(value)
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x42, value.size, ctypes.byref(value), 0) and value.flags & 1)


def appearance_tokens(window):
    settings = getattr(getattr(window, 'store', None), 'local', {})
    choice = settings.get('appearance', 'system')
    dark = choice == 'dark' or choice == 'system' and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    values = {name: getattr(Theme, name) for name in vars(Theme) if name.isupper()}
    if dark:
        values.update(BACKGROUND_PRIMARY='#171C24', BACKGROUND_SECONDARY='#202733', BACKGROUND_TERTIARY='#293241',
            TEXT_PRIMARY='#F0F3F8', TEXT_SECONDARY='#B8C3D3', TEXT_MUTED='#B8C3D3', TEXT_DISABLED='#8290A3',
            BORDER_LIGHT='#354154', BORDER_MEDIUM='#49566C', ACCENT_PRIMARY='#78BBFF', ACCENT_BUTTON='#0866BB',
            ACCENT_HOVER='#99CDFF', ACCENT_BUTTON_HOVER='#07599F', ACCENT_SOFT='#243E5B', SUCCESS='#8DD9AA', SUCCESS_SOFT='#1B3B2B',
            WARNING='#F4CE80', WARNING_SOFT='#44371F', ERROR='#FFAAA5', ERROR_SOFT='#4B282C',
            SKELETON='#303B4D', SKELETON_HIGHLIGHT='#3B4658')
    return SimpleNamespace(**values)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def apply_theme(window):
    font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"):
        if (font_dir / name).is_file():
            QFontDatabase.addApplicationFont(str(font_dir / name))
    t = appearance_tokens(window)
    settings = getattr(getattr(window, 'store', None), 'local', {})
    try: scale = max(1, min(2, float(settings.get('text_scale', 100)) / 100))
    except (TypeError, ValueError): scale = 1
    if high_contrast_enabled():
        window.setStyleSheet(f'QWidget {{ font-family: "Segoe UI"; font-size: {round(13 * scale)}px; }}')
        return
    sheet = f'''
        QWidget {{ background: {t.BACKGROUND_PRIMARY}; color: {t.TEXT_PRIMARY}; font-family: "Segoe UI"; font-size: 13px; }}
        QLabel {{ background: transparent; }}
        QLabel[kind="title"] {{ font-size: 30px; font-weight: 600; }}
        QLabel[kind="heading"] {{ font-size: 24px; font-weight: 600; }}
        QLabel[kind="section"] {{ font-size: 16px; font-weight: 600; }}
        QLabel[kind="cardTitle"] {{ font-size: 16px; font-weight: 600; }}
        QLabel[kind="eyebrow"], QLabel[kind="muted"] {{ color: {t.TEXT_SECONDARY}; font-size: 13px; }}
        QFrame#card, QFrame#emptyState, QFrame#sectionCard {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_LIGHT}; border-radius: {t.CARD_RADIUS}px; }}
        QWidget#cardActions {{ background: transparent; }}
        QWidget#sidebar {{ background: {t.BACKGROUND_TERTIARY}; border-radius: 12px; }}
        QPushButton, QToolButton {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_MEDIUM}; padding: 7px 12px; border-radius: {t.CONTROL_RADIUS}px; min-height: 20px; font-weight: 600; }}
        QPushButton:hover {{ background: {t.BACKGROUND_TERTIARY}; border-color: {t.ACCENT_PRIMARY}; }}
        QPushButton:pressed {{ background: {t.ACCENT_SOFT}; }}
        QPushButton:focus {{ border: 2px solid {t.ACCENT_PRIMARY}; }}
        QPushButton[primary="true"] {{ background: {t.ACCENT_BUTTON}; color: white; border-color: {t.ACCENT_BUTTON}; }}
        QPushButton[primary="true"]:hover {{ background: {t.ACCENT_BUTTON_HOVER}; }}
        QPushButton[variant="destructive"] {{ background: {Theme.ERROR}; color: white; }}
        QPushButton:disabled {{ color: {t.TEXT_DISABLED}; background: {t.BACKGROUND_TERTIARY}; border-color: {t.BORDER_LIGHT}; }}
        QPushButton[variant="sidebar"] {{ text-align: left; border: none; background: transparent; padding: 10px 12px; font-weight: 400; }}
        QPushButton[variant="sidebar"]:checked {{ color: {t.ACCENT_HOVER}; background: {t.ACCENT_SOFT}; font-weight: 600; }}
        QPushButton[variant="sidebar"]:hover {{ background: {t.ACCENT_SOFT}; }}
        QPushButton[variant="quiet"] {{ background: transparent; border-color: transparent; color: {t.ACCENT_HOVER}; }}
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ background: transparent; padding: 12px 18px; border-bottom: 2px solid transparent; color: {t.TEXT_SECONDARY}; }}
        QTabBar::tab:selected {{ color: {t.ACCENT_HOVER}; border-bottom-color: {t.ACCENT_PRIMARY}; font-weight: 600; }}
        QTabBar::tab:hover {{ background: {t.ACCENT_SOFT}; }}
        QLineEdit, QTextEdit, QComboBox {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_MEDIUM}; padding: 9px; border-radius: {t.CONTROL_RADIUS}px; min-height: 20px; selection-background-color: {t.ACCENT_PRIMARY}; }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 2px solid {t.ACCENT_PRIMARY}; }}
        QToolButton:focus, QTableView:focus, QListWidget:focus {{ border: 2px solid {t.ACCENT_PRIMARY}; }}
        QTextBrowser, QTextEdit {{ background: {t.BACKGROUND_SECONDARY}; color: {t.TEXT_PRIMARY}; }}
        QMenu {{ background: {t.BACKGROUND_SECONDARY}; color: {t.TEXT_PRIMARY}; border: 1px solid {t.BORDER_MEDIUM}; padding: 4px; }}
        QMenu::item {{ padding: 8px 16px; }}
        QMenu::item:selected {{ background: {t.ACCENT_SOFT}; color: {t.TEXT_PRIMARY}; }}
        QLineEdit[state="error"], QTextEdit[state="error"] {{ border-color: {t.ERROR}; }}
        QLineEdit:disabled, QTextEdit:disabled {{ background: {t.BACKGROUND_TERTIARY}; color: {t.TEXT_DISABLED}; }}
        QComboBox QAbstractItemView {{ background: {t.BACKGROUND_SECONDARY}; selection-background-color: {t.ACCENT_SOFT}; selection-color: {t.TEXT_PRIMARY}; padding: 4px; }}
        QScrollArea {{ border: none; }}
        QTableWidget {{ background: {t.BACKGROUND_SECONDARY}; alternate-background-color: {t.BACKGROUND_TERTIARY}; border: 1px solid {t.BORDER_LIGHT}; border-radius: 10px; gridline-color: transparent; selection-background-color: {t.ACCENT_SOFT}; selection-color: {t.TEXT_PRIMARY}; }}
        QTableWidget::item {{ padding: 6px; border-bottom: 1px solid {t.BORDER_LIGHT}; }}
        QTableWidget::item:hover {{ background: {t.BACKGROUND_TERTIARY}; }}
        QHeaderView::section {{ background: {t.BACKGROUND_TERTIARY}; border: none; padding: 10px 8px; font-weight: 600; color: {t.TEXT_SECONDARY}; }}
        QLabel[component="pill"] {{ background: {t.BACKGROUND_TERTIARY}; color: {t.TEXT_SECONDARY}; padding: 4px 10px; border-radius: 12px; font-size: 13px; }}
        QLabel[tone="success"] {{ background: {t.SUCCESS_SOFT}; color: {t.SUCCESS}; }}
        QLabel[tone="warning"] {{ background: {t.WARNING_SOFT}; color: {t.WARNING}; }}
        QLabel[tone="error"] {{ background: {t.ERROR_SOFT}; color: {t.ERROR}; }}
        QLabel[tone="info"] {{ background: {t.ACCENT_SOFT}; color: {t.ACCENT_HOVER}; }}
        QLabel[component="message"] {{ padding: 12px 16px; border-radius: 8px; }}
        QFrame#skeletonLine {{ background: {t.SKELETON}; border-radius: 5px; }}
        QFrame#toast {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_MEDIUM}; border-radius: 12px; }}
        QProgressBar {{ border: none; border-radius: 3px; background: {t.BACKGROUND_TERTIARY}; max-height: 6px; }}
        QProgressBar::chunk {{ background: {t.ACCENT_PRIMARY}; border-radius: 3px; }}
        QCheckBox[component="toggle"]::indicator {{ width: 38px; height: 20px; background: {t.BORDER_MEDIUM}; border-radius: 10px; border-left: 4px solid {t.BACKGROUND_SECONDARY}; border-right: 16px solid {t.BORDER_MEDIUM}; }}
        QCheckBox[component="toggle"]::indicator:checked {{ background: {t.ACCENT_PRIMARY}; border-left: 16px solid {t.ACCENT_PRIMARY}; border-right: 4px solid {t.BACKGROUND_SECONDARY}; }}
        QCheckBox[component="toggle"]:focus {{ color: {t.ACCENT_HOVER}; }}
        QListWidget {{ selection-color: {t.ACCENT_HOVER}; background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_LIGHT}; border-radius: 8px; }}
        QListWidget::item {{ padding: 9px; border-bottom: 1px solid {t.BORDER_LIGHT}; }}
        QListWidget::item:hover {{ background: {t.ACCENT_SOFT}; }}
        QListWidget::item:selected {{ background: {t.ACCENT_SOFT}; border-left: 3px solid {t.ACCENT_PRIMARY}; }}
        QSplitter::handle {{ background: {t.BORDER_MEDIUM}; width: 5px; }}
        QPushButton:checked {{ background: {t.ACCENT_SOFT}; color: {t.ACCENT_HOVER}; border-color: {t.ACCENT_PRIMARY}; }}
        QToolTip {{ background: {t.TEXT_PRIMARY}; color: {t.BACKGROUND_SECONDARY}; border: none; padding: 8px; }}
    '''
    sheet = re.sub(r'font-size: (\d+)px', lambda m: 'font-size: ' + str(round(int(m[1]) * scale)) + 'px', sheet)
    window.setStyleSheet(sheet)
    palette = window.palette(); palette.setColor(QPalette.Link, QColor(t.ACCENT_HOVER)); window.setPalette(palette)
    for view in window.findChildren(QTextBrowser):
        view.document().setDefaultStyleSheet(f'a {{ color: {t.ACCENT_HOVER}; }}')
    for table in window.findChildren(QTableView):
        table.verticalHeader().setDefaultSectionSize(round(38 * scale))
        header = table.horizontalHeader(); header.setMinimumSectionSize(round(100 * scale))
        for column in range(table.model().columnCount()):
            title = str(table.model().headerData(column, Qt.Horizontal) or '')
            header.resizeSection(column, max(header.sectionSize(column), header.fontMetrics().horizontalAdvance(title) + 32))
    rail = getattr(window, 'workspace_rail', None)
    if rail: rail.resize_to_text()
    header = getattr(window, 'workspace_header', None)
    if header: header.reflow()
