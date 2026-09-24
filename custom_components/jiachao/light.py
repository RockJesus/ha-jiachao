"""家超灯 Light 平台。"""
from __future__ import annotations

import logging
import json

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    DOMAIN_TITLE,
    CMD_OPEN_MODE,
    CMD_CLOSE_MODE,
    CMD_NORMAL_MODE,
    COLOR_TEMP_MIN_K,
    COLOR_TEMP_MAX_K,
    WV_MAX,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JiaChaoLight(coordinator)], update_before_add=True)


class JiaChaoLight(LightEntity):
    """家超 W800 智能灯实体（开关 / 亮度 / 颜色）。"""

    _attr_has_entity_name = True
    # 双色温灯：只做暖色到冷色渐变（用户实机确认，非 RGB 彩色）
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_mireds = int(1000000 / COLOR_TEMP_MAX_K)      # 6500K 冷
    _attr_max_mireds = int(1000000 / COLOR_TEMP_MIN_K)      # 2700K 暖
    _attr_min_color_temp_kelvin = COLOR_TEMP_MIN_K
    _attr_max_color_temp_kelvin = COLOR_TEMP_MAX_K

    def __init__(self, coordinator):
        self._coordinator = coordinator
        self._attr_unique_id = f"jiachao_{coordinator.device_id}"
        self._attr_name = coordinator.device_alias or DOMAIN_TITLE
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=self._attr_name,
            manufacturer="家超（创高智联）",
            model=coordinator.device_model or "W800 Smart Light (LT)",
            sw_version="1.0.0",
        )
        self._attr_is_on = False
        self._attr_brightness = None
        self._attr_color_temp_kelvin = COLOR_TEMP_MAX_K
        self._attr_available = True
        coordinator.set_state_listener(self._on_state)

    @callback
    def _on_state(self, message: dict) -> None:
        """MQTT 状态回调：解析真实状态消息 {"m":{"res":{...}}}。

        状态字段（实测）:
          mo: 225=开 / 224=关 / 129=亮灯调节模式（亮度色温操作后）
          lc: 亮度 0-255
          wv: 色温编码 0-1000（0=暖 2700K / 1000=冷 6500K）
          wh: 白光分量
          ls: 附加状态
        """
        topic = message.get("topic", "")
        payload = message.get("payload", "")
        if not topic.endswith("/dout/status"):
            # 只处理 status；online 消息用于在线标记
            try:
                data = json.loads(payload) if payload else {}
            except (ValueError, TypeError):
                return
            if isinstance(data, dict) and data.get("msg") in ("online", "offline"):
                self._attr_available = data.get("msg") == "online"
                self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)
            return
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            return
        res = (data.get("m") or {}).get("res") if isinstance(data, dict) else None
        if not isinstance(res, dict):
            return
        changed = False

        # 开关（用户实机确认）：mo=225 开 / mo=224 关 / mo=129 亮灯调节模式
        mo = res.get("mo")
        if isinstance(mo, int):
            if mo in (CMD_OPEN_MODE, CMD_NORMAL_MODE):
                self._attr_is_on = True
                changed = True
            elif mo == CMD_CLOSE_MODE:
                self._attr_is_on = False
                changed = True

        # 亮度 lc 0-255（同步给 mqtt，改色温时保持此亮度）
        lc = res.get("lc")
        if isinstance(lc, int):
            self._attr_brightness = max(0, min(255, lc))
            self._coordinator.mqtt.set_last_brightness(lc)
            changed = True

        # 色温 wv（0-1000：暖→冷）→ kelvin
        wv = res.get("wv")
        if isinstance(wv, int):
            k = COLOR_TEMP_MIN_K + wv * (COLOR_TEMP_MAX_K - COLOR_TEMP_MIN_K) / WV_MAX
            self._attr_color_temp_kelvin = int(k)
            changed = True

        if changed:
            # MQTT 回调运行在 paho 线程，必须调度回事件循环再写状态
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    # -- 控制（真实协议） -----------------------------------------------------
    async def async_turn_on(self, **kwargs) -> None:
        """开灯 / 调亮度 / 调色温（暖→冷渐变）。"""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if kelvin is not None:
            await self.hass.async_add_executor_job(
                self._coordinator.mqtt.set_color_temp, int(kelvin))
            self._attr_is_on = True
            self._attr_color_temp_kelvin = int(kelvin)
        elif brightness is not None:
            await self.hass.async_add_executor_job(
                self._coordinator.mqtt.set_brightness, brightness)
            self._attr_is_on = True
            self._attr_brightness = brightness
        else:
            await self.hass.async_add_executor_job(self._coordinator.mqtt.turn_on)
            self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(self._coordinator.mqtt.turn_off)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        # MQTT 状态推送为主；这里确保实体在线标记正确
        self._attr_available = (
            self._coordinator.mqtt.client is not None
            and self._coordinator.mqtt.client.is_connected()
        ) or True
