"""Webhook service - HMAC verification and event persistence."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from pymagnific.core.config import Settings, get_settings


class WebhookService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def verify_signature(
        self,
        body: bytes,
        webhook_id: str,
        webhook_timestamp: str,
        webhook_signature_header: str,
        secret: str,
    ) -> bool:
        content_to_sign = f"{webhook_id}.{webhook_timestamp}.{body.decode('utf-8')}"
        digest = hmac.new(
            secret.encode("utf-8"), content_to_sign.encode("utf-8"), hashlib.sha256
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")

        for part in webhook_signature_header.split():
            if "," in part:
                _, sig = part.split(",", 1)
            else:
                sig = part
            if hmac.compare_digest(sig, expected):
                return True
        return False

    def save_event(self, payload: dict[str, Any]) -> Path:
        run_id = (
            payload.get("run_id")
            or payload.get("workflow_run_identifier")
            or payload.get("workflowRunIdentifier")
            or "unknown"
        )
        out = self._settings.runs_dir / f"{run_id}.json"
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return out

    def process_webhook(
        self,
        body: bytes,
        *,
        webhook_id: str,
        webhook_timestamp: str,
        webhook_signature: str,
    ) -> Path:
        secret = self._settings.webhook_secret_value()
        if secret and webhook_signature:
            if not self.verify_signature(
                body, webhook_id, webhook_timestamp, webhook_signature, secret
            ):
                raise PermissionError("Invalid webhook signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(str(e)) from e

        return self.save_event(payload)
