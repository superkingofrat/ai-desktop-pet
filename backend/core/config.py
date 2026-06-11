"""Application configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Global application settings."""

    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # DeepSeek
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))

    # Database
    db_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/assistant.db"))

    # Agent
    max_tool_iterations: int = 10
    max_history_size: int = 40


settings = Settings()
