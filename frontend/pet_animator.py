"""Pet state-machine animation system — single image, frame sequence & spritesheet."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from enum import Enum, auto
from pathlib import Path
from typing import Any

from PyQt5.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
)
from PyQt5.QtGui import QPixmap

# ═══════════════════════════════════════════════════════════════
# Pet state enum
# ═══════════════════════════════════════════════════════════════

class PetState(Enum):
    IDLE = auto()
    THINKING = auto()
    SPEAKING = auto()
    CLICKED = auto()


# ═══════════════════════════════════════════════════════════════
# Abstract animator base
# ═══════════════════════════════════════════════════════════════

class BaseAnimator(ABC):
    """Abstract interface every animator subclass must implement."""

    def __init__(self, label, window=None):
        self._label = label        # QLabel that displays the pet
        self._window = window      # PetWindow (for geometry animation)
        self._current_state = PetState.IDLE
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_tick)
        self._interval_ms = 200

    # ── Public API ─────────────────────────────────────────

    @abstractmethod
    def transition_to(self, state: PetState) -> None:
        """Switch to a new state and play the corresponding animation."""
        ...

    def set_interval(self, ms: int) -> None:
        """Change the timer interval for frame-based animations."""
        self._interval_ms = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    @property
    def current_state(self) -> PetState:
        return self._current_state

    def stop(self) -> None:
        self._timer.stop()

    def start(self) -> None:
        self._timer.start(self._interval_ms)

    # ── Internal ───────────────────────────────────────────

    def _on_tick(self):
        """Override in subclasses for frame-stepping or periodic effects."""
        pass


# ═══════════════════════════════════════════════════════════════
# Single-image animator (jelly click + idle floating / pulse)
# ═══════════════════════════════════════════════════════════════

class SingleImageAnimator(BaseAnimator):
    """Animates a single static pet image with transform effects."""

    def __init__(self, label, window=None):
        super().__init__(label, window)
        self._jelly_group = None
        self._pulse_effect = None
        self._pulse_anim = None

    # ── State machine ───────────────────────────────────────

    def transition_to(self, state: PetState) -> None:
        self._current_state = state

        self._stop_all()

        if state == PetState.CLICKED:
            self._play_jelly()
        elif state == PetState.IDLE:
            self._play_idle_pulse()
        elif state == PetState.THINKING:
            self._play_idle_pulse()   # same pulse, just uses default interval
        elif state == PetState.SPEAKING:
            self._play_idle_pulse()

    # ── Jelly click ─────────────────────────────────────────

    def _play_jelly(self) -> None:
        win = self._window
        if win is None:
            return
        geo = win.geometry()
        w, h = geo.width(), geo.height()
        nw, nh = int(w * 1.15), int(h * 1.15)
        dx, dy = (nw - w) // 2, (nh - h) // 2
        expanded = QRect(geo.x() - dx, geo.y() - dy, nw, nh)

        a1 = QPropertyAnimation(win, b"geometry")
        a1.setDuration(50)
        a1.setStartValue(geo)
        a1.setEndValue(expanded)

        a2 = QPropertyAnimation(win, b"geometry")
        a2.setDuration(100)
        a2.setStartValue(expanded)
        a2.setEndValue(geo)
        a2.setEasingCurve(QEasingCurve.OutBounce)

        g = QSequentialAnimationGroup(win)
        g.addAnimation(a1)
        g.addAnimation(a2)
        g.finished.connect(lambda: self.transition_to(PetState.IDLE))
        g.start(QAbstractAnimation.DeleteWhenStopped)
        self._jelly_group = g

    # ── Idle pulse (subtle opacity breathing) ───────────────

    def _play_idle_pulse(self) -> None:
        from PyQt5.QtWidgets import QGraphicsOpacityEffect

        effect = QGraphicsOpacityEffect(self._label)
        self._label.setGraphicsEffect(effect)
        self._pulse_effect = effect

        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(2000)
        anim.setStartValue(1.0)
        anim.setEndValue(0.82)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setLoopCount(-1)  # infinite
        anim.start()
        self._pulse_anim = anim

    # ── Cleanup ─────────────────────────────────────────────

    def _stop_all(self) -> None:
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim = None
        if self._pulse_effect is not None:
            self._label.setGraphicsEffect(None)
            self._pulse_effect = None
        self._timer.stop()


# ═══════════════════════════════════════════════════════════════
# Frame-sequence animator (separate PNG files per state)
# ═══════════════════════════════════════════════════════════════

class FrameSequenceAnimator(BaseAnimator):
    """Cycles through numbered frame files: idle_1.png, idle_2.png …"""

    STATE_DIRS = ("idle", "thinking", "speaking", "clicked")

    def __init__(self, label, window=None, frame_map=None):
        super().__init__(label, window)
        # frame_map: {PetState: [QPixmap, ...]}
        self._frames: dict[PetState, list[QPixmap]] = frame_map or {}
        self._current_frames: list[QPixmap] = []
        self._frame_idx = 0
        self._click_played = False

    # ── Factory: scan folder ────────────────────────────────

    @classmethod
    def from_folder(cls, label, folder: Path, window=None):
        """Scan *folder* for files matching ``{state}_N.png``."""
        frame_map: dict[PetState, list[QPixmap]] = {}
        state_to_enum = {
            "idle": PetState.IDLE,
            "thinking": PetState.THINKING,
            "speaking": PetState.SPEAKING,
            "clicked": PetState.CLICKED,
        }

        if not folder.exists():
            return cls(label, window)

        for prefix, state in state_to_enum.items():
            pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)\.png$", re.I)
            matches = []
            for fname in os.listdir(str(folder)):
                m = pattern.match(fname)
                if m:
                    matches.append((int(m.group(1)), str(folder / fname)))
            if matches:
                matches.sort()
                pixmaps = [QPixmap(p) for _, p in matches]
                pixmaps = [p for p in pixmaps if not p.isNull()]
                if pixmaps:
                    frame_map[state] = pixmaps

        return cls(label, window, frame_map)

    # ── State machine ───────────────────────────────────────

    def transition_to(self, state: PetState) -> None:
        self._current_state = state
        self._frame_idx = 0
        self._click_played = False

        frames = self._frames.get(state, self._frames.get(PetState.IDLE, []))

        if not frames:
            return

        self._current_frames = frames
        self._show_frame()

        # CLICKED plays once then goes back to IDLE
        if state == PetState.CLICKED:
            self.set_interval(80)
        else:
            self.set_interval(200)
        self.start()

    def _show_frame(self) -> None:
        if not self._current_frames:
            return
        idx = self._frame_idx % len(self._current_frames)
        self._label.setPixmap(
            self._current_frames[idx].scaled(
                self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        )

    def _on_tick(self) -> None:
        if not self._current_frames:
            return

        self._frame_idx += 1

        # CLICKED: play once then idle
        if self._current_state == PetState.CLICKED:
            if self._frame_idx >= len(self._current_frames):
                self._click_played = True
                self.transition_to(PetState.IDLE)
                return

        self._show_frame()


# ═══════════════════════════════════════════════════════════════
# Spritesheet animator (single large image + JSON metadata)
# ═══════════════════════════════════════════════════════════════

class SpritesheetAnimator(BaseAnimator):
    """Crops frames from a spritesheet using JSON metadata."""

    def __init__(self, label, window=None, spritesheet_pm=None, json_data=None):
        super().__init__(label, window)
        # {PetState: [QPixmap, ...]}
        self._frames: dict[PetState, list[QPixmap]] = {}
        self._current_frames: list[QPixmap] = []
        self._frame_idx = 0
        self._click_played = False

        if spritesheet_pm is not None and json_data is not None:
            self._parse(spritesheet_pm, json_data)

    def _parse(self, sheet: QPixmap, data: dict) -> None:
        state_to_enum = {
            "idle": PetState.IDLE,
            "thinking": PetState.THINKING,
            "speaking": PetState.SPEAKING,
            "clicked": PetState.CLICKED,
        }

        raw_frames = data.get("frames", [])
        for entry in raw_frames:
            fname = entry.get("filename", "")
            for prefix, state in state_to_enum.items():
                if fname.startswith(prefix):
                    f = entry.get("frame", {})
                    x, y = f.get("x", 0), f.get("y", 0)
                    w, h = f.get("w", 1), f.get("h", 1)
                    cropped = sheet.copy(x, y, w, h)
                    if not cropped.isNull():
                        self._frames.setdefault(state, []).append(cropped)
                    break

    @classmethod
    def from_folder(cls, label, folder: Path, window=None):
        """Load ``spritesheet.png`` + ``spritesheet.json`` from *folder*."""
        img_path = folder / "spritesheet.png"
        meta_path = folder / "spritesheet.json"

        if not img_path.exists() or not meta_path.exists():
            return cls(label, window)

        sheet = QPixmap(str(img_path))
        if sheet.isNull():
            return cls(label, window)

        try:
            with open(str(meta_path), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, Exception):
            return cls(label, window)

        obj = cls(label, window)
        obj._parse(sheet, data)
        return obj

    # ── State machine ───────────────────────────────────────

    def transition_to(self, state: PetState) -> None:
        self._current_state = state
        self._frame_idx = 0
        self._click_played = False

        frames = self._frames.get(state, self._frames.get(PetState.IDLE, []))
        if not frames:
            return

        self._current_frames = frames
        self._show_frame()

        if state == PetState.CLICKED:
            self.set_interval(80)
        else:
            self.set_interval(200)
        self.start()

    def _show_frame(self) -> None:
        if not self._current_frames:
            return
        idx = self._frame_idx % len(self._current_frames)
        self._label.setPixmap(
            self._current_frames[idx].scaled(
                self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        )

    def _on_tick(self) -> None:
        if not self._current_frames:
            return
        self._frame_idx += 1
        if self._current_state == PetState.CLICKED:
            if self._frame_idx >= len(self._current_frames):
                self._click_played = True
                self.transition_to(PetState.IDLE)
                return
        self._show_frame()


# ═══════════════════════════════════════════════════════════════
# Unified wrapper (auto-selects best animator)
# ═══════════════════════════════════════════════════════════════

class PetAnimator(BaseAnimator):
    """Auto-selects the best animator based on available resources.

    Delegates all calls to the inner animator instance.
    """

    def __init__(self, label, window=None, resource_type="single_image",
                 folder=None, qsettings_icon_b64=None):
        super().__init__(label, window)
        self._inner: BaseAnimator | None = None
        self._rebuild(resource_type, folder, qsettings_icon_b64)

    # ── Reconstruction (hot-swap on resource change) ────────

    def _rebuild(self, resource_type="single_image",
                 folder=None, qsettings_icon_b64=None) -> None:
        old = self._inner
        if old is not None:
            old.stop()

        label = self._label
        win = self._window

        if resource_type == "frame_sequence" and folder is not None:
            self._inner = FrameSequenceAnimator.from_folder(label, folder, win)
        elif resource_type == "spritesheet" and folder is not None:
            self._inner = SpritesheetAnimator.from_folder(label, folder, win)
        else:
            self._inner = SingleImageAnimator(label, win)

        self._inner.transition_to(PetState.IDLE)

    # ── Delegate ────────────────────────────────────────────

    def transition_to(self, state: PetState) -> None:
        if self._inner is not None:
            self._inner.transition_to(state)

    def set_interval(self, ms: int) -> None:
        if self._inner is not None:
            self._inner.set_interval(ms)

    def stop(self) -> None:
        if self._inner is not None:
            self._inner.stop()

    def start(self) -> None:
        if self._inner is not None:
            self._inner.start()

    @property
    def current_state(self) -> PetState:
        if self._inner is not None:
            return self._inner.current_state
        return PetState.IDLE

    def hot_swap(self, resource_type, folder=None, qsettings_icon_b64=None):
        """Call from main thread after user uploads new resources."""
        self._rebuild(resource_type, folder, qsettings_icon_b64)


# ═══════════════════════════════════════════════════════════════
# Resource detection
# ═══════════════════════════════════════════════════════════════

def detect_animation_resources(folder_path: str | Path) -> dict[str, Any]:
    """Scan *folder_path* and return detected resource type + config.

    Returns
    -------
    {"type": "single_image" | "frame_sequence" | "spritesheet", "config": {...}}
    """
    folder = Path(folder_path)

    # 1) Spritesheet ?
    if (folder / "spritesheet.png").exists() and (folder / "spritesheet.json").exists():
        return {"type": "spritesheet", "config": {"folder": folder}}

    # 2) Frame sequence ?
    has_frames = False
    for prefix in ("idle_", "thinking_", "speaking_", "clicked_"):
        if list(folder.glob(f"{prefix}*.png")):
            has_frames = True
            break
    if has_frames:
        return {"type": "frame_sequence", "config": {"folder": folder}}

    # 3) Default single image
    return {"type": "single_image", "config": {"folder": folder}}
