"""Тонкая обёртка над официальным Avito API (https://api.avito.ru).

Эндпоинты и поля взяты из актуальной документации developers.avito.ru
(каталоги auth / item / autoload / messenger), без выдумывания.

Реализованы только методы, перечисленные в промпте 2 пайплайна:
- OAuth client_credentials с кэшем токена (см. auth.py)
- items: список объявлений, статистика просмотров/контактов, apply_vas
- autoload: загрузка XML-фида, отчёты
- messenger: чаты, сообщения, отправка, подписки на вебхуки

Требуются скоупы: items:info, items:apply_vas, autoload:reports,
messenger:read, messenger:write — выпускаются вместе с client_id/client_secret
на https://www.avito.ru/professionals/api.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import httpx

from .auth import TokenCache, fetch_access_token
from .exceptions import AvitoAPIError

API_BASE_URL = "https://api.avito.ru"

# Коды ответа, при которых имеет смысл повторить запрос.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AvitoClient:
    """Авторизованный клиент Avito API с ретраями и автообновлением токена."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        http_client: httpx.Client | None = None,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
        sleep=time.sleep,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or httpx.Client(base_url=API_BASE_URL, timeout=20.0)
        self._tokens = TokenCache()
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep

        self.items = ItemsAPI(self)
        self.autoload = AutoloadAPI(self)
        self.messenger = MessengerAPI(self)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "AvitoClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Авторизация
    # ------------------------------------------------------------------
    def _access_token(self, *, force_refresh: bool = False) -> str:
        if force_refresh:
            self._tokens.invalidate()
        token = self._tokens.get()
        if token is None:
            token, expires_in = fetch_access_token(self._http, self._client_id, self._client_secret)
            self._tokens.store(token, expires_in)
        return token

    # ------------------------------------------------------------------
    # Низкоуровневый запрос с ретраями и обновлением токена по 401
    # ------------------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            request_headers = dict(headers or {})
            request_headers["Authorization"] = f"Bearer {self._access_token(force_refresh=False)}"

            try:
                response = self._http.request(
                    method, path, params=params, json=json, data=data, headers=request_headers
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    self._sleep(self._retry_backoff_seconds * attempt)
                    continue
                raise AvitoAPIError(f"Сетевая ошибка при запросе {method} {path}: {exc}") from exc

            if response.status_code == 401 and attempt < self._max_attempts:
                # Токен мог протухнуть досрочно — сбрасываем кэш и пробуем ещё раз.
                self._access_token(force_refresh=True)
                continue

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_attempts:
                self._sleep(self._retry_backoff_seconds * attempt)
                continue

            if response.status_code >= 400:
                raise AvitoAPIError.from_response(response)

            return response

        raise AvitoAPIError(
            f"Не удалось выполнить {method} {path} за {self._max_attempts} попыток: {last_error}"
        )

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PUT", path, **kwargs)


class _SubAPI:
    def __init__(self, client: AvitoClient):
        self._client = client


class ItemsAPI(_SubAPI):
    """core/v1 / core/v2 / stats — объявления, статистика, продвижение.

    Источник: https://developers.avito.ru/api-catalog/item/documentation
    """

    def list(
        self,
        *,
        per_page: int = 25,
        page: int = 1,
        category: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """GET /core/v1/items — список объявлений текущего пользователя (items:info)."""
        params: dict[str, Any] = {"per_page": per_page, "page": page}
        if category is not None:
            params["category"] = category
        if status is not None:
            params["status"] = status
        return self._client.get("/core/v1/items", params=params).json()

    def get(self, user_id: int, item_id: int) -> dict[str, Any]:
        """GET /core/v1/accounts/{user_id}/items/{item_id}/ — карточка объявления (items:info)."""
        return self._client.get(f"/core/v1/accounts/{user_id}/items/{item_id}/").json()

    def stats_shallow(
        self,
        user_id: int,
        item_ids: Iterable[int],
        *,
        date_from: str,
        date_to: str,
        fields: Iterable[str] = ("uniqViews", "uniqContacts"),
    ) -> dict[str, Any]:
        """POST /stats/v1/accounts/{user_id}/items — счётчики просмотров/контактов (stats:read).

        date_from / date_to — строки в формате YYYY-MM-DD.
        """
        payload = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "fields": list(fields),
            "itemIds": list(item_ids),
        }
        return self._client.post(f"/stats/v1/accounts/{user_id}/items", json=payload).json()

    def vas_prices(self, user_id: int, item_ids: Iterable[int]) -> dict[str, Any]:
        """POST /core/v1/accounts/{user_id}/vas/prices — цены платных услуг (items:apply_vas)."""
        return self._client.post(
            f"/core/v1/accounts/{user_id}/vas/prices", json={"ids": list(item_ids)}
        ).json()

    def apply_vas(self, item_id: int, vas_ids: Iterable[str]) -> dict[str, Any]:
        """PUT /core/v2/items/{item_id}/vas/ — применить продвижение к объявлению (items:apply_vas)."""
        return self._client.put(f"/core/v2/items/{item_id}/vas/", json={"vas": list(vas_ids)}).json()

    def update_price(self, item_id: int, price: int) -> dict[str, Any]:
        """POST /core/v1/items/{item_id}/update_price — обновить цену объявления (items:apply_vas)."""
        return self._client.post(f"/core/v1/items/{item_id}/update_price", json={"price": price}).json()


class AutoloadAPI(_SubAPI):
    """autoload/v1 / v2 — загрузка XML-фида и отчёты.

    Источник: https://developers.avito.ru/api-catalog/autoload/documentation
    """

    def upload(self, feed_url: str) -> dict[str, Any]:
        """POST /autoload/v1/upload — запустить загрузку фида по ссылке (autoload:reports)."""
        return self._client.post("/autoload/v1/upload", json={"feed_url": feed_url}).json()

    def profile(self) -> dict[str, Any]:
        """GET /autoload/v2/profile — настройки профиля автозагрузки (autoload:reports)."""
        return self._client.get("/autoload/v2/profile").json()

    def reports(self, *, per_page: int = 25, page: int = 1) -> dict[str, Any]:
        """GET /autoload/v2/reports — список отчётов автозагрузки (autoload:reports)."""
        return self._client.get("/autoload/v2/reports", params={"per_page": per_page, "page": page}).json()

    def report(self, report_id: int) -> dict[str, Any]:
        """GET /autoload/v2/reports/{report_id} — детали конкретного отчёта (autoload:reports)."""
        return self._client.get(f"/autoload/v2/reports/{report_id}").json()

    def last_completed_report(self) -> dict[str, Any]:
        """GET /autoload/v2/reports/last_completed_report — последний завершённый отчёт."""
        return self._client.get("/autoload/v2/reports/last_completed_report").json()


class MessengerAPI(_SubAPI):
    """messenger/v1 / v2 / v3 — чаты, сообщения, подписки на вебхуки.

    Источник: https://developers.avito.ru/api-catalog/messenger/documentation
    """

    def chats(self, user_id: int, *, unread_only: bool = False, item_ids: Iterable[int] | None = None) -> dict[str, Any]:
        """GET /messenger/v2/accounts/{user_id}/chats — список чатов (messenger:read)."""
        params: dict[str, Any] = {}
        if unread_only:
            params["unread_only"] = "true"
        if item_ids is not None:
            params["item_ids"] = list(item_ids)
        return self._client.get(f"/messenger/v2/accounts/{user_id}/chats", params=params).json()

    def chat(self, user_id: int, chat_id: str) -> dict[str, Any]:
        """GET /messenger/v2/accounts/{user_id}/chats/{chat_id} — карточка чата (messenger:read)."""
        return self._client.get(f"/messenger/v2/accounts/{user_id}/chats/{chat_id}").json()

    def messages(self, user_id: int, chat_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        """GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/ — история сообщений (messenger:read)."""
        params = {"limit": limit, "offset": offset}
        return self._client.get(
            f"/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/", params=params
        ).json()

    def send_message(self, user_id: int, chat_id: str, text: str) -> dict[str, Any]:
        """POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages — отправить текст (messenger:write)."""
        payload = {"message": {"text": text}, "type": "text"}
        return self._client.post(
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages", json=payload
        ).json()

    def mark_read(self, user_id: int, chat_id: str) -> dict[str, Any]:
        """POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/read — пометить чат прочитанным (messenger:read)."""
        return self._client.post(f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/read").json()

    def subscribe_webhook_v3(self, webhook_url: str) -> dict[str, Any]:
        """POST /messenger/v3/webhook — подписаться на уведомления о новых сообщениях (messenger:read).

        После регистрации Avito проверяет, что webhook_url отвечает 200 OK за 2 секунды.
        """
        return self._client.post("/messenger/v3/webhook", json={"url": webhook_url}).json()

    def unsubscribe_webhook(self, webhook_url: str) -> dict[str, Any]:
        """POST /messenger/v1/webhook/unsubscribe — отключить уведомления (messenger:read)."""
        return self._client.post("/messenger/v1/webhook/unsubscribe", json={"url": webhook_url}).json()

    def subscriptions(self) -> dict[str, Any]:
        """POST /messenger/v1/subscriptions — текущие подписки на вебхуки (messenger:read)."""
        return self._client.post("/messenger/v1/subscriptions").json()
