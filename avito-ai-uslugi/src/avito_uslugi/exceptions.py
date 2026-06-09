"""Исключения обёртки Avito API."""

from __future__ import annotations

import httpx


class AvitoAPIError(Exception):
    """Ошибка ответа Avito API (статус >= 400) или сетевой ошибки после ретраев."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: object | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload

    @classmethod
    def from_response(cls, response: httpx.Response) -> "AvitoAPIError":
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        message = f"Avito API вернул {response.status_code} для {response.request.method} {response.request.url}: {payload}"
        return cls(message, status_code=response.status_code, payload=payload)


class AvitoAuthError(AvitoAPIError):
    """Ошибка получения/обновления токена доступа (POST /token)."""
