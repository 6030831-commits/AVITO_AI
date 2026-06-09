"""Тесты AvitoClient (items / autoload / messenger) и логики ретраев/обновления токена.

Вся сеть — через httpx.MockTransport, реальных вызовов к api.avito.ru нет.
"""

import unittest

import httpx

from avito_uslugi.client import API_BASE_URL, AvitoClient
from avito_uslugi.exceptions import AvitoAPIError

TOKEN_RESPONSE = {"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"}


def make_client(handler, **kwargs) -> AvitoClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url=API_BASE_URL, transport=transport)
    return AvitoClient("client-id", "client-secret", http_client=http, sleep=lambda _seconds: None, **kwargs)


def token_route(request: httpx.Request) -> httpx.Response | None:
    if request.url.path in ("/token", "/token/"):
        return httpx.Response(200, json=TOKEN_RESPONSE)
    return None


class ItemsAPITests(unittest.TestCase):
    def test_list_sends_authorized_request_and_parses_response(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            seen.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            self.assertEqual(request.url.path, "/core/v1/items")
            self.assertEqual(request.url.params["per_page"], "10")
            return httpx.Response(200, json={"resources": [{"id": 1}], "meta": {"page": 1}})

        client = make_client(handler)
        result = client.items.list(per_page=10)

        self.assertEqual(result["resources"], [{"id": 1}])
        self.assertEqual(len(seen), 1)

    def test_token_is_cached_across_calls(self):
        token_calls = []
        item_calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path in ("/token", "/token/"):
                token_calls.append(request)
                return httpx.Response(200, json=TOKEN_RESPONSE)
            item_calls.append(request)
            return httpx.Response(200, json={"resources": []})

        client = make_client(handler)
        client.items.list()
        client.items.list()

        self.assertEqual(len(token_calls), 1, "токен должен запрашиваться один раз и переиспользоваться")
        self.assertEqual(len(item_calls), 2)

    def test_401_triggers_token_refresh_and_retry(self):
        token_calls = []
        item_attempts = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path in ("/token", "/token/"):
                token_calls.append(request)
                return httpx.Response(200, json={**TOKEN_RESPONSE, "access_token": f"token-{len(token_calls)}"})
            item_attempts.append(request.headers["Authorization"])
            if len(item_attempts) == 1:
                return httpx.Response(401, json={"error": "expired_token"})
            return httpx.Response(200, json={"resources": ["ok"]})

        client = make_client(handler)
        result = client.items.get(user_id=42, item_id=99)

        self.assertEqual(result["resources"], ["ok"])
        self.assertEqual(len(token_calls), 2, "после 401 токен должен быть обновлён")
        self.assertEqual(item_attempts, ["Bearer token-1", "Bearer token-2"])

    def test_5xx_is_retried_then_succeeds(self):
        attempts = []

        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            attempts.append(request)
            if len(attempts) < 3:
                return httpx.Response(503, json={"error": "temporarily unavailable"})
            return httpx.Response(200, json={"resources": []})

        client = make_client(handler, max_attempts=3)
        client.items.list()
        self.assertEqual(len(attempts), 3)

    def test_exhausted_retries_raise_avito_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            return httpx.Response(500, json={"error": "boom"})

        client = make_client(handler, max_attempts=2)
        with self.assertRaises(AvitoAPIError) as ctx:
            client.items.list()
        self.assertEqual(ctx.exception.status_code, 500)

    def test_apply_vas_uses_put_and_correct_path(self):
        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            self.assertEqual(request.method, "PUT")
            self.assertEqual(request.url.path, "/core/v2/items/123/vas/")
            return httpx.Response(200, json={"applied": True})

        client = make_client(handler)
        result = client.items.apply_vas(123, ["x100", "highlight"])
        self.assertTrue(result["applied"])

    def test_stats_shallow_posts_expected_payload(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            captured["path"] = request.url.path
            captured["body"] = request.read()
            return httpx.Response(200, json={"result": {}})

        client = make_client(handler)
        client.items.stats_shallow(7, [1, 2, 3], date_from="2026-06-01", date_to="2026-06-07")

        self.assertEqual(captured["path"], "/stats/v1/accounts/7/items")
        self.assertIn(b'"itemIds":[1,2,3]', captured["body"])
        self.assertIn(b'"dateFrom":"2026-06-01"', captured["body"])


class AutoloadAPITests(unittest.TestCase):
    def test_reports_calls_expected_path_with_pagination(self):
        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            self.assertEqual(request.url.path, "/autoload/v2/reports")
            self.assertEqual(request.url.params["page"], "2")
            return httpx.Response(200, json={"reports": []})

        client = make_client(handler)
        client.autoload.reports(page=2)

    def test_upload_posts_feed_url(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            captured["path"] = request.url.path
            captured["body"] = request.read()
            return httpx.Response(200, json={"status": "queued"})

        client = make_client(handler)
        client.autoload.upload("https://example.com/feed.xml")

        self.assertEqual(captured["path"], "/autoload/v1/upload")
        self.assertIn(b"https://example.com/feed.xml", captured["body"])


class MessengerAPITests(unittest.TestCase):
    def test_send_message_posts_text_payload(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = request.read()
            return httpx.Response(200, json={"id": "msg-1"})

        client = make_client(handler)
        client.messenger.send_message(11, "chat-abc", "Здравствуйте! Опишите задачу — оценим объём.")

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/messenger/v1/accounts/11/chats/chat-abc/messages")
        self.assertIn('"type":"text"'.encode(), captured["body"])
        self.assertIn("Опишите задачу".encode("utf-8"), captured["body"])

    def test_chats_passes_unread_only_param(self):
        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            self.assertEqual(request.url.path, "/messenger/v2/accounts/11/chats")
            self.assertEqual(request.url.params["unread_only"], "true")
            return httpx.Response(200, json={"chats": []})

        client = make_client(handler)
        client.messenger.chats(11, unread_only=True)

    def test_subscribe_webhook_v3_posts_url(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            token_resp = token_route(request)
            if token_resp is not None:
                return token_resp
            captured["path"] = request.url.path
            captured["body"] = request.read()
            return httpx.Response(200, json={"ok": True})

        client = make_client(handler)
        result = client.messenger.subscribe_webhook_v3("https://my-vps.example/webhooks/avito")

        self.assertEqual(captured["path"], "/messenger/v3/webhook")
        self.assertIn(b"https://my-vps.example/webhooks/avito", captured["body"])
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
