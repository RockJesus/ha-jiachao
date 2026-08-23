"""家超睡眠灯 - Light 实体平台"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    SUPPORTED_EFFECTS,
)
from .device import BLELightDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """通过 config flow 设置灯实体。"""
    device: BLELightDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JiaChaoLightEntity(device, entry)], update_before_add=True)


class JiaChaoLightEntity(LightEntity):
    """家超睡眠灯实体。"""

    _attr_has_entity_name = True
    _attr_should_poll = True
    _attr_supported_color_modes = {
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
        ColorMode.BRIGHTNESS,
        ColorMode.ONOFF,
    }
    _attr_color_mode = ColorMode.RGB
    _attr_effect_list = SUPPORTED_EFFECTS

    def __init__(self, device: BLELightDevice, entry: ConfigEntry) -> None:
        """初始化灯实体。"""
        self._device = device
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{format_mac(device.address)}"
        self._attr_name = device.name or DEFAULT_NAME
        self._attr_device_info = {
            "identifiers": {(DOMAIN, format_mac(device.address))},
            "name": device.name or DEFAULT_NAME,
            "manufacturer": "家超",
            "model": "睡眠灯 BLE",
            "connections": {("mac", device.address)},
        }
        self._attr_available = False

        # 注册断开连接回调
        device.set_disconnect_listener(self._on_device_disconnected)

    @callback
    def _on_device_disconnected(self, address: str) -> None:
        """设备断开连接时标记不可用。"""
        self._attr_available = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """实体添加到 HA 时尝试连接。"""
        await super().async_added_to_hass()
        if not self._device.is_connected:
            await self._device.connect()
        self._attr_available = self._device.is_connected

    async def async_will_remove_from_hass(self) -> None:
        """实体移除时断开连接。"""
        await self._device.disconnect()
        await super().async_will_remove_from_hass()

    async def async_update(self) -> None:
        """更新设备状态。"""
        if not self._device.is_connected:
            connected = await self._device.connect()
            self._attr_available = connected
            if not connected:
                return
        else:
            self._attr_available = True

        await self._device.update_status()

        # 同步状态
        self._attr_is_on = self._device.is_on
        self._attr_brightness = self._device.brightness

        if self._device.color_mode == "rgb":
            self._attr_color_mode = ColorMode.RGB
            self._attr_rgb_color = self._device.rgb_color
        elif self._device.color_mode == "color_temp":
            self._attr_color_mode = ColorMode.COLOR_TEMP
            if self._device.color_temp:
                self._attr_color_temp = self._device.color_temp

        if self._device.effect:
            self._attr_effect = self._device.effect
        else:
            self._attr_effect = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """开灯并设置参数。"""
        if not self._device.is_connected:
            if not await self._device.connect():
                _LOGGER.warning("无法连接到设备 %s", self._device.address)
                return

        # 先开灯
        await self._device.turn_on()

        # 处理亮度
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            await self._device.set_brightness(brightness)

        # 处理 RGB 颜色
        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            brightness = kwargs.get(ATTR_BRIGHTNESS, self._device.brightness)
            await self._device.set_rgb_color(r, g, b, brightness)

        # 处理色温
        if ATTR_COLOR_TEMP in kwargs:
            temp = kwargs[ATTR_COLOR_TEMP]
            brightness = kwargs.get(ATTR_BRIGHTNESS, self._device.brightness)
            await self._device.set_color_temp(temp, brightness)

        # 处理效果
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            await self._device.set_effect(effect)

        # 更新状态
        self._attr_is_on = True
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关灯。"""
        if not self._device.is_connected:
            if not await self._device.connect():
                return
        await self._device.turn_off()
        self._attr_is_on = False
        self.async_write_ha_state()
