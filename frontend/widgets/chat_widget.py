"""Chat widget — message display, input, and streaming support."""
from __future__ import annotations

from PyQt5.QtCore import QCoreApplication, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class ChatWidget(QWidget):
    """Bubble-chat style widget with streaming message support."""

    message_sent = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        # Scrollable message area
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setReadOnly(True)

        # Input row
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self._on_send)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
        layout.addLayout(input_layout)

        self._streaming = False

    def _on_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.message_sent.emit(text)

    def add_user_message(self, text: str):
        self.browser.append(f'<p style="color:#666;"><b>You:</b> {text}</p>')
        self._scroll_bottom()

    def add_system_message(self, text: str):
        self.browser.append(f'<p style="color:#999;"><i>{text}</i></p>')
        self._scroll_bottom()

    def show_thinking(self, text: str):
        self.browser.append(f'<p style="color:#aaa;"><i>{text}</i></p>')
        self._scroll_bottom()

    def append_stream(self, text: str):
        if not self._streaming:
            self.browser.append('<p><b>Assistant:</b> ')
            self._streaming = True
        # Insert at cursor end
        cursor = self.browser.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self._scroll_bottom()

    def finalize_message(self, text: str):
        if self._streaming:
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertText("</p>")
            self._streaming = False
        self._scroll_bottom()

    def _scroll_bottom(self):
        scrollbar = self.browser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QCoreApplication.processEvents()
