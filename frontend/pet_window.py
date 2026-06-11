"""Desktop pet window — transparent, draggable, with day/night switching and chat."""

from __future__ import annotations

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
from PyQt5.QtNetwork import QAbstractSocket
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QVBoxLayout,
)

from frontend.widgets.chat_widget import ChatWidget

IMG_DIR = Path(__file__).resolve().parent.parent / "images"
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
# Chat dialog (standalone window, no parent)
# ====================================================================

CHAT_W = 340
CHAT_H = 460


class ChatDialog(QDialog):
    """Frameless chat popup using existing ChatWidget + QWebSocket."""

    def __init__(self, pet_pos: QPoint):
        super().__init__()  # IMPORTANT: no parent — avoid auto-close on parent click
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(CHAT_W, CHAT_H)
        self.setStyleSheet(
            "QDialog { background: rgba(255,255,255,0.95); border-radius: 16px; }"
        )

        # Position to the left of the pet
        x = max(0, pet_pos.x() - CHAT_W + 20)
        y = max(0, pet_pos.y() - CHAT_H + 60)
        self.move(x, y)

        # ── Layout ──────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(12, 10, 12, 4)
        title = QLabel("AI \u5c0f\u52a9\u624b")
        title.setStyleSheet("font-weight:600; color:#1a1a2e; font-size:13px;")
        self._close_btn = QPushButton("\u2715")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:13px; "
            "background:rgba(0,0,0,0.1); font-size:13px; }"
            "QPushButton:hover { background:rgba(0,0,0,0.2); }"
        )
        self._close_btn.clicked.connect(self.close)
        hdr.addWidget(title, 1)
        hdr.addWidget(self._close_btn)
        layout.addLayout(hdr)

        # Chat widget (reused from existing project)
        self._chat_widget = ChatWidget()
        layout.addWidget(self._chat_widget, 1)

        # Connect ChatWidget's send signal to our handler
        self._chat_widget.message_sent.connect(self._on_user_message)

        # ── WebSocket ───────────────────────────────────────
        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.disconnected.connect(self._on_ws_disconnected)

        self._connect_timer = QTimer(self)
        self._connect_timer.setSingleShot(True)
        self._connect_timer.timeout.connect(self._retry_ws)

        self._chat_widget.add_system_message("Connecting to backend...")
        self._ws.open(QUrl(WS_URL))

    # -- WebSocket signals -----------------------------------------

    def _on_ws_connected(self):
        self._chat_widget.add_system_message("Connected.")

    def _on_ws_disconnected(self):
        self._chat_widget.add_system_message("Disconnected. Retrying...")
        self._connect_timer.start(3000)

    def _retry_ws(self):
        self._ws.open(QUrl(WS_URL))

    # -- Send -------------------------------------------------------

    def _on_user_message(self, text: str):
        if self._ws.state() != QAbstractSocket.ConnectedState:
            self._chat_widget.add_system_message(
                "Backend offline. Start:  uvicorn backend.main:app"
            )
            return
        stream = self._chat_widget.stream_check.isChecked()
        self._ws.sendTextMessage(
            __import__("json").dumps({"content": text, "stream": stream})
        )

    # -- WebSocket receive ------------------------------------------

    def _on_ws_message(self, raw: str):
        try:
            data = __import__("json").loads(raw)
        except Exception:
            return

        t = data.get("type")
        c = data.get("content", "")
        stream_on = self._chat_widget.stream_check.isChecked()

        if t == "token" or (t == "delta" and stream_on):
            self._chat_widget.append_stream(c)
        elif t in ("done", "reply"):
            self._chat_widget.finalize_message(c)
        elif t == "thinking":
            self._chat_widget.show_thinking(c)
        elif t == "tool_call":
            self._chat_widget.add_system_message(
                "[Tool] Calling " + data.get("tool", "?")
            )
        elif t == "tool_result":
            self._chat_widget.add_system_message(
                "[Tool] " + (c[:120] if c else "")
            )
        elif t == "error":
            self._chat_widget.add_system_message("[Error] " + c)
        elif t == "reply":
            self._chat_widget.finalize_message(c)


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

        self._chat = None
        self._phase = None
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
            self._chat.deleteLater()
            self._chat = None
        else:
            self._chat = ChatDialog(self.geometry().topLeft())
            self._chat.destroyed.connect(self._on_chat_destroyed)
            self._chat.show()

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
            self._phase = "day"
            self._apply_phase()
        elif action == n:
            self._phase = "night"
            self._apply_phase()
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
