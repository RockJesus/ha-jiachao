"""家超云 API client.

API protocol reconstructed from jiachao.apk analysis:
- Base URL: https://query.iotdreamcatcher.net.cn:12082
- All requests use GET method
- Common params: countryCode, os, osVer, app, appVer, uuid
- Login: GET /v2/user/login?name=xxx&password=xxx&...
- Auth: token via header or query param
- Response: {"code":200,"data":{...},"msg":"OK"}
- Error codes: 462=User Not Exist, 464=Username Or Password Error
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid as uuid_lib
from typing import Any

import aiohttp

from .const import (
    API_CODE_LOGIN,
    API_DEVICE_INFO,
    API_DEVICE_LIST,
    API_LOGIN,
    API_SEND_LOGIN_CODE,
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

    @staticmethod
    def _generate_username_variants(username: str) -> list[str]:
        """Generate possible username formats.

        Args:
            username: Original username input.

        Returns:
            List of possible username formats.
        """
        variants = [username]
        username = username.strip()

        # Phone number variants
        if re.match(r'^\+?\d{6,}$', username):
            # With +86 prefix
            if username.startswith('+86'):
                variants.append(username[3:])  # Remove +86
                variants.append('86' + username[3:])  # Replace + with 86
            elif username.startswith('86') and len(username) > 11:
                variants.append(username[2:])  # Remove 86 prefix
                variants.append('+' + username)  # Add + prefix
            else:
                # Plain phone number, try with prefixes
                variants.append('+86' + username)
                variants.append('86' + username)

        # Email - try lowercase
        if '@' in username:
            lower = username.lower()
            if lower not in variants:
                variants.append(lower)

        # Deduplicate while preserving order
        seen = set()
        result = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result

    @staticmethod
    def _generate_password_variants(password: str) -> list[tuple[str, str]]:
        """Generate possible password formats.

        Args:
            password: Original password.

        Returns:
            List of (password, description) tuples.
        """
        variants = [
            (password, "plain"),
            (hashlib.md5(password.encode('utf-8')).hexdigest(), "md5_lower"),
            (hashlib.md5(password.encode('utf-8')).hexdigest().upper(), "md5_upper"),
            (hashlib.md5(password.encode('utf-8')).hexdigest()[8:24], "md5_16_lower"),
        ]
        # Deduplicate
        seen = set()
        result = []
        for pwd, desc in variants:
            if pwd not in seen:
                seen.add(pwd)
                result.append((pwd, desc))
        return result

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Login to 家超 cloud.

        Automatically tries multiple username formats and password encryption
        methods (plain, MD5) to find the correct combination.

        Args:
            username: Phone number or email.
            password: Account password.

        Returns:
            Login response data.

        Raises:
            JiachaoAPIError: If login fails after all attempts.
        """
        username_variants = self._generate_username_variants(username)
        password_variants = self._generate_password_variants(password)

        _LOGGER.debug(
            "Login attempts: %d username variants x %d password variants = %d total",
            len(username_variants), len(password_variants),
            len(username_variants) * len(password_variants)
        )

        last_error: JiachaoAPIError | None = None
        found_existing_user = False

        for uname in username_variants:
            for pwd, pwd_desc in password_variants:
                try:
                    _LOGGER.debug("Trying login: name=%s, password_type=%s", uname, pwd_desc)
                    params = self._common_params()
                    params["name"] = uname
                    params["password"] = pwd

                    data = await self._request("GET", API_LOGIN, params=params, auth=False)

                    # Success!
                    _LOGGER.info("Login successful with name=%s, password_type=%s", uname, pwd_desc)

                    # Extract token and user info
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

                except JiachaoAPIError as err:
                    last_error = err
                    err_msg = str(err)

                    # If user exists but password wrong, try other password formats
                    if "464" in err_msg or "Password Error" in err_msg or "Username Or Password" in err_msg:
                        found_existing_user = True
                        _LOGGER.debug("User %s exists, password type %s wrong", uname, pwd_desc)
                        continue

                    # If user doesn't exist, try other username formats
                    if "462" in err_msg or "User Not Exist" in err_msg:
                        _LOGGER.debug("User %s does not exist", uname)
                        # Skip remaining password variants for this username
                        break

                    # Other errors (network, etc.) - retry might help
                    _LOGGER.debug("Login error for %s/%s: %s", uname, pwd_desc, err)
                    continue

        # All attempts failed
        if found_existing_user:
            raise JiachaoAPIError(
                f"用户名存在但密码错误，请确认密码是否正确。"
                f"已尝试明文和MD5加密。最后错误: {last_error}"
            )
        raise JiachaoAPIError(
            f"登录失败，未找到匹配的用户。请确认用户名（手机号/邮箱）是否正确。"
            f"已尝试 {len(username_variants)} 种用户名格式。最后错误: {last_error}"
        )

    async def send_login_code(self, phone: str, region: str = COUNTRY_CODE) -> dict[str, Any]:
        """Send login verification code to phone.

        Args:
            phone: Phone number.
            region: Region code (default CN).

        Returns:
            Response data.

        Raises:
            JiachaoAPIError: If sending fails.
        """
        # Normalize phone number - remove +86 or 86 prefix
        normalized_phone = phone.strip()
        if normalized_phone.startswith('+86'):
            normalized_phone = normalized_phone[3:]
        elif normalized_phone.startswith('86') and len(normalized_phone) > 11:
            normalized_phone = normalized_phone[2:]

        params = self._common_params()
        params["name"] = normalized_phone
        params["region"] = region

        _LOGGER.debug("Sending login code to %s", normalized_phone)
        data = await self._request("GET", API_SEND_LOGIN_CODE, params=params, auth=False)
        _LOGGER.info("Login code sent to %s", normalized_phone)
        return data

    async def login_with_code(self, phone: str, code: str) -> dict[str, Any]:
        """Login with phone and verification code.

        Args:
            phone: Phone number.
            code: Verification code.

        Returns:
            Login response data.

        Raises:
            JiachaoAPIError: If login fails.
        """
        # Normalize phone number
        normalized_phone = phone.strip()
        if normalized_phone.startswith('+86'):
            normalized_phone = normalized_phone[3:]
        elif normalized_phone.startswith('86') and len(normalized_phone) > 11:
            normalized_phone = normalized_phone[2:]

        params = self._common_params()
        params["name"] = normalized_phone
        params["code"] = code

        _LOGGER.debug("Logging in with code for %s", normalized_phone)
        data = await self._request("GET", API_CODE_LOGIN, params=params, auth=False)

        # Extract token and user info
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

        _LOGGER.info("Code login successful, user_id=%s", self._user_id)
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
        timeout = aiohttp.ClientTimeout(total=30)
        for base_url in API_BASE_URLS:
            url = f"{base_url}{path}"
            try:
                _LOGGER.debug("Requesting %s with params %s", url, request_params)
                resp = await self._session.get(
                    url, params=request_params, headers=headers, ssl=False, timeout=timeout
                )

                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise JiachaoAPIError(f"HTTP {resp.status}: {text[:500]}")

                try:
                    result = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    text = await resp.text()
                    raise JiachaoAPIError(f"Invalid JSON response: {text[:500]}") from err

                _LOGGER.debug("API response: %s", result)

                # Check API-level error code
                code = result.get("code", result.get("errcode", 0))
                if code not in (0, 200, "0", "200"):
                    msg = result.get("msg", result.get("message", result.get("errmsg", "Unknown error")))
                    raise JiachaoAPIError(f"API error {code}: {msg}")

                # Success - update base_url to working one
                self._base_url = base_url
                return result.get("data", result)

            except JiachaoAPIError:
                raise
            except Exception as err:
                last_error = err
                _LOGGER.warning("Request to %s failed: %s: %s", base_url, type(err).__name__, err)
                continue

        if last_error:
            raise JiachaoAPIError(f"All API servers failed: {type(last_error).__name__}: {last_error}")
        raise JiachaoAPIError("All API servers failed")


class JiachaoAPIError(Exception):
    """Exception for 家超 API errors."""
