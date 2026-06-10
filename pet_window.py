"""Desktop pet window — transparent, draggable, day/night images, jelly click."""

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
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QMenu


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


class PetWindow(QMainWindow):
    """Frameless transparent pet with day/night images + jelly click."""

    IMG_DIR = Path(__file__).resolve().parent / "images"
    SIZE = QSize(120, 120)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.SIZE)

        self._label = _PetLabel(self)
        self._label.setGeometry(0, 0, self.SIZE.width(), self.SIZE.height())
        self._label.clicked.connect(self._jelly_click)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._phase = None
        self._apply_phase()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._apply_phase)
        self._timer.start(60_000)

    # -- Day / night --------------------------------------------------
    def _compute_phase(self):
        hour = QTime.currentTime().hour()
        return "night" if hour >= 18 or hour < 6 else "day"

    def _apply_phase(self):
        new = self._compute_phase()
        if new == self._phase:
            return
        self._phase = new
        pix = self._load_pixmap(new)
        scaled = pix.scaled(self.SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(scaled)

    def _load_pixmap(self, phase):
        path = self.IMG_DIR / f"{phase}.png"
        if path.exists():
            return QPixmap(str(path))
        pm = QPixmap(self.SIZE)
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

    # -- Jelly click --------------------------------------------------
    def _jelly_click(self):
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

    # -- Context menu -------------------------------------------------
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


def main():
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("Desktop Pet")
    win = PetWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
