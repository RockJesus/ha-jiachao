"""家超云 API client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout

from .const import (
    API_BASE_URL,
    API_DEVICE_INFO,
    API_DEVICE_LIST,
    API_LOGIN,
    API_USER_CONFIG,
)

_LOGGER = logging.getLogger(__name__)


class JiachaoAPI:
    """家超云 API client."""

    def __init__(self, websession: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._session = websession
        self._base_url = API_BASE_URL
        self._token: str | None = None
        self._user_id: str | None = None

    @property
    def token(self) -> str | None:
        """Return the access token."""
        return self._token

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Login to 家超 cloud.

        Args:
            username: Phone number or email.
            password: Account password.

        Returns:
            Login response data.

        Raises:
            JiachaoAPIError: If login fails.
        """
        payload = {
            "account": username,
            "password": password,
        }

        data = await self._request("POST", API_LOGIN, json=payload, auth=False)

        if "token" in data:
            self._token = data["token"]
        if "userId" in data:
            self._user_id = str(data["userId"])
        elif "uid" in data:
            self._user_id = str(data["uid"])

        _LOGGER.debug("Login successful, user_id=%s", self._user_id)
        return data

    async def get_device_list(self) -> list[dict[str, Any]]:
        """Get list of devices bound to the account.

        Returns:
            List of device info dicts.
        """
        data = await self._request("GET", API_DEVICE_LIST)
        devices = data.get("list", data.get("devices", []))
        _LOGGER.debug("Got %d devices", len(devices))
        return devices

    async def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Get detailed info for a specific device.

        Args:
            device_id: The device ID.

        Returns:
            Device info dict.
        """
        params = {"deviceId": device_id}
        data = await self._request("GET", API_DEVICE_INFO, params=params)
        return data

    async def get_user_config(self) -> dict[str, Any]:
        """Get user config including MQTT server info.

        Returns:
            User config dict with server info.
        """
        data = await self._request("GET", API_USER_CONFIG)
        return data

    async def get_mqtt_config(self) -> dict[str, Any]:
        """Extract MQTT server configuration from user config.

        Returns:
            MQTT config dict with host, port, username, password.
        """
        config = await self.get_user_config()

        # ServerInfoMqtt structure from APK analysis
        mqtt_info = config.get("mqtt", config.get("serverInfo", {}))
        if isinstance(mqtt_info, str):
            # Sometimes nested as string
            import json
            try:
                mqtt_info = json.loads(mqtt_info)
            except (json.JSONDecodeError, TypeError):
                mqtt_info = {}

        return {
            "host": mqtt_info.get("domain", mqtt_info.get("host", "")),
            "port": int(mqtt_info.get("port", mqtt_info.get("serverPort", 1883))),
            "username": mqtt_info.get("username", mqtt_info.get("userToken", self._user_id or "")),
            "password": mqtt_info.get("password", mqtt_info.get("token", self._token or "")),
            "client_id": mqtt_info.get("clientId", f"ha_{self._user_id}"),
            "use_tls": mqtt_info.get("useTls", mqtt_info.get("ssl", False)),
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            json: JSON body.
            auth: Whether to include auth token.

        Returns:
            Parsed response data.

        Raises:
            JiachaoAPIError: On request failure or API error.
        """
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json"}

        if auth and self._token:
            headers["token"] = self._token
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with async_timeout.timeout(30):
                resp = await self._session.request(
                    method, url, params=params, json=json, headers=headers
                )
        except (aiohttp.ClientError, async_timeout.TimeoutError) as err:
            raise JiachaoAPIError(f"Network error: {err}") from err

        if resp.status not in (200, 201):
            text = await resp.text()
            raise JiachaoAPIError(f"HTTP {resp.status}: {text[:500]}")

        try:
            result = await resp.json()
        except aiohttp.ContentTypeError as err:
            text = await resp.text()
            raise JiachaoAPIError(f"Invalid JSON response: {text[:500]}") from err

        # Check API-level error code
        code = result.get("code", result.get("errcode", 0))
        if code not in (0, 200, "0", "200"):
            msg = result.get("msg", result.get("message", result.get("errmsg", "Unknown error")))
            raise JiachaoAPIError(f"API error {code}: {msg}")

        return result.get("data", result)


class JiachaoAPIError(Exception):
    """Exception for 家超 API errors."""
