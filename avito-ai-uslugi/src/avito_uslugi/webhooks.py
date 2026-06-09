"""Проверка подписи вебхуков мессенджера Авито (заголовок x-avito-messenger-signature).

⚠ Точный алгоритм подписи Авито официально не публикует в каталоге
developers.avito.ru/api-catalog/messenger/documentation#operation/postWebhookV3 —
там описан только формат подписки (POST /messenger/v3/webhook, тело {"url": ...},
без поля secret). Подпись приходит готовой строкой длиной 64 hex-символа
(см. https://qna.habr.com/q/1404944), что соответствует HMAC-SHA256 hex-digest —
это и есть отраслевой стандарт для такого рода заголовков (ср. x-hub-signature-256).

Поэтому ниже — реализация по этому стандарту с понятным интерфейсом: если в вашем
аккаунте Авито алгоритм/секрет окажется другим, замените только тело
`compute_signature`, остальной код (verify, маршрут вебхука) менять не придётся.
AVITO_WEBHOOK_SECRET берите из настроек вебхука в личном кабинете, если там
он показывается; если такого поля нет — see TODO ниже.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "x-avito-messenger-signature"


def compute_signature(raw_body: bytes, secret: str) -> str:
    """HMAC-SHA256(secret, raw_body) в виде hex-строки (см. предупреждение в докстринге модуля)."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_messenger_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Сверяет заголовок x-avito-messenger-signature с вычисленной подписью.

    Возвращает False, если заголовка нет или подпись не совпадает —
    в этом случае запрос нужно отклонять (HTTP 4xx), не доверяя телу.
    Сравнение — через hmac.compare_digest, чтобы не утекало время сравнения.
    """
    if not signature_header:
        return False
    expected = compute_signature(raw_body, secret)
    return hmac.compare_digest(expected, signature_header.strip().lower())
