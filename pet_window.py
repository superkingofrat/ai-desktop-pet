"""Desktop pet window — transparent, draggable, with chat dialog."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PyQt5.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTime,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


IMG_DIR = Path(__file__).resolve().parent / "images"
SIZE = QSize(120, 120)
WS_URL = "ws://127.0.0.1:8000/ws/chat?session_id=pet-desktop"


# ====================================================================
# Clickable label
# ====================================================================

class _PetLabel(QLabel):
    """QLabel with hand cursor, click signal, and drag support."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setScaledContents(True)
        self._press_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPos()
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._press_pos is not None:
            parent = self.window()
            delta = event.globalPos() - self._press_pos
            parent.move(parent.pos() + delta)
            self._press_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = None
        super().mouseReleaseEvent(event)


# ====================================================================
# Chat dialog
# ====================================================================

class ChatDialog(QDialog):
    """Frameless chat window that connects to the backend via WebSocket."""

    CHAT_SIZE = QSize(340, 440)

    def __init__(self, pet_pos: QPoint, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.CHAT_SIZE)
        self.setStyleSheet("""
            QDialog { background: rgba(255,255,255,0.95); border-radius: 16px; }
        """)

        # Position to the left of the pet
        cx, cy = pet_pos.x(), pet_pos.y()
        dx = max(0, cx - self.CHAT_SIZE.width() + 20)
        dy = max(0, cy - self.CHAT_SIZE.height() + 60)
        self.move(dx, dy)

        # ── Layout ──────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("AI 小助手")
        title.setStyleSheet("font-weight:600; color:#1a1a2e;")
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:13px; "
            "background:rgba(0,0,0,0.1); font-size:13px; }"
            "QPushButton:hover { background:rgba(0,0,0,0.2); }"
        )
        close_btn.clicked.connect(self.close)
        hdr.addWidget(title, 1)
        hdr.addWidget(close_btn)
        layout.addLayout(hdr)

        # Chat browser
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setReadOnly(True)
        self.browser.setStyleSheet("QTextBrowser { border: none; background: transparent; }")
        layout.addWidget(self.browser, 1)

        # Stream toggle + input
        self.stream_check = QCheckBox("Stream")
        self.stream_check.setChecked(True)
        self.stream_check.setStyleSheet("font-size:11px; color:#666;")

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self._send_message)

        self.send_btn = QPushButton("\u27a4")
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:18px; "
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1, "
            "stop:0 #f093fb, stop:1 #f5576c); color:#fff; font-size:16px; }"
            "QPushButton:hover { opacity:0.9; }"
        )
        self.send_btn.clicked.connect(self._send_message)

        inp_row = QHBoxLayout()
        inp_row.addWidget(self.stream_check)
        inp_row.addWidget(self.input_field, 1)
        inp_row.addWidget(self.send_btn)
        layout.addLayout(inp_row)

        # ── WebSocket ───────────────────────────────────────
        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.connected.connect(lambda: self._add_sys("Connected."))
        self._ws.disconnected.connect(lambda: self._add_sys("Disconnected."))
        self._ws.open(QUrl(WS_URL))

        self._streaming = False

    # -- WS connection handlers ------------------------------------

    def _on_ws_connected(self):
        self._add_sys('Connected to AI Assistant backend.')

    def _on_ws_disconnected(self):
        self._add_sys('Backend disconnected. Retrying in 3s...')
        self._connect_timer.start(3000)

    def _on_ws_error(self, error_code):
        self._add_sys('Cannot reach backend. Retrying in 5s...')
        self._add_sys('Start backend with:  uvicorn backend.main:app')
        self._connect_timer.start(5000)

    def _retry_ws(self):
        self._add_sys('Reconnecting...')
        self._ws.open(QUrl(WS_URL))

    # -- Send -------------------------------------------------------

    def _send_message(self):
        text = self.input_field.text().strip()
        if not text or self._ws.state() != QWebSocket.ConnectedState:
            return
        self.input_field.clear()
        self._add_user(text)

        stream = self.stream_check.isChecked()
        self._ws.sendTextMessage(json.dumps({"content": text, "stream": stream}))

    # -- Receive ----------------------------------------------------

    def _on_ws_message(self, raw: str):
        try:
            data = json.loads(raw)
        except Exception:
            return

        t = data.get("type")

        if t == "token" or (t == "delta" and self.stream_check.isChecked()):
            self._append_stream(data.get("content", ""))

        elif t == "done":
            self._finalize(data.get("content", ""))

        elif t == "reply":
            self._finalize(data.get("content", ""))

        elif t == "thinking":
            self._add_sys("\u23f3 " + data.get("content", ""))

        elif t == "tool_call":
            self._add_sys("\U0001f527 Calling " + data.get("tool", "?"))

        elif t == "tool_result":
            result = (data.get("result", "") or "")[:120]
            self._add_sys("\u2705 " + result)

        elif t == "error":
            self._add_sys("\u274c " + data.get("content", ""))

    # -- Display helpers -------------------------------------------

    def _add_user(self, text: str):
        self.browser.append(
            '<p style="color:#666;"><b>You:</b> {}</p>'.format(text)
        )

    def _add_sys(self, text: str):
        self.browser.append(
            '<p style="color:#999;"><i>{}</i></p>'.format(text)
        )

    def _append_stream(self, text: str):
        if not self._streaming:
            self.browser.append("<p><b>Assistant:</b> ")
            self._streaming = True
        cursor = self.browser.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)

    def _finalize(self, text: str):
        if self._streaming:
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertText("</p>")
            self._streaming = False
        else:
            self.browser.append(
                "<p><b>Assistant:</b> {}</p>".format(text)
            )


