"""Perception utilities — screen capture and active window detection."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

# ── Lazy imports ─────────────────────────────────────────────
try:
    import pygetwindow as gw
except ImportError:
    gw = None  # type: ignore

try:
    import pyautogui
except ImportError:
    pyautogui = None  # type: ignore

from PIL import Image


# Entertainment keywords (case-insensitive)
ENTERTAINMENT_KEYWORDS = [
    "youtube",
    "哔哩哔哩",
    "bilibili",
    "twitch",
    "netflix",
    "steam",
    "游戏",
    "game",
    "douyin",
    "tiktok",
    "spotify",
]


def is_entertainment_app(title: str | None) -> bool:
    """Return True if *title* contains entertainment-related keywords."""
    if not title:
        return False
    lower = title.lower()
    return any(kw in lower for kw in ENTERTAINMENT_KEYWORDS)


# ── Active window ─────────────────────────────────────────────

def get_active_window_title() -> str | None:
    """Return the title of the currently active foreground window.

    Returns None if no window is active or the library is unavailable.
    """
    if gw is None:
        return None
    try:
        win = gw.getActiveWindow()
        if win is None:
            return None
        title = win.title
        return title if title else None
    except Exception:
        return None


# ── Screen capture ────────────────────────────────────────────

def capture_screen() -> Image.Image | None:
    """Capture the full screen and return a PIL Image.

    Returns None if pyautogui is unavailable.
    """
    if pyautogui is None:
        return None
    try:
        return pyautogui.screenshot()
    except Exception:
        return None


def capture_screen_and_save(path: str | Path | None = None) -> str | None:
    """Capture the full screen and save to *path* (or auto-generate one).

    Auto-generated path format:  ``screenshots/YYYYMMDD_HHMMSS.png``

    Returns the file path on success, or None on failure.
    """
    img = capture_screen()
    if img is None:
        return None

    if path is None:
        folder = Path.cwd() / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = folder / f"{ts}.png"

    try:
        img.save(str(path))
        return str(path)
    except Exception:
        return None


# Window classification

PROGRAMMING_KEYWORDS = [
    "vscode", "visual studio", "visualstudio", "code",
    "pycharm", "intellij", "idea", "webstorm", "goland", "datagrip",
    "eclipse", "xcode", "android studio", "androidstudio",
    "github", "gitlab", "stack overflow", "stackoverflow",
    "terminal", "cmd", "powershell", "wsl", "bash",
    "终端", "命令行",
    "jupyter", "notebook", "python", "javascript", "typescript",
    "docker", "kubernetes", "k8s", "vim", "neovim", "emacs",
    "sublime", "atom", "clion", "rider", "rust",
]

OFFICE_KEYWORDS = [
    "word", "excel", "powerpoint", "ppt", "outlook", "onenote",
    "钉钉", "dingtalk", "飞书", "feishu", "lark",
    "teams", "microsoft teams", "slack", "discord",
    "邮件", "mail", "thunderbird", "foxmail",
    "wps", "企业微信", "wecom",
    "notion", "evernote", "印象笔记",
]


def classify_window(title: str | None) -> str:
    """Classify a window title into a category.

    Returns one of:
        "programming"   - IDE, terminal, GitHub, etc.
        "entertainment"  - Bilibili, YouTube, Steam, etc.
        "office"         - Word, Excel, Teams, DingTalk, etc.
        "other"          - unrecognised / empty
    """
    if not title:
        return "other"

    if is_entertainment_app(title):
        return "entertainment"

    lower = title.lower()
    for kw in PROGRAMMING_KEYWORDS:
        if kw in lower:
            return "programming"
    for kw in OFFICE_KEYWORDS:
        if kw in lower:
            return "office"
    return "other"
