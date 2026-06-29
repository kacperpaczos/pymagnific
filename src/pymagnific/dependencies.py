"""Dependency injection factories."""

from __future__ import annotations

from functools import lru_cache

from pymagnific.clients.magnific_mcp import MagnificMcpClient
from pymagnific.clients.magnific_rest import MagnificRestClient
from pymagnific.core.config import Settings, get_settings
from pymagnific.services.apps_service import AppsService
from pymagnific.services.assets_service import AssetsService
from pymagnific.services.auth_service import AuthService
from pymagnific.services.spaces_service import SpacesService
from pymagnific.services.webhook_service import WebhookService


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService()


@lru_cache
def get_apps_service() -> AppsService:
    return AppsService()


@lru_cache
def get_spaces_service() -> SpacesService:
    return SpacesService()


@lru_cache
def get_assets_service() -> AssetsService:
    return AssetsService()


@lru_cache
def get_webhook_service() -> WebhookService:
    return WebhookService()


def get_rest_client(settings: Settings | None = None) -> MagnificRestClient:
    return MagnificRestClient(settings=settings or get_settings())


def get_mcp_client(settings: Settings | None = None) -> MagnificMcpClient:
    return MagnificMcpClient(settings=settings or get_settings())
