"""Frameless, always-on-top dialog that shows detected blacklisted processes
and offers the user a choice to terminate them or ignore.
"""

from __future__ import annotations

import logging
import sys
from typing import List

import psutil
from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.app_blocker import get_process_display_name, terminate_processes

logger = logging.getLogger(__name__)

# ── Style constants ─────────────────────────────────────────────
_BG_ALPHA = "QDialog { background: rgba(0, 0, 0, 140); }"
_CONTAINER_STYLE = (
    "QFrame#container {"
    "  background: #ffffff;"
    "  border-radius: 16px;"
    "}"
)
_BTN_CLOSE_STYLE = (
    "QPushButton {"
    "  border: none;"
    "  border-radius: 8px;"
    "  padding: 10px 24px;"
    "  background: #e74c3c;"
    "  color: white;"
    "  font-size: 13px;"
    "  font-weight: 600;"
    "}"
    "QPushButton:hover { background: #c0392b; }"
    "QPushButton:pressed { background: #a93226; }"
)
_BTN_IGNORE_STYLE = (
    "QPushButton {"
    "  border: 1px solid #ccc;"
    "  border-radius: 8px;"
    "  padding: 10px 24px;"
    "  background: white;"
    "  color: #555;"
    "  font-size: 13px;"
    "}"
    "QPushButton:hover { background: #f5f5f5; }"
    "QPushButton:pressed { background: #e8e8e8; }"
)
_LIST_STYLE = (
    "QListWidget {"
    "  border: 1px solid #eee;"
    "  border-radius: 8px;"
    "  background: #fafafa;"
    "  padding: 4px;"
    "  font-size: 12px;"
    "}"
    "QListWidget::item {"
    "  padding: 6px 8px;"
    "  border-bottom: 1px solid #f0f0f0;"
    "}"
)


class FocusBlockerDialog(QDialog):
    """Modal dialog showing running blacklisted processes.

    The user can either terminate them or dismiss the warning.
    """

    W = 400
    H = 320

    def __init__(
        self,
        processes: list[psutil.Process],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._processes = processes

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)

        # Semi-transparent overlay background
        self.setStyleSheet(_BG_ALPHA)

        # Center on screen
        self._center_on_screen()

        # ── Container frame ────────────────────────────────────
        container = QFrame(self)
        container.setObjectName("container")
        container.setStyleSheet(_CONTAINER_STYLE)
        container.setGeometry(20, 40, self.W - 40, self.H - 80)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("\u26a0\ufe0f  \u4e13\u6ce8\u6a21\u5f0f \u2014 \u68c0\u6d4b\u5230\u9ed1\u540d\u5355\u8fdb\u7a0b")
        title.setStyleSheet("font-size:14px; font-weight:600; color:#1a1a2e;")
        layout.addWidget(title)

        # Process list
        self._list = QListWidget()
        self._list.setStyleSheet(_LIST_STYLE)
        self._populate_list()
        layout.addWidget(self._list, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self._ignore_btn = QPushButton("\u5ffd\u7565")
        self._ignore_btn.setCursor(Qt.PointingHandCursor)
        self._ignore_btn.setStyleSheet(_BTN_IGNORE_STYLE)
        self._ignore_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._ignore_btn)

        self._close_btn = QPushButton("\u5173\u95ed\u8fd9\u4e9b\u8fdb\u7a0b")
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(_BTN_CLOSE_STYLE)
        self._close_btn.clicked.connect(self._on_terminate)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    # ── Internal helpers ─────────────────────────────────────


    @staticmethod
    def _get_process_icon(proc) -> QIcon:
        try:
            exe_path = proc.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return QIcon()
        if sys.platform == "win32":
            try:
                import win32gui
                large, _ = win32gui.ExtractIconEx(exe_path, 0)
                if large:
                    hicon = large[0]
                    pm = QPixmap.fromWinHICON(hicon)
                    win32gui.DestroyIcon(hicon)
                    if pm and not pm.isNull():
                        return QIcon(pm)
            except Exception:
                pass
        return QIcon()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        x = geo.center().x() - self.W // 2
        y = geo.center().y() - self.H // 2
        self.move(x, y)

    def _populate_list(self) -> None:
        for proc in self._processes:
            try:
                name = proc.name()
                pid = proc.pid
                display_name = get_process_display_name(proc)
                icon = self._get_process_icon(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            text = f"{display_name}  ({name}, PID: {pid})"
            item = QListWidgetItem(icon, text)
            item.setSizeHint(QSize(self._list.width() - 20, 36))
            item.setToolTip(f"{display_name}\n{name}\nPID: {pid}")
            self._list.addItem(item)

    def _on_terminate(self) -> None:
        """Terminate the listed processes and show a result message."""
        count = terminate_processes(self._processes)
        total = len(self._processes)
        logger.info(
            "Focus blocker: terminated %d / %d blacklisted process(es)",
            count, total,
        )

        # Refresh the list to show which processes remain
        self._processes = [
            p for p in self._processes
            if p.is_running()
        ]
        self._list.clear()
        self._populate_list()

        if not self._processes:
            # All terminated — close with success
            QMessageBox.information(
                self,
                "\u63d0\u793a",
                f"\u5df2\u6210\u529f\u5173\u95ed {count} \u4e2a\u9ed1\u540d\u5355\u8fdb\u7a0b\u3002",
            )
            self.accept()
        else:
            # Some survived
            msg = (
                f"\u5df2\u5173\u95ed {count} \u4e2a\u8fdb\u7a0b\uff0c"
                f"\u4ecd\u6709 {len(self._processes)} \u4e2a\u8fdb\u7a0b\u5b58\u6d3b\u3002"
            )
            QMessageBox.warning(self, "\u63d0\u793a", msg)
