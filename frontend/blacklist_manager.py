
"""Blacklist manager dialog — add/remove process names from the blacklist."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.app_blocker import load_blacklist, save_blacklist


class BlacklistManagerDialog(QDialog):
    """Modal dialog for editing the process blacklist."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("\u9ed1\u540d\u5355\u7ba1\u7406")
        self.setFixedSize(420, 480)
        self.setModal(True)

        self._blacklist: list[str] = load_blacklist()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Add row
        add_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("\u8f93\u5165\u8fdb\u7a0b\u540d\uff08\u5982 notepad.exe\uff09")
        add_btn = QPushButton("\u6dfb\u52a0")
        add_btn.clicked.connect(self._on_add)
        add_row.addWidget(self._input, 1)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # List
        self._list = QListWidget()
        self._populate()
        layout.addWidget(self._list, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("\u4fdd\u5b58")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("\u53d6\u6d88")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _populate(self) -> None:
        self._list.clear()
        for name in sorted(self._blacklist, key=str.lower):
            item = QListWidgetItem()
            w = self._make_item_widget(name)
            item.setSizeHint(w.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, w)

    def _make_item_widget(self, name: str) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(4, 2, 4, 2)
        label = QLabel(name)
        label.setStyleSheet("font-size:12px; color:#e0e0e0;")
        del_btn = QPushButton("\u5220\u9664")
        del_btn.setFixedSize(50, 24)
        del_btn.setStyleSheet(
            "QPushButton { border:1px solid #e74c3c; border-radius:4px; "
            "background:transparent; color:#e74c3c; font-size:11px; }"
            "QPushButton:hover { background:#e74c3c; color:white; }"
        )
        del_btn.clicked.connect(lambda checked, n=name: self._on_delete(n))
        lay.addWidget(label, 1)
        lay.addWidget(del_btn)
        return row

    def _on_add(self) -> None:
        text = self._input.text().strip().lower()
        if not text:
            return
        if text not in self._blacklist:
            self._blacklist.append(text)
            self._populate()
        self._input.clear()

    def _on_delete(self, name: str) -> None:
        if name in self._blacklist:
            self._blacklist.remove(name)
            self._populate()

    def _on_save(self) -> None:
        save_blacklist(self._blacklist)
        self.accept()
