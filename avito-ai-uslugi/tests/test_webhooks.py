"""Тесты проверки подписи x-avito-messenger-signature (HMAC-SHA256, см. webhooks.py)."""

import hashlib
import hmac
import unittest

from avito_uslugi.webhooks import compute_signature, verify_messenger_signature

SECRET = "test-webhook-secret"
BODY = b'{"id":"evt-1","payload":{"type":"message"}}'


class SignatureTests(unittest.TestCase):
    def test_compute_signature_is_hmac_sha256_hex(self):
        expected = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
        self.assertEqual(compute_signature(BODY, SECRET), expected)
        self.assertEqual(len(expected), 64)

    def test_verify_accepts_matching_signature(self):
        signature = compute_signature(BODY, SECRET)
        self.assertTrue(verify_messenger_signature(BODY, signature, SECRET))

    def test_verify_is_case_insensitive_to_header_casing(self):
        signature = compute_signature(BODY, SECRET)
        self.assertTrue(verify_messenger_signature(BODY, signature.upper(), SECRET))

    def test_verify_rejects_wrong_secret(self):
        signature = compute_signature(BODY, SECRET)
        self.assertFalse(verify_messenger_signature(BODY, signature, "wrong-secret"))

    def test_verify_rejects_tampered_body(self):
        signature = compute_signature(BODY, SECRET)
        tampered = BODY.replace(b"evt-1", b"evt-2")
        self.assertFalse(verify_messenger_signature(tampered, signature, SECRET))

    def test_verify_rejects_missing_header(self):
        self.assertFalse(verify_messenger_signature(BODY, None, SECRET))
        self.assertFalse(verify_messenger_signature(BODY, "", SECRET))


if __name__ == "__main__":
    unittest.main()
