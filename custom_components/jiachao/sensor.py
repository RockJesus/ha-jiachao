"""Sensor platform for 家超."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .api import JiachaoClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 家超 sensors based on a config entry."""
    client: JiachaoClient = hass.data[DOMAIN][entry.entry_id]

    entities = [
        JiachaoUserSensor(client, entry.entry_id),
    ]

    async_add_entities(entities)


class JiachaoUserSensor(SensorEntity):
    """Sensor for 家超 user info."""

    _attr_has_entity_name = True
    _attr_name = "用户信息"
    _attr_icon = "mdi:account"

    def __init__(
        self,
        client: JiachaoClient,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._client = client
        self._entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_user_info"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="家超账号",
            manufacturer="家超",
            model="智能家居平台",
            sw_version="0.1.0",
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._client.nickname or self._client.username

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "user_id": self._client.user_id,
            "nickname": self._client.nickname,
            "avatar": self._client.avatar,
        }
