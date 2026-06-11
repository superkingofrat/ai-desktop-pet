"""Application configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Global application settings loaded from .env / environment."""

    # Server
    host: str = field(default_factory=lambda: os.getenv("BACKEND_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("BACKEND_PORT", "8000")))

    # WebSocket endpoint
    ws_chat_path: str = field(default_factory=lambda: os.getenv("WS_CHAT_PATH", "/ws/chat"))

    # DeepSeek
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))

    # Data directories
    host_data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "./data"))

    @property
    def data_dir(self) -> Path:
        return Path(self.host_data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "assistant.db"

    @property
    def cache_db_path(self) -> Path:
        return self.data_dir / "cache.db"

    # Legacy DB URL
    db_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))

    # Agent
    max_tool_iterations: int = 10
    max_history_size: int = 40


settings = Settings()
