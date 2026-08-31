"""家超云 API client.

API protocol reconstructed from jiachao.apk analysis:
- Base URL: https://query.iotdreamcatcher.net.cn:12082
- All requests use GET method
- Common params: countryCode, os, osVer, app, appVer, uuid
- Login: GET /v2/user/login?name=xxx&password=xxx&...
- Auth: token via header or query param
- Response: {"code":200,"data":{...},"msg":"OK"}
"""
from __future__ import annotations

import logging
import uuid as uuid_lib
from typing import Any

import aiohttp
import async_timeout

from .const import (
    API_DEVICE_INFO,
    API_DEVICE_LIST,
    API_LOGIN,
    API_USER_CONFIG,
)

_LOGGER = logging.getLogger(__name__)

# API base URLs (primary + fallback)
API_BASE_URLS = [
    "https://query.iotdreamcatcher.net.cn:12082",
    "https://dc02.iotdreamcatcher.net.cn:12443",
]

# App identification (from APK analysis)
APP_PACKAGE = "com.dc.jiachao"
APP_VERSION = "1.3.0"
OS_TYPE = "android"
OS_VERSION = "13"
COUNTRY_CODE = "CN"

# Generate a stable device UUID for this HA installation
_DEVICE_UUID = str(uuid_lib.uuid4())


class JiachaoAPI:
    """家超云 API client."""

    def __init__(self, websession: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._session = websession
        self._base_url = API_BASE_URLS[0]
        self._token: str | None = None
        self._user_id: str | None = None
        self._device_uuid = _DEVICE_UUID

    @property
    def token(self) -> str | None:
        """Return the access token."""
        return self._token

    def _common_params(self) -> dict[str, str]:
        """Return common parameters required for all API requests."""
        return {
            "countryCode": COUNTRY_CODE,
            "os": OS_TYPE,
            "osVer": OS_VERSION,
            "app": APP_PACKAGE,
            "appVer": APP_VERSION,
            "uuid": self._device_uuid,
        }

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
        params = self._common_params()
        params["name"] = username
        params["password"] = password

        data = await self._request("GET", API_LOGIN, params=params, auth=False)

        # Extract token and user info from response
        if "token" in data:
            self._token = str(data["token"])
        elif "accessToken" in data:
            self._token = str(data["accessToken"])

        if "userId" in data:
            self._user_id = str(data["userId"])
        elif "uid" in data:
            self._user_id = str(data["uid"])
        elif "id" in data:
            self._user_id = str(data["id"])

        _LOGGER.debug("Login successful, user_id=%s", self._user_id)
        return data

    async def get_device_list(self) -> list[dict[str, Any]]:
        """Get list of devices bound to the account.

        Returns:
            List of device info dicts.
        """
        data = await self._request("GET", API_DEVICE_LIST)
        devices = data.get("list", data.get("devices", data.get("deviceList", [])))
        if isinstance(devices, dict):
            devices = devices.get("list", devices.get("devices", []))
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
        mqtt_info = config.get("mqtt", config.get("serverInfo", config.get("mqttInfo", {})))
        if isinstance(mqtt_info, str):
            import json
            try:
                mqtt_info = json.loads(mqtt_info)
            except (json.JSONDecodeError, TypeError):
                mqtt_info = {}

        # Handle nested serverInfo structure
        if isinstance(mqtt_info, dict) and "mqtt" in mqtt_info:
            mqtt_info = mqtt_info["mqtt"]

        host = mqtt_info.get("domain", mqtt_info.get("host", mqtt_info.get("serverDomain", "")))
        port = int(mqtt_info.get("port", mqtt_info.get("serverPort", 1883)))
        username = mqtt_info.get("username", mqtt_info.get("userToken", self._user_id or ""))
        password = mqtt_info.get("password", mqtt_info.get("token", self._token or ""))
        client_id = mqtt_info.get("clientId", mqtt_info.get("clientID", f"ha_{self._user_id}"))
        use_tls = bool(mqtt_info.get("useTls", mqtt_info.get("ssl", mqtt_info.get("tls", False))))

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "client_id": client_id,
            "use_tls": use_tls,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API.

        All requests use GET method with query parameters.

        Args:
            method: HTTP method (always GET for this API).
            path: API path.
            params: Query parameters (merged with common params).
            auth: Whether to include auth token.

        Returns:
            Parsed response data.

        Raises:
            JiachaoAPIError: On request failure or API error.
        """
        # Merge common params with request-specific params
        request_params = self._common_params()
        if params:
            request_params.update(params)

        # Add token to params if authenticated
        if auth and self._token:
            request_params["token"] = self._token

        headers = {
            "Accept": "application/json",
            "User-Agent": f"{APP_PACKAGE}/{APP_VERSION} (Android {OS_VERSION})",
        }
        if auth and self._token:
            headers["token"] = self._token

        # Try each base URL
        last_error: Exception | None = None
        for base_url in API_BASE_URLS:
            url = f"{base_url}{path}"
            try:
                async with async_timeout.timeout(30):
                    resp = await self._session.get(
                        url, params=request_params, headers=headers, ssl=False
                    )

                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise JiachaoAPIError(f"HTTP {resp.status}: {text[:500]}")

                try:
                    result = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    text = await resp.text()
                    raise JiachaoAPIError(f"Invalid JSON response: {text[:500]}") from err

                # Check API-level error code
                code = result.get("code", result.get("errcode", 0))
                if code not in (0, 200, "0", "200"):
                    msg = result.get("msg", result.get("message", result.get("errmsg", "Unknown error")))
                    raise JiachaoAPIError(f"API error {code}: {msg}")

                # Success - update base_url to working one
                self._base_url = base_url
                return result.get("data", result)

            except (aiohttp.ClientError, async_timeout.TimeoutError) as err:
                last_error = err
                _LOGGER.debug("Request to %s failed: %s, trying next server", base_url, err)
                continue
            except JiachaoAPIError as err:
                # API errors (not network) should be raised immediately
                raise

        if last_error:
            raise JiachaoAPIError(f"All API servers failed: {last_error}")
        raise JiachaoAPIError("All API servers failed")


class JiachaoAPIError(Exception):
    """Exception for 家超 API errors."""
