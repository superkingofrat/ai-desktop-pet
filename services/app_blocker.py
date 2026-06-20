"""Process blacklist detection and termination for focus mode.

Provides utilities to find running blacklisted processes and
attempt graceful termination (with fallback to force-kill).
"""

from __future__ import annotations

import logging
import sys
import json
from pathlib import Path
from typing import List

import psutil

logger = logging.getLogger(__name__)


def get_blacklist_processes(blacklist: list[str]) -> list[psutil.Process]:
    found: list[psutil.Process] = []
    lower_keywords = [kw.strip().lower() for kw in blacklist if kw.strip()]
    if not lower_keywords:
        return found
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc_name = proc.info.get('name') or proc.name() or ''
            proc_name_lower = proc_name.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        for keyword in lower_keywords:
            if keyword in proc_name_lower:
                found.append(proc)
                break
    return found


def terminate_processes(processes: list[psutil.Process]) -> int:
    success_count = 0
    for proc in processes:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                logger.warning('Process %d (%s) did not exit gracefully, killing...', proc.pid, proc.name())
                proc.kill()
                proc.wait(timeout=2)
            success_count += 1
            logger.info('Terminated process %d (%s)', proc.pid, proc.name())
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            logger.warning('Could not terminate process %d: %s', proc.pid, exc)
        except Exception:
            logger.exception('Unexpected error terminating process %d', proc.pid)
    return success_count


def get_process_display_name(proc: psutil.Process) -> str:
    try:
        exe_path = proc.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return proc.name()
    if sys.platform != 'win32':
        return proc.name()
    try:
        import win32api
        bs = chr(92)
        sk = bs + 'StringFileInfo' + bs
        lp = win32api.GetFileVersionInfo(exe_path, bs + 'VarFileInfo' + bs + 'Translation')
        if not lp:
            return proc.name()
        lang, cp = lp[0]
        for key in ('FileDescription', 'ProductName', 'InternalName'):
            try:
                val = win32api.GetFileVersionInfo(exe_path, sk + f'{lang:04X}{cp:04X}' + bs + key)
                if val:
                    return val
            except Exception:
                continue
    except ImportError:
        pass
    except Exception:
        pass
    return proc.name()


BLACKLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "blacklist.json"

_DEFAULT_BLACKLIST = [
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe",
    "sogouexplorer.exe", "360se.exe", "qqbrowser.exe",
    "wechat.exe", "qq.exe", "tim.exe", "dingtalk.exe", "feishu.exe",
    "steam.exe", "epicgameslauncher.exe", "leagueclient.exe",
    "dota2.exe", "overwatch.exe", "wow.exe",
    "genshinimpact.exe", "douyu.exe", "huya.exe", "twitch.exe",
    "potplayer.exe", "vlc.exe", "kugou.exe",
    "qqmusic.exe", "spotify.exe", "neteasemusic.exe",
    "bilibili.exe", "douyin.exe", "tiktok.exe",
    "wegame.exe", "thunder.exe",
    "obs64.exe", "teamviewer.exe", "todesk.exe",
    "foxmail.exe", "thunderbird.exe",
]


def load_blacklist() -> list[str]:
    if not BLACKLIST_PATH.exists():
        return list(_DEFAULT_BLACKLIST)
    try:
        data = json.loads(BLACKLIST_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return [n.strip().lower() for n in data if n.strip()]
    except Exception:
        pass
    return list(_DEFAULT_BLACKLIST)


def save_blacklist(blacklist: list[str]) -> None:
    BLACKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLACKLIST_PATH.write_text(
        json.dumps(blacklist, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
