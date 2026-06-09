"""OAuth client_credentials для Avito API с кэшированием токена по expires_in.

Источник: https://developers.avito.ru/api-catalog/auth/documentation
(POST https://api.avito.ru/token, grant_type=client_credentials).
"""

from __future__ import annotations

import time

import httpx

from .exceptions import AvitoAuthError

TOKEN_URL = "https://api.avito.ru/token"

# Обновляем токен немного раньше истечения, чтобы не словить 401 в середине запроса.
EXPIRY_SAFETY_MARGIN_SECONDS = 60


class TokenCache:
    """Хранит access_token в памяти и считает его действительным до expires_in - margin."""

    def __init__(self, *, safety_margin: int = EXPIRY_SAFETY_MARGIN_SECONDS, clock=time.monotonic):
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._safety_margin = safety_margin
        self._clock = clock

    def get(self) -> str | None:
        if self._token is not None and self._clock() < self._expires_at:
            return self._token
        return None

    def store(self, access_token: str, expires_in: int) -> None:
        self._token = access_token
        self._expires_at = self._clock() + max(expires_in - self._safety_margin, 0)

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0


def fetch_access_token(http: httpx.Client, client_id: str, client_secret: str) -> tuple[str, int]:
    """Запрашивает новый access_token по client_credentials. Возвращает (token, expires_in)."""
    response = http.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if response.status_code >= 400:
        raise AvitoAuthError.from_response(response)

    payload = response.json()
    try:
        return payload["access_token"], int(payload["expires_in"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AvitoAuthError(
            f"Неожиданный формат ответа /token: {payload}", status_code=response.status_code, payload=payload
        ) from exc
