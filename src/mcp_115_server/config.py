from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    p115_cookies: str | None = Field(default=None, alias="P115_COOKIES")
    p115_cookies_path: str | None = Field(default=None, alias="P115_COOKIES_PATH")
    p115_check_for_relogin: bool = Field(default=True, alias="P115_CHECK_FOR_RELOGIN")
    p115_allow_qrcode_login: bool = Field(default=False, alias="P115_ALLOW_QRCODE_LOGIN")
    p115_console_qrcode: bool = Field(default=False, alias="P115_CONSOLE_QRCODE")
    p115_app: str | None = Field(default=None, alias="P115_APP")
    p115_cookie_platform: str | None = Field(default=None, alias="P115_COOKIE_PLATFORM")
    p115_platform_fallbacks: str | None = Field(default=None, alias="P115_PLATFORM_FALLBACKS")

    fastmcp_transport: str = Field(default="stdio", alias="FASTMCP_TRANSPORT")
    fastmcp_host: str = Field(default="127.0.0.1", alias="FASTMCP_HOST")
    fastmcp_port: int = Field(default=8000, alias="FASTMCP_PORT")
    fastmcp_path: str = Field(default="/mcp", alias="FASTMCP_PATH")
    fastmcp_log_level: str = Field(default="info", alias="FASTMCP_LOG_LEVEL")

    @property
    def cookies_path(self) -> Path | None:
        if not self.p115_cookies_path:
            return None
        return Path(self.p115_cookies_path).expanduser()

    @property
    def has_auth_configuration(self) -> bool:
        return bool(self.p115_cookies or self.p115_cookies_path or self.p115_allow_qrcode_login)

    @property
    def cookies_source(self) -> str:
        if self.p115_cookies:
            return "env"
        if self.p115_cookies_path:
            return "file"
        if self.p115_allow_qrcode_login:
            return "qrcode"
        return "missing"

    @property
    def preferred_platform(self) -> str | None:
        for value in (self.p115_cookie_platform, self.p115_app):
            if value and value.strip():
                return value.strip()
        return None

    @property
    def fallback_platforms(self) -> list[str]:
        if not self.p115_platform_fallbacks:
            return []
        return [part.strip() for part in self.p115_platform_fallbacks.split(",") if part.strip()]
