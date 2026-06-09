"""Загрузка конфигурации из .env. Секреты живут только в .env (см. .gitignore)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

REQUIRED_VARS = ("AVITO_CLIENT_ID", "AVITO_CLIENT_SECRET")


@dataclass(frozen=True)
class Settings:
    avito_client_id: str
    avito_client_secret: str
    avito_webhook_secret: str | None
    anthropic_api_key: str | None
    telegram_bot_token: str | None
    telegram_owner_chat_id: str | None

    @classmethod
    def from_env(cls, *, env_file: str | None = None) -> "Settings":
        load_dotenv(env_file)
        missing = [name for name in REQUIRED_VARS if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "Не заданы переменные окружения: "
                f"{', '.join(missing)}. Заполните .env по образцу .env.example."
            )
        return cls(
            avito_client_id=os.environ["AVITO_CLIENT_ID"],
            avito_client_secret=os.environ["AVITO_CLIENT_SECRET"],
            avito_webhook_secret=os.getenv("AVITO_WEBHOOK_SECRET") or None,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_owner_chat_id=os.getenv("TELEGRAM_OWNER_CHAT_ID") or None,
        )
