"""Webhook HMAC verification tests."""

import base64
import hashlib
import hmac

from pymagnific.services.webhook_service import WebhookService


def test_verify_webhook_signature_valid():
    secret = "test-secret"
    body = b'{"status":"finished"}'
    wh_id = "msg_123"
    wh_ts = "1700000000"
    service = WebhookService()
    content = f"{wh_id}.{wh_ts}.{body.decode()}"
    digest = hmac.new(secret.encode(), content.encode(), hashlib.sha256).digest()
    sig = base64.b64encode(digest).decode()
    header = f"v1,{sig}"
    assert service.verify_signature(body, wh_id, wh_ts, header, secret)


def test_verify_webhook_signature_invalid():
    service = WebhookService()
    body = b"{}"
    assert not service.verify_signature(body, "a", "1", "v1,bad", "secret")
