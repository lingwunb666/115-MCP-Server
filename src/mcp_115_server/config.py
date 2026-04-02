from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    p115_cookies: str | None = Field(default=None, alias="P115_COOKIES")
    p115_cookies_path: str | None = Field(default=None, alias="P115_COOKIES_PATH")
    p115_check_for_relogin: bool = Field(default=True, alias="P115_CHECK_FOR_RELOGIN")
    p115_allow_qrcode_login: bool = Field(default=False, alias="P115_ALLOW_QRCODE_LOGIN")
    p115_console_qrcode: bool = Field(default=False, alias="P115_CONSOLE_QRCODE")

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
