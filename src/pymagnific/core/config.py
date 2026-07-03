"""Application settings via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from pymagnific.core.exceptions import ConfigError

_PKG_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _PKG_ROOT / ".env"

MAGNIFIC_API_BASE = "https://api.magnific.com"
OAUTH_AUTH_SERVER = "https://auth.magnific.com/realms/mcp"
OAUTH_REGISTRATION_ENDPOINT = (
    "https://auth.magnific.com/realms/mcp/clients-registrations/openid-connect"
)


def _default_runs_dir() -> Path:
    d = _PKG_ROOT / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _default_projects_dir() -> Path:
    d = _PKG_ROOT / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Settings(BaseSettings):
    api_key: SecretStr | None = None
    mcp_url: str = "https://mcp.magnific.com"
    oauth_dir: Path | None = None
    oauth_path: Path | None = None
    webhook_secret: SecretStr | None = None
    webhook_url: str | None = None
    oauth_scopes: str = "openid profile email offline_access mcp:custom-audience"
    oauth_device_timeout: int = 300
    runs_dir: Path = Field(default_factory=_default_runs_dir)
    projects_dir: Path = Field(default_factory=_default_projects_dir)
    rest_timeout: float = 60.0
    log_dir: Path | None = None
    log_level: str = "INFO"
    log_to_console: bool = True

    @property
    def pkg_root(self) -> Path:
        return _PKG_ROOT

    def resolved_log_dir(self) -> Path:
        """Log directory: MAGNIFIC_LOG_DIR or ./logs in cwd."""
        base = self.log_dir.expanduser() if self.log_dir else Path.cwd() / "logs"
        base.mkdir(parents=True, exist_ok=True)
        return base

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        env_prefix="MAGNIFIC_",
        extra="ignore",
    )

    def resolved_oauth_dir(self) -> Path:
        if self.oauth_dir:
            path = self.oauth_dir.expanduser()
        else:
            path = Path.home() / ".config" / "pymagnific"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def oauth_token_path(self) -> Path:
        if self.oauth_path:
            return self.oauth_path.expanduser()
        return self.resolved_oauth_dir() / "oauth.json"

    def oauth_client_path(self) -> Path:
        return self.resolved_oauth_dir() / "oauth_client.json"

    def rate_usage_path(self) -> Path:
        return self.resolved_oauth_dir() / "rate_usage.json"

    def require_api_key(self) -> str:
        if not self.api_key:
            raise ConfigError(
                "Missing MAGNIFIC_API_KEY. Copy .env.example to .env and set your key."
            )
        return self.api_key.get_secret_value()

    def webhook_secret_value(self) -> str | None:
        if not self.webhook_secret:
            return None
        return self.webhook_secret.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
