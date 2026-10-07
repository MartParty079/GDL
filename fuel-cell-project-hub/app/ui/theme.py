"""Shared design tokens and Qt stylesheet for all Hub surfaces."""
import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase


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
    ACCENT_SOFT = "#EAF4FF"
    SUCCESS = "#137A40"
    SUCCESS_SOFT = "#EAF8F0"
    WARNING = "#976000"
    WARNING_SOFT = "#FFF6E2"
    ERROR = "#D92D20"
    ERROR_SOFT = "#FDECEC"
    BORDER_LIGHT = "#E4E8ED"
    BORDER_MEDIUM = "#D5DAE1"
    SKELETON = "#E8EBEF"
    SKELETON_HIGHLIGHT = "#F3F5F7"
    SPACE_SMALL = 8
    SPACE_MEDIUM = 16
    SPACE_LARGE = 24
    CARD_RADIUS = 14
    CONTROL_RADIUS = 8


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def apply_theme(window):
    font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"):
        if (font_dir / name).is_file():
            QFontDatabase.addApplicationFont(str(font_dir / name))
    t = Theme
    window.setStyleSheet(f'''
        QWidget {{ background: {t.BACKGROUND_PRIMARY}; color: {t.TEXT_PRIMARY}; font-family: "Segoe UI"; font-size: 14px; }}
        QLabel {{ background: transparent; }}
        QLabel[kind="title"] {{ font-size: 30px; font-weight: 600; }}
        QLabel[kind="heading"] {{ font-size: 25px; font-weight: 600; }}
        QLabel[kind="section"] {{ font-size: 19px; font-weight: 600; }}
        QLabel[kind="cardTitle"] {{ font-size: 16px; font-weight: 600; }}
        QLabel[kind="eyebrow"], QLabel[kind="muted"] {{ color: {t.TEXT_SECONDARY}; font-size: 13px; }}
        QFrame#card, QFrame#emptyState, QFrame#sectionCard {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_LIGHT}; border-radius: {t.CARD_RADIUS}px; }}
        QWidget#cardActions {{ background: transparent; }}
        QWidget#sidebar {{ background: {t.BACKGROUND_TERTIARY}; border-radius: 12px; }}
        QPushButton {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_MEDIUM}; padding: 9px 16px; border-radius: {t.CONTROL_RADIUS}px; min-height: 20px; font-weight: 600; }}
        QPushButton:hover {{ background: {t.BACKGROUND_TERTIARY}; border-color: {t.ACCENT_PRIMARY}; }}
        QPushButton:pressed {{ background: {t.ACCENT_SOFT}; }}
        QPushButton:focus {{ border: 2px solid {t.ACCENT_PRIMARY}; }}
        QPushButton[primary="true"] {{ background: {t.ACCENT_BUTTON}; color: white; border-color: {t.ACCENT_BUTTON}; }}
        QPushButton[primary="true"]:hover {{ background: {t.ACCENT_HOVER}; }}
        QPushButton[variant="destructive"] {{ background: {t.ERROR}; color: white; }}
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
        QLineEdit[state="error"], QTextEdit[state="error"] {{ border-color: {t.ERROR}; }}
        QLineEdit:disabled, QTextEdit:disabled {{ background: {t.BACKGROUND_TERTIARY}; color: {t.TEXT_DISABLED}; }}
        QComboBox QAbstractItemView {{ background: {t.BACKGROUND_SECONDARY}; selection-background-color: {t.ACCENT_SOFT}; selection-color: {t.TEXT_PRIMARY}; padding: 4px; }}
        QScrollArea {{ border: none; }}
        QTableWidget {{ background: {t.BACKGROUND_SECONDARY}; border: 1px solid {t.BORDER_LIGHT}; border-radius: 10px; gridline-color: transparent; selection-background-color: {t.ACCENT_SOFT}; selection-color: {t.TEXT_PRIMARY}; }}
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
        QToolTip {{ background: {t.TEXT_PRIMARY}; color: {t.BACKGROUND_SECONDARY}; border: none; padding: 8px; }}
    ''')
