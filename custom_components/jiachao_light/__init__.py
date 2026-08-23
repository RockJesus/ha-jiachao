"""家超睡眠灯 BLE 集成 - 初始化"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CUSTOM_NOTIFY_UUID,
    CONF_CUSTOM_SERVICE_UUID,
    CONF_CUSTOM_WRITE_UUID,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    CONF_PROTOCOL,
    DOMAIN,
    PROTOCOL_PRESETS,
)
from .device import BLELightDevice
from .protocol import BLELightProtocol

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置 config entry。"""
    hass.data.setdefault(DOMAIN, {})

    address = entry.data.get(CONF_DEVICE_ADDRESS, entry.data.get(CONF_ADDRESS, ""))
    name = entry.data.get(CONF_DEVICE_NAME, entry.data.get(CONF_NAME, "家超睡眠灯"))
    protocol_type = entry.data.get(CONF_PROTOCOL, "jiachao_default")

    # 获取 UUID 配置
    preset = PROTOCOL_PRESETS.get(protocol_type, PROTOCOL_PRESETS["jiachao_default"])
    if protocol_type == "custom":
        service_uuid = entry.data.get(CONF_CUSTOM_SERVICE_UUID, preset["service_uuid"])
        write_uuid = entry.data.get(CONF_CUSTOM_WRITE_UUID, preset["write_uuid"])
        notify_uuid = entry.data.get(CONF_CUSTOM_NOTIFY_UUID, preset["notify_uuid"])
    else:
        service_uuid = preset["service_uuid"]
        write_uuid = preset["write_uuid"]
        notify_uuid = preset["notify_uuid"]

    # 创建协议处理器
    protocol = BLELightProtocol(protocol_type=protocol_type)

    # 创建设备实例
    device = BLELightDevice(
        address=address,
        service_uuid=service_uuid,
        write_uuid=write_uuid,
        notify_uuid=notify_uuid,
        protocol=protocol,
        name=name,
    )

    # 尝试连接
    try:
        connected = await device.connect()
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady(f"连接设备失败: {err}") from err

    if not connected:
        # 连接失败但不阻止设置，设备会在后续轮询中重连
        _LOGGER.warning("初始连接失败，设备将在后续尝试重连: %s", address)

    hass.data[DOMAIN][entry.entry_id] = device

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载 config entry。"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    device: BLELightDevice | None = hass.data[DOMAIN].get(entry.entry_id)
    if device:
        await device.disconnect()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
