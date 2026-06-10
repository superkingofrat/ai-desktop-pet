"""Main application window — PyQt5 with real-time streaming support."""
from __future__ import annotations

import json

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QWebSocket
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from frontend.widgets.chat_widget import ChatWidget


class MainWindow(QMainWindow):
    """Main window hosting the chat interface and connecting via WebSocket."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Assistant")
        self.setMinimumSize(800, 600)

        # Streaming toggle (default True for real-time UX)
        self._stream = True

        # WebSocket connection
        self.ws = QWebSocket()
        self.ws.connected.connect(self._on_connected)
        self.ws.textMessageReceived.connect(self._on_message)
        self.ws.disconnected.connect(self._on_disconnected)

        # Chat widget
        self.chat_widget = ChatWidget()
        self.chat_widget.message_sent.connect(self._send_message)
        self.chat_widget.stream_toggled.connect(self._on_stream_toggle)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.chat_widget)
        self.setCentralWidget(central)

        # Connect to backend
        self.ws.open(QUrl("ws://127.0.0.1:8000/ws/chat"))

    def _on_connected(self):
        self.chat_widget.add_system_message("Connected to server.")

    def _on_disconnected(self):
        self.chat_widget.add_system_message("Disconnected from server.")

    def _on_stream_toggle(self, enabled: bool):
        self._stream = enabled

    def _on_message(self, message: str):
        data = json.loads(message)
        msg_type = data.get("type")

        if msg_type == "token":
            # ── Real-time streaming token ──────────────────
            self.chat_widget.append_stream(data.get("content", ""))

        elif msg_type == "reply":
            # ── Batch reply (non-streaming mode) ───────────
            self.chat_widget.finalize_message(data.get("content", ""))

        elif msg_type == "delta":
            self.chat_widget.append_stream(data.get("content", ""))

        elif msg_type == "thinking":
            self.chat_widget.show_thinking(data.get("content", ""))

        elif msg_type == "done":
            self.chat_widget.finalize_message(data.get("content", ""))

        elif msg_type == "tool_call":
            self.chat_widget.add_system_message(
                "[Tool] Calling {}...".format(data["tool"])
            )

        elif msg_type == "tool_result":
            self.chat_widget.add_system_message(
                "[Tool] {} returned: {}".format(
                    data["tool"], data["result"][:100]
                )
            )

        elif msg_type == "error":
            self.chat_widget.add_system_message("[Error] {}".format(data["content"]))

    def _send_message(self, text: str):
        payload = json.dumps({"content": text, "stream": self._stream})
        self.ws.sendTextMessage(payload)
        self.chat_widget.add_user_message(text)
