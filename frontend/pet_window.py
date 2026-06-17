"""Desktop pet window — transparent, draggable, with day/night switching and chat."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path (works for: python frontend/pet_window.py)
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from PyQt5.QtCore import (
    QBuffer,
    QIODevice,
    QByteArray,
    QSettings,
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
from frontend.idle_detector import get_idle_seconds
from frontend.pet_animator import (
    PetState,
    PetAnimator,
    detect_animation_resources,
)
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QPlainTextEdit,
    QFrame,
    QWidget,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QVBoxLayout,
)


IMG_DIR = Path(__file__).resolve().parent.parent / "images"
SIZE = QSize(120, 120)
def _ws_url():
    """Lazy WebSocket URL — reads config fresh each call (port may change)."""
    return __import__("frontend.config", fromlist=["get_ws_url"]).get_ws_url()


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




# -- Pet icon helpers --------------------------------------------------
def _icon_to_b64(pm):
    """QPixmap -> base64 string (uses temp file for reliability)."""
    import base64, tempfile, os
    tmp = tempfile.mktemp(suffix=".png")
    pm.save(tmp)
    with open(tmp, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    os.unlink(tmp)
    return b64


def _b64_to_icon(b64_str):
    """base64 string -> QPixmap."""
    import base64
    raw = base64.b64decode(b64_str)
    pm = QPixmap()
    pm.loadFromData(raw)
    return pm

class ChatDialog(QDialog):
    """Frameless chat popup with bubble messages, styled input, status indicator."""

    CHAT_W = 340
    CHAT_H = 480

    def __init__(self, pet_pos: QPoint, parent_win=None):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Background painted by QFrame container
        self.setFixedSize(self.CHAT_W, self.CHAT_H)
        # QFrame container has the white background + rounded corners
        x = max(0, pet_pos.x() - self.CHAT_W + 20)
        y = max(0, pet_pos.y() - self.CHAT_H + 60)
        self.move(x, y)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(12, 10, 12, 4)
        title = QLabel("AI \u5c0f\u52a9\u624b")
        title.setStyleSheet("font-weight:600; color:#1a1a2e; font-size:13px;")
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(10, 10)
        self._status_dot.setStyleSheet("background: #999; border-radius:5px;")
        self._pulse_on = False
        self._parent_win = parent_win
        self._personality = QSettings("MyApp", "AIDesktopPet").value("personality", "", str)
        self._stream_cb = QCheckBox("Stream")
        self._stream_cb.setChecked(True)
        self._stream_cb.setStyleSheet("font-size:11px; color:#666;")
        self._close_btn = QPushButton("\u2715")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:13px;"
            " background:rgba(0,0,0,0.1); font-size:13px; }"
            "QPushButton:hover { background:rgba(0,0,0,0.2); }"
        )
        self._close_btn.clicked.connect(self.close)
        hdr.addWidget(title, 1)
        hdr.addWidget(self._status_dot)
        hdr.addSpacing(4)
        hdr.addWidget(self._stream_cb)
        hdr.addSpacing(4)
        self._settings_btn = QPushButton("\u2699")
        self._settings_btn.setFixedSize(26, 26)
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:13px; "
            "background:rgba(0,0,0,0.1); font-size:13px; }"
            "QPushButton:hover { background:rgba(0,0,0,0.2); }"
        )
        self._settings_btn.clicked.connect(self._open_settings)
        hdr.addWidget(self._settings_btn)
        hdr.addWidget(self._close_btn)

        # Chat list (bubbles)
        self._chat_list = QListWidget()
        self._chat_list.setStyleSheet(
            "QListWidget { background: #ffffff; border: none; border-radius: 0px; }"
            "QListWidget::item { border: none; padding: 2px 4px; }"
        )
        self._chat_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._streaming_label = None

        # Input row
        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Type a message...")
        self._input_field.setStyleSheet(
            "QLineEdit { border:2px solid #ddd; border-radius:15px;"
            " padding:8px 14px; background:rgba(0,0,0,0.7);"
            " color:white; font-size:13px; }"
            "QLineEdit:focus { border-color:#4CAF50; }"
        )
        self._input_field.returnPressed.connect(self._on_send)
        self._send_btn = QPushButton("\u27a4")
        self._send_btn.setFixedSize(38, 38)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:19px;"
            " background:#4CAF50; color:white; font-size:18px; }"
            "QPushButton:hover { background:#388E3C; }"
            "QPushButton:pressed { background:#2E7D32; }"
        )
        self._send_btn.clicked.connect(self._on_send)

        inp = QHBoxLayout()
        inp.setContentsMargins(8, 4, 8, 8)
        inp.addWidget(self._input_field, 1)
        inp.addWidget(self._send_btn)

        self._container = QFrame(self)
        self._container.setObjectName("chatBG")
        self._container.setStyleSheet(
            "#chatBG { background: #ffffff; border-radius: 16px; }"
        )
        self._container.setGeometry(0, 0, self.CHAT_W, self.CHAT_H)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._container)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(hdr)
        layout.addWidget(self._chat_list, 1)
        layout.addLayout(inp)

        # Pulse timer
        self._pulse_timer = QTimer(self)
        # Load personality from QSettings
        self._personality = QSettings("MyApp", "AIDesktopPet").value(
            "personality", "", str
        )
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_timer.start(600)

        # WebSocket
        self._ws = QWebSocket()
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.disconnected.connect(self._on_ws_disconnected)
        self._ws.error.connect(self._on_ws_error)
        self._connect_timer = QTimer(self)
        self._connect_timer.setSingleShot(True)
        self._connect_timer.timeout.connect(self._retry_ws)
        self._add_sys("Connecting to backend...")
        self._ws.open(QUrl(_ws_url()))

    def add_message_bubble(self, text, role="user"):
        """Add a rounded bubble to the chat list.

        role="user"   -> green, right, avatar
        role="ai"     -> gray,  left,  avatar
        role="system" -> center, italic
        """
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.setSpacing(6)

        avatar = QLabel("\U0001f464" if role == "user" else "\U0001f916")
        avatar.setFixedSize(24, 24)
        avatar.setStyleSheet("font-size:16px;")

        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(240)

        if role == "user":
            label.setStyleSheet(
                "background:#4CAF50; color:white; border-radius:10px;"
                " padding:8px 12px; font-size:13px;"
            )
            lay.addStretch()
            lay.addWidget(label)
            lay.addWidget(avatar)
        elif role == "ai":
            label.setStyleSheet(
                "background:#E8E8E8; color:#333; border-radius:10px;"
                " padding:8px 12px; font-size:13px;"
            )
            lay.addWidget(avatar)
            lay.addWidget(label)
            lay.addStretch()
        else:
            label.setStyleSheet(
                "color:#999; font-style:italic; font-size:11px;"
            )
            lay.addStretch()
            lay.addWidget(label)
            lay.addStretch()

        item = QListWidgetItem()
        self._chat_list.addItem(item)
        self._chat_list.setItemWidget(item, row)
        item.setSizeHint(row.sizeHint())
        self._chat_list.scrollToBottom()
        return label

    def _add_sys(self, text):
        self.add_message_bubble(text, "system")

    def _append_stream(self, text, role="ai"):
        if self._streaming_label is None:
            self._streaming_label = self.add_message_bubble("", role)
        old = self._streaming_label.text()
        self._streaming_label.setText(old + text)
        idx = self._chat_list.count() - 1
        if idx >= 0:
            it = self._chat_list.item(idx)
            w = self._chat_list.itemWidget(it)
            if w:
                it.setSizeHint(w.sizeHint())
        self._chat_list.scrollToBottom()

    def _finalize(self, text):
        if self._streaming_label is not None:
            pass  # streaming: label already has accumulated text
        elif text:
            # Non-streaming (reply) or no tokens: create full-text bubble
            self.add_message_bubble(text, "ai")
        self._streaming_label = None

    def _on_ws_error(self, error_code):
        """Handle WebSocket connection failure and retry."""
        self._add_sys("Connection failed. Retrying in 5s...")
        self._connect_timer.start(5000)

    def _on_ws_connected(self):
        self._add_sys("Connected.")

    def _on_ws_disconnected(self):
        self._add_sys("Disconnected. Retrying...")
        self._connect_timer.start(3000)

    def _open_settings(self):
        """Open the settings dialog; reload personality + icon on save."""
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            s = QSettings("MyApp", "AIDesktopPet")
            self._personality = s.value("personality", "", str)
            if self._parent_win is not None:
                self._parent_win._reload_custom_icon()

    def _retry_ws(self):
        self._ws.open(QUrl(_ws_url()))

    def _pulse_tick(self):
        if self._ws.state() == QAbstractSocket.ConnectedState:
            self._pulse_on = not self._pulse_on
            c = "#4CAF50" if self._pulse_on else "#66BB6A"
            self._status_dot.setStyleSheet(
                "background:{}; border-radius:5px;".format(c)
            )
        else:
            self._status_dot.setStyleSheet(
                "background:#999; border-radius:5px;"
            )

    def send_idle_greeting(self):
        """Send a proactive greeting via WebSocket (no user bubble shown)."""
        if self._ws.state() != QAbstractSocket.ConnectedState:
            return
        self._ws.sendTextMessage(
            __import__("json").dumps({
                "content": "用户已有一段时间没有操作了，请主动打个招呼，语气要友好",
                "stream": True,
            })
        )

    def _on_user_message(self, text):
        if self._ws.state() != QAbstractSocket.ConnectedState:
            self._add_sys("Backend offline. Start: uvicorn backend.main:app")
            return
        self._ws.sendTextMessage(
            __import__("json").dumps({
                "content": text,
                "stream": self._stream_cb.isChecked(),
                "personality": self._personality
            })
        )

    def _on_send(self):
        text = self._input_field.text().strip()
        if not text:
            return
        self._input_field.clear()
        self.add_message_bubble(text, "user")
        self._on_user_message(text)

    def _on_ws_message(self, raw):
        try:
            data = __import__("json").loads(raw)
        except Exception:
            return
        t = data.get("type")
        c = data.get("content", "")
        if t in ("token", "delta"):
            self._append_stream(c)
        elif t in ("done", "reply"):
            self._finalize(c)
        elif t == "thinking":
            self._add_sys(c)
        elif t == "tool_call":
            self._add_sys("[Tool] Calling " + data.get("tool", "?") + "...")
        elif t == "tool_result":
            self._add_sys("[Tool] " + (c[:120] if c else ""))
        elif t == "error":
            self._add_sys("[Error] " + c)

class SettingsDialog(QDialog):
    """Settings panel — personality prompt + pet icon editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\u8bbe\u7f6e")
        self.setFixedSize(440, 480)
        self.setModal(True)
        self._selected_icon = None  # QPixmap or None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("\u8bbe\u7f6e")
        title.setStyleSheet("font-size:18px; font-weight:600; color:#1a1a2e;")
        layout.addWidget(title)

        # ---- Personality ----
        lbl = QLabel("\u6027\u683c Prompt\uff1a")
        lbl.setStyleSheet("font-size:13px; font-weight:500; color:#333;")
        layout.addWidget(lbl)

        self._editor = QPlainTextEdit()
        self._editor.setFixedHeight(80)
        self._editor.setStyleSheet(
            "QPlainTextEdit { border:1px solid #ddd; border-radius:8px; "
            "padding:8px; font-size:13px; }"
            "QPlainTextEdit:focus { border-color:#4CAF50; }"
        )
        layout.addWidget(self._editor)

        hint = QLabel("\u7559\u7a7a\u5219\u4f7f\u7528\u9ed8\u8ba4\u52a9\u624b\u6027\u683c\u3002")
        hint.setStyleSheet("font-size:11px; color:#999;")
        layout.addWidget(hint)

        # ---- Pet Icon ----
        grp = QGroupBox("\u5ba0\u7269\u5f62\u8c61")
        grp.setStyleSheet("font-size:13px; font-weight:500;")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(10)

        icon_row = QHBoxLayout()
        self._preview = QLabel()
        self._preview.setFixedSize(60, 60)
        self._preview.setStyleSheet(
            "border:2px solid #ddd; border-radius:8px; background:#f9f9f9;"
        )
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setText("\U0001f431")
        self._preview.setStyleSheet(
            self._preview.styleSheet()
            + " font-size:32px;"
        )
        icon_row.addWidget(self._preview)

        btn_col = QVBoxLayout()
        self._select_btn = QPushButton("\u9009\u62e9\u56fe\u7247")
        self._select_btn.setCursor(Qt.PointingHandCursor)
        self._select_btn.setStyleSheet(
            "QPushButton { border:1px solid #4CAF50; border-radius:6px; "
            "padding:6px 16px; background:white; color:#4CAF50; font-size:13px; }"
            "QPushButton:hover { background:#E8F5E9; }"
        )
        self._select_btn.clicked.connect(self._on_select_icon)

        self._reset_btn = QPushButton("\u91cd\u7f6e")
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        self._reset_btn.setStyleSheet(
            "QPushButton { border:1px solid #ccc; border-radius:6px; "
            "padding:6px 16px; background:white; color:#666; font-size:13px; }"
            "QPushButton:hover { background:#f5f5f5; }"
        )
        self._reset_btn.clicked.connect(self._on_reset_icon)

        btn_col.addWidget(self._select_btn)
        btn_col.addWidget(self._reset_btn)
        btn_col.addStretch()
        icon_row.addLayout(btn_col)
        icon_row.addStretch()
        grp_layout.addLayout(icon_row)

        icon_hint = QLabel(
            "\u56fe\u7247\u5c06\u4fdd\u5b58\u5230\u672c\u5730\u8bbe\u7f6e\uff0c"
            "\u5ba0\u7269\u7a97\u548c\u804a\u5929\u7a97\u56fe\u6807\u90fd\u4f1a\u6539\u53d8"
        )
        icon_hint.setStyleSheet("font-size:11px; color:#999;")
        icon_hint.setWordWrap(True)
        grp_layout.addWidget(icon_hint)

        layout.addWidget(grp)
        layout.addStretch(1)

        # ---- Buttons ----
        self._save_btn = QPushButton("\u4fdd\u5b58")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setStyleSheet(
            "QPushButton { border:none; border-radius:6px; padding:8px 24px; "
            "background:#4CAF50; color:white; font-size:13px; }"
            "QPushButton:hover { background:#388E3C; }"
        )
        self._save_btn.clicked.connect(self._on_save)

        self._cancel_btn = QPushButton("\u53d6\u6d88")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet(
            "QPushButton { border:1px solid #ccc; border-radius:6px; padding:8px 24px; "
            "background:white; color:#333; font-size:13px; }"
            "QPushButton:hover { background:#f5f5f5; }"
        )
        self._cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        # Load existing values from QSettings
        s = QSettings("MyApp", "AIDesktopPet")
        saved_p = s.value("personality", "", str)
        if saved_p:
            self._editor.setPlainText(saved_p)
        saved_icon = s.value("pet_icon_data", "", str)
        if saved_icon:
            pm = _b64_to_icon(saved_icon)
            if pm and not pm.isNull():
                self._selected_icon = pm
                thumb = pm.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._preview.setPixmap(thumb)
                self._preview.setText("")

    def _on_select_icon(self):
        """Open file dialog to choose a pet image."""
        fpath, _ = QFileDialog.getOpenFileName(
            self, "\u9009\u62e9\u5ba0\u7269\u56fe\u7247", "",
            "\u56fe\u7247 (*.png *.jpg *.jpeg *.gif)"
        )
        if not fpath:
            return
        pm = QPixmap(fpath)
        if pm.isNull():
            return
        self._selected_icon = pm
        thumb = pm.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._preview.setPixmap(thumb)
        self._preview.setText("")

    def _on_reset_icon(self):
        """Reset icon to default (emoji cat face)."""
        self._selected_icon = None
        self._preview.setText("\U0001f431")
        self._preview.setPixmap(QPixmap())

    def _on_save(self):
        """Save personality + pet icon to QSettings and accept."""
        s = QSettings("MyApp", "AIDesktopPet")
        s.setValue("personality", self._editor.toPlainText())
        if self._selected_icon is not None:
            s.setValue("pet_icon_data", _icon_to_b64(self._selected_icon))
        else:
            s.remove("pet_icon_data")
        s.sync()
        self.accept()



