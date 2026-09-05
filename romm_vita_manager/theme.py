from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from .design_tokens import DARK


def application_stylesheet() -> str:
    p = DARK
    return f"""
    QMainWindow, QDialog, QWidget {{
        background: {p.background};
        color: {p.text_primary};
        selection-background-color: #3A3A3C;
        selection-color: {p.text_primary};
    }}

    QToolTip {{
        background: {p.surface_raised};
        color: {p.text_primary};
        border: 1px solid {p.separator};
        border-radius: 7px;
        padding: 5px 8px;
    }}

    QLabel {{
        background: transparent;
        color: {p.text_primary};
    }}

    QLabel[secondary="true"] {{ color: {p.text_secondary}; }}
    QLabel[tertiary="true"] {{ color: {p.text_tertiary}; }}

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {p.surface};
        color: {p.text_primary};
        border: 1px solid {p.separator};
        border-radius: 9px;
        padding: 7px 10px;
        min-height: 20px;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: #6E6E73;
        background: {p.surface_raised};
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
    QComboBox:disabled {{
        background: #171719;
        color: #65656A;
        border-color: #2A2A2D;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {p.surface_raised};
        color: {p.text_primary};
        border: 1px solid {p.separator};
        selection-background-color: {p.surface_hover};
        outline: none;
    }}

    QPushButton {{
        background: {p.surface_raised};
        color: {p.text_primary};
        border: 1px solid {p.separator};
        border-radius: 9px;
        padding: 7px 13px;
        min-height: 22px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {p.surface_hover};
        border-color: #4A4A4D;
    }}
    QPushButton:focus {{
        border-color: #8E8E93;
    }}
    QPushButton:pressed {{
        background: #323235;
    }}
    QPushButton:disabled {{
        background: #171719;
        color: #5C5C61;
        border-color: #29292C;
    }}
    QPushButton[quiet="true"] {{
        background: transparent;
        border-color: transparent;
        color: {p.text_secondary};
    }}
    QPushButton[quiet="true"]:hover {{
        background: {p.surface};
        color: {p.text_primary};
    }}
    QPushButton[quiet="true"]:focus {{
        border-color: #6E6E73;
    }}
    QPushButton[destructive="true"] {{
        color: {p.error};
    }}

    QGroupBox {{
        background: {p.surface};
        border: 1px solid {p.separator};
        border-radius: 13px;
        margin-top: 15px;
        padding: 15px 13px 13px 13px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 13px;
        padding: 0 5px;
        color: {p.text_secondary};
    }}

    QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {{
        background: {p.surface};
        alternate-background-color: #202022;
        color: {p.text_primary};
        border: 1px solid {p.separator};
        border-radius: 11px;
        outline: none;
    }}
    QListWidget:focus, QListView:focus, QTreeWidget:focus, QTreeView:focus,
    QTableWidget:focus, QTableView:focus {{
        border-color: #5A5A5E;
    }}
    QListWidget::item, QListView::item, QTreeView::item {{
        padding: 8px;
        border-radius: 7px;
    }}
    QListWidget::item:hover, QListView::item:hover, QTreeView::item:hover {{
        background: {p.surface_hover};
    }}
    QListWidget::item:selected, QListView::item:selected, QTreeView::item:selected {{
        background: #343437;
        color: {p.text_primary};
    }}
    QHeaderView::section {{
        background: #18181A;
        color: {p.text_secondary};
        border: none;
        border-bottom: 1px solid {p.separator};
        padding: 7px 9px;
        font-weight: 600;
    }}

    QProgressBar {{
        background: #242426;
        border: none;
        border-radius: 4px;
        min-height: 7px;
        max-height: 7px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: #8E8E93;
        border-radius: 4px;
    }}

    QRadioButton, QCheckBox {{
        background: transparent;
        spacing: 7px;
        color: {p.text_primary};
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: #48484A;
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #636366; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:add-page:vertical, QScrollBar:sub-page:vertical {{ background: transparent; }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: #48484A;
        border-radius: 3px;
        min-width: 30px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar:add-page:horizontal, QScrollBar:sub-page:horizontal {{ background: transparent; }}

    QSplitter::handle {{ background: transparent; }}

    QStatusBar {{
        background: #111113;
        color: {p.text_secondary};
        border-top: 1px solid #252528;
    }}

    QMessageBox {{ background: {p.surface}; }}
    """


def apply_application_theme(app: QApplication) -> None:
    """Apply the shared desktop theme once at application startup."""
    app.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
    app.setStyleSheet(application_stylesheet())


__all__ = ["apply_application_theme", "application_stylesheet"]