# ====================================================================
# Pet window
# ====================================================================

class PetWindow(QMainWindow):
    """Frameless transparent pet with day/night images, jelly click, and chat."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(SIZE)

        self._label = _PetLabel(self)
        self._label.setGeometry(0, 0, SIZE.width(), SIZE.height())
        self._label.clicked.connect(self._on_click)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._chat: ChatDialog | None = None
        self._phase: str | None = None
        self._apply_phase()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._apply_phase)
        self._timer.start(60_000)

    # -- Day / night ------------------------------------------------

    def _compute_phase(self):
        hour = QTime.currentTime().hour()
        return "night" if hour >= 18 or hour < 6 else "day"

    def _apply_phase(self):
        new = self._compute_phase()
        if new == self._phase:
            return
        self._phase = new
        pix = self._load_pixmap(new)
        scaled = pix.scaled(SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(scaled)

    def _load_pixmap(self, phase: str) -> QPixmap:
        path = IMG_DIR / f"{phase}.png"
        if path.exists():
            return QPixmap(str(path))
        pm = QPixmap(SIZE)
        pm.fill(Qt.transparent)
        with QPainter(pm) as p:
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            if phase == "day":
                p.setBrush(QColor(255, 200, 50))
                p.drawEllipse(8, 8, 104, 104)
            else:
                p.setBrush(QColor(30, 30, 60))
                p.drawEllipse(8, 8, 104, 104)
                p.setBrush(QColor(240, 230, 180))
                p.drawEllipse(22, 22, 76, 76)
                p.setBrush(QColor(30, 30, 60))
                p.drawEllipse(34, 22, 76, 76)
        return pm

    # -- Click: jelly + toggle chat --------------------------------

    def _on_click(self):
        self._jelly()
        self._toggle_chat()

    def _jelly(self):
        geo = self.geometry()
        w, h = geo.width(), geo.height()
        nw, nh = int(w * 1.15), int(h * 1.15)
        dx, dy = (nw - w) // 2, (nh - h) // 2
        expanded = QRect(geo.x() - dx, geo.y() - dy, nw, nh)

        a1 = QPropertyAnimation(self, b"geometry")
        a1.setDuration(50)
        a1.setStartValue(geo)
        a1.setEndValue(expanded)

        a2 = QPropertyAnimation(self, b"geometry")
        a2.setDuration(100)
        a2.setStartValue(expanded)
        a2.setEndValue(geo)
        a2.setEasingCurve(QEasingCurve.OutBounce)

        g = QSequentialAnimationGroup(self)
        g.addAnimation(a1)
        g.addAnimation(a2)
        g.start(QAbstractAnimation.DeleteWhenStopped)

    def _toggle_chat(self):
        if self._chat is not None and self._chat.isVisible():
            self._chat.close()
            self._chat = None
        else:
            self._chat = ChatDialog(self.geometry().topLeft(), self)
            self._chat.show()
            self._chat.destroyed.connect(lambda: setattr(self, "_chat", None))

    def _on_chat_destroyed(self):
        self._chat = None

    # -- Context menu ----------------------------------------------

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        d = menu.addAction("\u2600\ufe0f  白天模式")
        n = menu.addAction("\U0001f319\ufe0f  夜间模式")
        menu.addSeparator()
        q = menu.addAction("\U0001f6aa  退出")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == d:
            self._phase = "day"; self._apply_phase()
        elif action == n:
            self._phase = "night"; self._apply_phase()
        elif action == q:
            QApplication.quit()


# ====================================================================
# Entry point
# ====================================================================

def main():
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("Desktop Pet")
    win = PetWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
