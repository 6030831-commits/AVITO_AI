"""Тесты кэша токена и получения access_token. Сеть мокается httpx.MockTransport."""

import unittest

import httpx

from avito_uslugi.auth import TOKEN_URL, TokenCache, fetch_access_token
from avito_uslugi.exceptions import AvitoAuthError


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


class TokenCacheTests(unittest.TestCase):
    def test_returns_none_when_empty(self):
        cache = TokenCache(clock=FakeClock())
        self.assertIsNone(cache.get())

    def test_returns_token_before_expiry_minus_margin(self):
        clock = FakeClock(start=0.0)
        cache = TokenCache(safety_margin=60, clock=clock)
        cache.store("tok-1", expires_in=3600)

        clock.now = 3600 - 61  # ещё до границы margin
        self.assertEqual(cache.get(), "tok-1")

        clock.now = 3600 - 59  # уже внутри окна margin — считаем протухшим
        self.assertIsNone(cache.get())

    def test_invalidate_clears_token(self):
        clock = FakeClock(start=0.0)
        cache = TokenCache(clock=clock)
        cache.store("tok-1", expires_in=3600)
        cache.invalidate()
        self.assertIsNone(cache.get())


class FetchAccessTokenTests(unittest.TestCase):
    def _client(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_success_returns_token_and_expiry(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = request.read().decode()
            return httpx.Response(200, json={"access_token": "abc123", "expires_in": 86400, "token_type": "Bearer"})

        with self._client(handler) as http:
            token, expires_in = fetch_access_token(http, "client-id", "client-secret")

        self.assertEqual(token, "abc123")
        self.assertEqual(expires_in, 86400)
        self.assertEqual(captured["url"], TOKEN_URL)
        self.assertIn("grant_type=client_credentials", captured["body"])
        self.assertIn("client_id=client-id", captured["body"])
        self.assertIn("client_secret=client-secret", captured["body"])

    def test_error_response_raises_auth_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid_client"})

        with self._client(handler) as http:
            with self.assertRaises(AvitoAuthError) as ctx:
                fetch_access_token(http, "bad-id", "bad-secret")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_malformed_payload_raises_auth_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"token_type": "Bearer"})

        with self._client(handler) as http:
            with self.assertRaises(AvitoAuthError):
                fetch_access_token(http, "id", "secret")


if __name__ == "__main__":
    unittest.main()