class PetWindow(QMainWindow):
    """Frameless transparent pet with day/night images, jelly click, and chat."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Background painted by QFrame container
        self.setFixedSize(SIZE)

        self._label = _PetLabel(self)
        self._label.setGeometry(0, 0, SIZE.width(), SIZE.height())
        self._label.clicked.connect(self._on_click)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._chat = None
        self._phase = None
        self._custom_icon_active = False
        self._apply_phase()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._apply_phase)
        self._timer.start(60_000)
        self._apply_custom_icon()
        self._setup_animator()
        self._last_idle_greeting = 0.0
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._check_idle)
        self._idle_timer.start(300_000)  # 5 min

    # -- Day / night ------------------------------------------------

    def _compute_phase(self):
        hour = QTime.currentTime().hour()
        return "night" if hour >= 18 or hour < 6 else "day"

    def _check_idle(self):
        """Check idle time; send proactive greeting if user is AFK."""
        idle = get_idle_seconds()
        if idle < 600:  # less than 10 min
            return
        if idle > 3600:  # likely API error
            return
        import time
        now = time.time()
        if now - self._last_idle_greeting < 300:  # already greeted in 5 min
            return
        self._last_idle_greeting = now
        # Open chat if needed, then send greeting
        if self._chat is None or not self._chat.isVisible():
            self._toggle_chat()
            QTimer.singleShot(2500, self._do_idle_greeting)
        else:
            self._do_idle_greeting()

    def _do_idle_greeting(self):
        """Send idle greeting via the active ChatDialog."""
        if self._chat is not None and self._chat.isVisible():
            self._chat.send_idle_greeting()

    def _setup_animator(self):
        """Detect resources and create pet animator."""
        res = detect_animation_resources(IMG_DIR)
        saved = QSettings("MyApp", "AIDesktopPet").value("pet_icon_data", "", str)
        rt = "single_image" if saved else res["type"]
        self.animator = PetAnimator(
            label=self._label, window=self,
            resource_type=rt, folder=res["config"]["folder"],
        )

    def _rebuild_animator(self):
        """Hot-swap after user uploads/resets image."""
        res = detect_animation_resources(IMG_DIR)
        saved = QSettings("MyApp", "AIDesktopPet").value("pet_icon_data", "", str)
        rt = "single_image" if saved else res["type"]
        a = getattr(self, 'animator', None)
        if a is not None:
            a.hot_swap(rt, folder=res["config"]["folder"])
        else:
            self._setup_animator()
        self._last_idle_greeting = 0.0
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._check_idle)
        self._idle_timer.start(300_000)  # 5 min

    def _apply_phase(self):
        if self._custom_icon_active:
            return
        new = self._compute_phase()
        if new == self._phase:
            return
        self._phase = new
        pix = self._load_pixmap(new)
        scaled = pix.scaled(SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(scaled)

    def _apply_custom_icon(self, pm=None):
        """Set custom pet image; stop day/night timer."""
        if pm is not None:
            self._custom_icon_active = True
            scaled = pm.scaled(SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._label.setPixmap(scaled)
            self._timer.stop()
            return
        # No custom icon passed: check QSettings
        saved = QSettings("MyApp", "AIDesktopPet").value(
            "pet_icon_data", "", str
        )
        if saved:
            pm = _b64_to_icon(saved)
            if pm and not pm.isNull():
                self._custom_icon_active = True
                scaled = pm.scaled(SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._label.setPixmap(scaled)
                self._timer.stop()
                return
        # No custom icon: ensure day/night is active
        self._custom_icon_active = False
        self._phase = None
        self._timer.start()
        self._apply_phase()

    def _reload_custom_icon(self):
        """Re-read QSettings, apply icon, and rebuild animator."""
        self._apply_custom_icon()
        self._rebuild_animator()

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
        a = getattr(self, 'animator', None)
        if a is not None:
            a.transition_to(PetState.CLICKED)
        else:
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
        # Close existing chat
        if self._chat is not None:
            old = self._chat
            self._chat = None  # clear FIRST so _on_click can't re-enter
            old.close()
            old.deleteLater()
            return

        # Create new chat (use local var to avoid race with destroyed signal)
        dlg = ChatDialog(self.geometry().topLeft())
        dlg.destroyed.connect(self._on_chat_destroyed)
        dlg.show()
        self._chat = dlg

    def _on_chat_destroyed(self):
        try:
            if self._chat is not None and hasattr(self._chat, 'isVisible') and not self._chat.isVisible():
                self._chat = None
        except (RuntimeError, Exception):
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
