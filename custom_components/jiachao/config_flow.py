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
from .const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME, DOMAIN, LIGHT_DEVICE_TYPES

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Args:
        hass: Home Assistant instance.
        data: User input data.

    Returns:
        Dict with validation results.

    Raises:
        ValueError: If validation fails.
    """
    session = async_get_clientsession(hass)
    api = JiachaoAPI(session)

    try:
        await api.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    except JiachaoAPIError as err:
        raise ValueError(f"登录失败: {err}") from err

    try:
        devices = await api.get_device_list()
    except JiachaoAPIError as err:
        raise ValueError(f"获取设备列表失败: {err}") from err

    # Filter light devices
    light_devices = []
    for dev in devices:
        dev_type = str(dev.get("deviceType", dev.get("type", ""))).lower()
        model = str(dev.get("model", dev.get("productKey", ""))).lower()
        if any(t in dev_type or t in model for t in LIGHT_DEVICE_TYPES):
            light_devices.append(dev)

    if not light_devices:
        raise ValueError("未找到家超睡眠灯设备，请先在APP中绑定设备")

    return {"devices": light_devices, "api": api}


class JiachaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 家超睡眠灯."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._devices: list[dict[str, Any]] = []
        self._api: JiachaoAPI | None = None
        self._auth_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - account login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                self._devices = info["devices"]
                self._api = info["api"]
                self._auth_data = user_input
                return await self.async_step_select_device()
            except ValueError as err:
                _LOGGER.error("Validation failed: %s", err)
                errors["base"] = "auth_error"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "username_hint": "手机号或邮箱",
                "password_hint": "家超APP登录密码",
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
