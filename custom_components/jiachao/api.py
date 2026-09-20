"""API client for 家超."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_LOGIN,
    API_LOGOUT,
    API_USER_INFO,
    API_DEVICE_LIST,
    DEFAULT_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)


class JiachaoAuthError(Exception):
    """Authentication error."""


class JiachaoApiError(Exception):
    """API error."""


class JiachaoClient:
    """API client for 家超."""

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._session = session or aiohttp.ClientSession()

        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires: int = 0

        self.user_id: str | None = None
        self.nickname: str | None = None
        self.avatar: str | None = None

    @property
    def access_token(self) -> str | None:
        """Return access token."""
        return self._access_token

    def _base_headers(self, token: str | None = None) -> dict[str, str]:
        """Build base request headers."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "JiaChao/2.2.2 (iPhone; iOS 17.0; Scale/3.00)",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a request and return decoded JSON."""
        url = f"{self.base_url}{path}"
        headers = self._base_headers(token)

        async with self._session.request(
            method,
            url,
            headers=headers,
            json=payload if payload is not None else None,
            params=params,
            ssl=False,
        ) as resp:
            data = await resp.json(content_type=None)

            if isinstance(data, dict):
                code = data.get("code")
                try:
                    code_int = int(code)
                except (TypeError, ValueError):
                    code_int = None

                if code_int not in (0, 200, None):
                    if resp.status == 401 or code_int in (401, 1001):
                        raise JiachaoAuthError("令牌无效或已过期")
                    raise JiachaoApiError(
                        f"API error: code {code}: {str(data.get('msg') or data.get('message'))[:200]}"
                    )

            if resp.status >= 400:
                raise JiachaoApiError(f"HTTP {resp.status}")

            return data

    async def login(self) -> None:
        """Login with username and password."""
        payload = {
            "account": self.username,
            "password": self.password,
        }

        _LOGGER.debug("Logging in...")
        data = await self._request("POST", API_LOGIN, payload=payload)

        result = data.get("data", data)
        self._access_token = result.get("accessToken") or result.get("access_token")
        self._refresh_token = result.get("refreshToken") or result.get("refresh_token")

        if not self._access_token:
            raise JiachaoAuthError("登录失败：未返回 accessToken")

        self._token_expires = int(time.time()) + 7 * 24 * 3600
        _LOGGER.info("Login successful")

        # Get user info
        try:
            await self.get_user_info()
        except Exception as err:
            _LOGGER.warning("Failed to get user info: %s", err)

    async def get_user_info(self) -> dict[str, Any]:
        """Get current user info."""
        data = await self._request("GET", API_USER_INFO, token=self._access_token)
        result = data.get("data", data)

        if isinstance(result, dict):
            self.user_id = str(result.get("id", ""))
            self.nickname = result.get("nickname", "")
            self.avatar = result.get("avatar", "")
            _LOGGER.info("User: %s (id: %s)", self.nickname, self.user_id)

        return result

    async def get_device_list(self) -> list[dict[str, Any]]:
        """Get device list."""
        data = await self._request("GET", API_DEVICE_LIST, token=self._access_token)
        raw = data.get("data", data)
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            devices = raw.get("list") or raw.get("devices") or []
            if isinstance(devices, list):
                return devices
        return []

    async def async_close(self) -> None:
        """Close the session."""
        await self._session.close()
