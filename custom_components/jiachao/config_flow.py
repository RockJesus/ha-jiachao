"""Config flow for 家超睡眠灯 integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JiachaoAPI, JiachaoAPIError
from .const import (
    CONF_CODE,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    LIGHT_DEVICE_TYPES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)

STEP_CAPTCHA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODE): str,
    }
)


async def _get_devices(api: JiachaoAPI) -> list[dict[str, Any]]:
    """Get and filter light devices from API."""
    devices = await api.get_device_list()
    _LOGGER.debug("Got %d devices", len(devices))

    light_devices = []
    for dev in devices:
        dev_type = str(dev.get("deviceType", dev.get("type", ""))).lower()
        model = str(dev.get("model", dev.get("productKey", ""))).lower()
        if any(t in dev_type or t in model for t in LIGHT_DEVICE_TYPES):
            light_devices.append(dev)

    if not light_devices:
        raise ValueError("未找到家超睡眠灯设备，请先在APP中绑定设备")

    return light_devices


async def validate_password_login(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate password login and get device list.

    Args:
        hass: Home Assistant instance.
        data: User input data with username and password.

    Returns:
        Dict with devices and api.

    Raises:
        ValueError: If login or device fetch fails.
    """
    session = async_get_clientsession(hass)
    api = JiachaoAPI(session)

    try:
        _LOGGER.debug("Attempting password login for user: %s", data[CONF_USERNAME])
        await api.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    except Exception as err:
        _LOGGER.error("Password login failed: %s: %s", type(err).__name__, err, exc_info=True)
        raise ValueError(f"登录失败: {err}") from err

    try:
        devices = await _get_devices(api)
    except Exception as err:
        _LOGGER.error("Get device list failed: %s", err, exc_info=True)
        raise ValueError(f"获取设备列表失败: {err}") from err

    return {"devices": devices, "api": api}


async def validate_code_login(
    hass: HomeAssistant, phone: str, code: str
) -> dict[str, Any]:
    """Validate code login and get device list.

    Args:
        hass: Home Assistant instance.
        phone: Phone number.
        code: Verification code.

    Returns:
        Dict with devices and api.

    Raises:
        ValueError: If login or device fetch fails.
    """
    session = async_get_clientsession(hass)
    api = JiachaoAPI(session)

    try:
        _LOGGER.debug("Attempting code login for phone: %s", phone)
        await api.login_with_code(phone, code)
    except Exception as err:
        _LOGGER.error("Code login failed: %s: %s", type(err).__name__, err, exc_info=True)
        raise ValueError(f"验证码登录失败: {err}") from err

    try:
        devices = await _get_devices(api)
    except Exception as err:
        _LOGGER.error("Get device list failed: %s", err, exc_info=True)
        raise ValueError(f"获取设备列表失败: {err}") from err

    return {"devices": devices, "api": api}


class JiachaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 家超睡眠灯."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._devices: list[dict[str, Any]] = []
        self._api: JiachaoAPI | None = None
        self._auth_data: dict[str, Any] = {}
        self._phone: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - account login.

        If password is provided, use password login.
        If password is empty, switch to verification code login.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "").strip()

            if not username:
                errors["base"] = "auth_error"
                errors["description"] = "请输入手机号或邮箱"
            elif not password:
                # Password empty - switch to verification code login
                self._phone = username
                self._auth_data = {CONF_USERNAME: username, CONF_PASSWORD: ""}
                return await self.async_step_captcha()
            else:
                # Password login
                try:
                    info = await validate_password_login(self.hass, user_input)
                    self._devices = info["devices"]
                    self._api = info["api"]
                    self._auth_data = user_input
                    return await self.async_step_select_device()
                except Exception as err:
                    _LOGGER.error("Validation failed: %s: %s", type(err).__name__, err, exc_info=True)
                    errors["base"] = "auth_error"
                    errors["description"] = str(err)[:200]

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "username_hint": "手机号或邮箱",
                "password_hint": "家超APP登录密码（留空使用验证码登录）",
            },
        )

    async def async_step_captcha(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle verification code login step.

        Sends verification code on first entry, then validates code input.
        """
        errors: dict[str, str] = {}

        if user_input is None:
            # First entry - send verification code
            try:
                session = async_get_clientsession(self.hass)
                api = JiachaoAPI(session)
                await api.send_login_code(self._phone)
                errors["description"] = f"验证码已发送到 {self._phone}，请查收短信"
            except Exception as err:
                _LOGGER.error("Send code failed: %s: %s", type(err).__name__, err, exc_info=True)
                errors["base"] = "auth_error"
                errors["description"] = f"发送验证码失败: {err}"
        else:
            code = user_input.get(CONF_CODE, "").strip()
            if not code:
                errors["base"] = "auth_error"
                errors["description"] = "请输入验证码"
            else:
                try:
                    info = await validate_code_login(self.hass, self._phone, code)
                    self._devices = info["devices"]
                    self._api = info["api"]
                    self._auth_data[CONF_CODE] = code
                    return await self.async_step_select_device()
                except Exception as err:
                    _LOGGER.error("Code login failed: %s: %s", type(err).__name__, err, exc_info=True)
                    errors["base"] = "auth_error"
                    errors["description"] = str(err)[:200]

        return self.async_show_form(
            step_id="captcha",
            data_schema=STEP_CAPTCHA_SCHEMA,
            errors=errors,
            description_placeholders={
                "phone": self._phone,
                "code_hint": "请输入收到的6位短信验证码",
            },
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection step."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = next(
                (d for d in self._devices if str(d.get("deviceId", d.get("id", ""))) == device_id),
                None,
            )

            if device is None:
                return self.async_show_form(
                    step_id="select_device",
                    data_schema=self._build_device_schema(),
                    errors={"base": "device_not_found"},
                )

            title = device.get("deviceName", device.get("name", f"家超睡眠灯 {device_id}"))

            return self.async_create_entry(
                title=title,
                data={
                    **self._auth_data,
                    CONF_DEVICE_ID: device_id,
                    "device_name": title,
                    "device_info": device,
                },
            )

        return self.async_show_form(
            step_id="select_device",
            data_schema=self._build_device_schema(),
        )

    def _build_device_schema(self) -> vol.Schema:
        """Build the device selection schema."""
        device_options = {}
        for dev in self._devices:
            dev_id = str(dev.get("deviceId", dev.get("id", "")))
            name = dev.get("deviceName", dev.get("name", dev_id))
            model = dev.get("model", dev.get("productKey", ""))
            label = f"{name} ({model})" if model else name
            device_options[dev_id] = label

        return vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): vol.In(device_options),
            }
        )
