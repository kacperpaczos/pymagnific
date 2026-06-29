"""Pydantic models for auth status."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AuthStatus(BaseModel):
    logged_in: bool
    client_registered: bool
    client_id: str | None = None
    token_path: str
    client_path: str
    expired: bool | None = None
    has_refresh: bool | None = None
    grant_types: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthStatus:
        return cls.model_validate(data)
