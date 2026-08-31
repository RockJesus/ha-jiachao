"""家超睡眠灯 light platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_BRIGHTNESS,
    DATA_COLOR,
    DATA_COLOR_TEMP,
    DATA_DEVICE_ID,
    DATA_DEVICE_NAME,
    DATA_DEVICE_TYPE,
    DATA_FW_VERSION,
    DATA_HW_VERSION,
    DATA_MODEL,
    DATA_ONLINE,
    DATA_POWER,
    DATA_SCENE,
    DATA_VOLUME,
    DATA_WHITE_NOISE,
    DOMAIN,
    EFFECT_COOL,
    EFFECT_FOCUS,
    EFFECT_NIGHT,
    EFFECT_PARTY,
    EFFECT_READING,
    EFFECT_RELAX,
    EFFECT_ROMANTIC,
    EFFECT_SLEEP,
    EFFECT_WARM,
)
from .mqtt_client import JiachaoMQTTClient

_LOGGER = logging.getLogger(__name__)

# Effect list mapped to device scene IDs
EFFECT_LIST = [
    EFFECT_READING,
    EFFECT_RELAX,
    EFFECT_SLEEP,
    EFFECT_NIGHT,
    EFFECT_FOCUS,
    EFFECT_WARM,
    EFFECT_COOL,
    EFFECT_ROMANTIC,
    EFFECT_PARTY,
]

# Effect display names
EFFECT_NAMES = {
    EFFECT_READING: "阅读",
    EFFECT_RELAX: "放松",
    EFFECT_SLEEP: "睡眠",
    EFFECT_NIGHT: "夜灯",
    EFFECT_FOCUS: "专注",
    EFFECT_WARM: "暖光",
    EFFECT_COOL: "冷光",
    EFFECT_ROMANTIC: "浪漫",
    EFFECT_PARTY: "派对",
}

# Color temperature range (mireds)
MIN_MIREDS = 153  # 6500K
MAX_MIREDS = 500  # 2000K


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 家超睡眠灯 from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    mqtt_client: JiachaoMQTTClient = data["mqtt"]
    device_id = data["device_id"]
    device_info = data.get("device_info", {})
    device_name = data.get("device_name", "家超睡眠灯")

    light = JiachaoLight(
        mqtt_client=mqtt_client,
        device_id=device_id,
        device_name=device_name,
        device_info=device_info,
    )

    # Register callbacks
    mqtt_client.register_status_callback(device_id, light._on_status_update)
    mqtt_client.register_online_callback(device_id, light._on_online_update)

    async_add_entities([light])


class JiachaoLight(LightEntity):
    """Representation of a 家超睡眠灯."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {
        ColorMode.BRIGHTNESS,
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    }
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = [EFFECT_NAMES.get(e, e) for e in EFFECT_LIST]
    _attr_min_mireds = MIN_MIREDS
    _attr_max_mireds = MAX_MIREDS

    def __init__(
        self,
        mqtt_client: JiachaoMQTTClient,
        device_id: str,
        device_name: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the light."""
        self._mqtt = mqtt_client
        self._device_id = device_id
        self._device_name = device_name
        self._device_info = device_info

        # State
        self._is_on = False
        self._brightness = 255
        self._color_temp = None
        self._hs_color = None
        self._effect = None
        self._available = False
        self._volume = 50
        self._white_noise = None

        # Device identifiers
        model = device_info.get(DATA_MODEL, device_info.get("productKey", "LT800"))
        fw_version = device_info.get(DATA_FW_VERSION, device_info.get("softwareVersion", ""))
        hw_version = device_info.get(DATA_HW_VERSION, device_info.get("hardwareVersion", ""))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="家超 (Jiachao)",
            model=model,
            sw_version=fw_version or None,
            hw_version=hw_version or None,
        )
        self._attr_unique_id = f"{DOMAIN}_{device_id}_light"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available and self._mqtt.connected

    @property
    def is_on(self) -> bool:
        """Return True if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds."""
        return self._color_temp

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._effect:
            return EFFECT_NAMES.get(self._effect, self._effect)
        return None

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        if self._hs_color is not None:
            return ColorMode.HS
        if self._color_temp is not None:
            return ColorMode.COLOR_TEMP
        return ColorMode.BRIGHTNESS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attrs = {}
        if self._volume is not None:
            attrs["volume"] = self._volume
        if self._white_noise is not None:
            attrs["white_noise"] = self._white_noise
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        command: dict[str, Any] = {DATA_POWER: True}

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            self._brightness = brightness
            command[DATA_BRIGHTNESS] = round(brightness * 100 / 255)

        if ATTR_COLOR_TEMP in kwargs:
            ct = kwargs[ATTR_COLOR_TEMP]
            self._color_temp = ct
            self._hs_color = None
            # Convert mireds to Kelvin
            kelvin = round(1000000 / ct)
            command[DATA_COLOR_TEMP] = kelvin

        if ATTR_HS_COLOR in kwargs:
            hs = kwargs[ATTR_HS_COLOR]
            self._hs_color = hs
            self._color_temp = None
            command[DATA_COLOR] = {
                "hue": round(hs[0]),
                "saturation": round(hs[1]),
            }

        if ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            # Reverse lookup effect ID
            effect_id = next(
                (k for k, v in EFFECT_NAMES.items() if v == effect_name),
                effect_name,
            )
            self._effect = effect_id
            command[DATA_SCENE] = effect_id

        _LOGGER.debug("Turn on command: %s", command)
        await self._send_command(command)

        # Update local state immediately for responsiveness
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        command = {DATA_POWER: False}
        _LOGGER.debug("Turn off command")
        await self._send_command(command)
        self._is_on = False
        self.async_write_ha_state()

    async def _send_command(self, command: dict[str, Any]) -> None:
        """Send a command to the device via MQTT."""
        try:
            await self._mqtt.send_control(self._device_id, command)
        except ConnectionError as err:
            _LOGGER.error("Failed to send command to %s: %s", self._device_id, err)
            self._available = False
            self.async_write_ha_state()

    @callback
    def _on_status_update(self, data: dict[str, Any]) -> None:
        """Handle status update from MQTT."""
        _LOGGER.debug("Status update for %s: %s", self._device_id, data)

        changed = False

        if DATA_POWER in data:
            new_state = bool(data[DATA_POWER])
            if new_state != self._is_on:
                self._is_on = new_state
                changed = True

        if DATA_BRIGHTNESS in data:
            brightness_pct = data[DATA_BRIGHTNESS]
            if isinstance(brightness_pct, (int, float)):
                new_brightness = round(brightness_pct * 255 / 100)
                if new_brightness != self._brightness:
                    self._brightness = new_brightness
                    changed = True

        if DATA_COLOR_TEMP in data:
            kelvin = data[DATA_COLOR_TEMP]
            if isinstance(kelvin, (int, float)) and kelvin > 0:
                new_ct = round(1000000 / kelvin)
                new_ct = max(MIN_MIREDS, min(MAX_MIREDS, new_ct))
                if new_ct != self._color_temp:
                    self._color_temp = new_ct
                    self._hs_color = None
                    changed = True

        if DATA_COLOR in data:
            color = data[DATA_COLOR]
            if isinstance(color, dict):
                hue = color.get("hue", color.get("h", 0))
                sat = color.get("saturation", color.get("s", 0))
                new_hs = (float(hue), float(sat))
                if new_hs != self._hs_color:
                    self._hs_color = new_hs
                    self._color_temp = None
                    changed = True

        if DATA_SCENE in data:
            scene = data[DATA_SCENE]
            if scene != self._effect:
                self._effect = scene
                changed = True

        if DATA_VOLUME in data:
            self._volume = data[DATA_VOLUME]
            changed = True

        if DATA_WHITE_NOISE in data:
            self._white_noise = data[DATA_WHITE_NOISE]
            changed = True

        if changed:
            self.async_write_ha_state()

    @callback
    def _on_online_update(self, data: dict[str, Any]) -> None:
        """Handle online/offline update from MQTT."""
        _LOGGER.debug("Online update for %s: %s", self._device_id, data)

        online = data.get(DATA_ONLINE, data.get("online", data.get("status", False)))
        new_available = bool(online)

        if new_available != self._available:
            self._available = new_available
            self.async_write_ha_state()
