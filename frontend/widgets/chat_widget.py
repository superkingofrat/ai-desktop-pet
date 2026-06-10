"""Chat widget — message display, input, streaming support, and stream toggle."""
from __future__ import annotations

from PyQt5.QtCore import QCoreApplication, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class ChatWidget(QWidget):
    """Chat interface with real-time streaming token display."""

    message_sent = pyqtSignal(str)
    stream_toggled = pyqtSignal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        # ── Message display area ────────────────────────────
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setReadOnly(True)

        # ── Stream toggle ───────────────────────────────────
        self.stream_check = QCheckBox("Stream")
        self.stream_check.setChecked(True)
        self.stream_check.stateChanged.connect(
            lambda s: self.stream_toggled.emit(s == Qt.Checked)
        )

        # ── Input row ───────────────────────────────────────
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self._on_send)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.stream_check)
        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(self.send_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.browser, 1)
        layout.addLayout(input_layout)

        self._streaming = False   # True while accumulating a streamed response

    # ── Send ─────────────────────────────────────────────────

    def _on_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.message_sent.emit(text)

    # ── Display helpers ──────────────────────────────────────

    def add_user_message(self, text: str):
        self.browser.append(
            '<p style="color:#666;"><b>You:</b> {}</p>'.format(text)
        )
        self._scroll_bottom()

    def add_system_message(self, text: str):
        self.browser.append(
            '<p style="color:#999;"><i>{}</i></p>'.format(text)
        )
        self._scroll_bottom()

    def show_thinking(self, text: str):
        self.browser.append(
            '<p style="color:#aaa;"><i>{}</i></p>'.format(text)
        )
        self._scroll_bottom()

    # ── Streaming helpers ────────────────────────────────────

    def append_stream(self, text: str):
        """Append a token/delta chunk to the current streaming message."""
        if not self._streaming:
            self.browser.append("<p><b>Assistant:</b> ")
            self._streaming = True
        cursor = self.browser.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self._scroll_bottom()

    def finalize_message(self, text: str):
        """Finalize the current assistant message (called on ``done`` or ``reply``)."""
        if self._streaming:
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertText("</p>")
            self._streaming = False
        else:
            # Non-streaming path: insert the whole reply at once
            self.browser.append(
                '<p><b>Assistant:</b> {}</p>'.format(text)
            )
        self._scroll_bottom()

    # ── Internals ────────────────────────────────────────────

    def _scroll_bottom(self):
        scrollbar = self.browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QCoreApplication.processEvents()
