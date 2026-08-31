"""The 家超睡眠灯 integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JiachaoAPI, JiachaoAPIError
from .const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME, DATA_VOLUME, DATA_WHITE_NOISE, DOMAIN
from .mqtt_client import JiachaoMQTTClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]

# Service schemas
SERVICE_SET_WHITE_NOISE = "set_white_noise"
SERVICE_SET_VOLUME = "set_volume"

ATTR_NOISE_ID = "noise_id"
ATTR_VOLUME = "volume"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SET_WHITE_NOISE_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_NOISE_ID): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)

SET_VOLUME_SCHEMA = SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_VOLUME): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 家超睡眠灯 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    api = JiachaoAPI(session)

    # Login
    try:
        await api.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except JiachaoAPIError as err:
        _LOGGER.error("Failed to login to 家超 cloud: %s", err)
        return False

    # Get MQTT config
    try:
        mqtt_config = await api.get_mqtt_config()
    except JiachaoAPIError as err:
        _LOGGER.error("Failed to get MQTT config: %s", err)
        return False

    device_id = entry.data[CONF_DEVICE_ID]

    # Create MQTT client
    mqtt_client = JiachaoMQTTClient(
        host=mqtt_config["host"],
        port=mqtt_config["port"],
        username=mqtt_config["username"],
        password=mqtt_config["password"],
        client_id=mqtt_config["client_id"],
        use_tls=mqtt_config["use_tls"],
    )

    # Store coordinator data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "mqtt": mqtt_client,
        "device_id": device_id,
        "device_info": entry.data.get("device_info", {}),
        "device_name": entry.data.get("device_name", "家超睡眠灯"),
    }

    # Connect MQTT
    try:
        await mqtt_client.connect()
        await mqtt_client.subscribe_device(device_id)
    except ConnectionError as err:
        _LOGGER.error("Failed to connect MQTT: %s", err)
        # Don't fail setup - light entity will show unavailable

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_register_services(hass, entry)

    return True


async def _async_register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register integration services."""

    async def async_set_white_noise(call: ServiceCall) -> None:
        """Handle set_white_noise service call."""
        entity_ids = call.data[ATTR_ENTITY_ID]
        noise_id = call.data[ATTR_NOISE_ID]
        await _async_send_to_entities(hass, entry, entity_ids, {DATA_WHITE_NOISE: noise_id})

    async def async_set_volume(call: ServiceCall) -> None:
        """Handle set_volume service call."""
        entity_ids = call.data[ATTR_ENTITY_ID]
        volume = call.data[ATTR_VOLUME]
        await _async_send_to_entities(hass, entry, entity_ids, {DATA_VOLUME: volume})

    hass.services.async_register(
        DOMAIN, SERVICE_SET_WHITE_NOISE, async_set_white_noise, schema=SET_WHITE_NOISE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_VOLUME, async_set_volume, schema=SET_VOLUME_SCHEMA
    )


async def _async_send_to_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entity_ids: list[str],
    command: dict[str, Any],
) -> None:
    """Send a command to specified light entities."""
    from homeassistant.helpers import entity_registry as er

    entity_reg = er.async_get(hass)
    data = hass.data[DOMAIN][entry.entry_id]
    mqtt_client: JiachaoMQTTClient = data["mqtt"]
    device_id = data["device_id"]

    for entity_id in entity_ids:
        entry_reg = entity_reg.async_get(entity_id)
        if entry_reg and entry_reg.config_entry_id == entry.entry_id:
            try:
                await mqtt_client.send_control(device_id, command)
            except ConnectionError as err:
                _LOGGER.error("Failed to send command to %s: %s", device_id, err)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove services if no other config entries exist
        if not any(
            e.domain == DOMAIN for e in hass.config_entries.async_entries() if e.entry_id != entry.entry_id
        ):
            hass.services.async_remove(DOMAIN, SERVICE_SET_WHITE_NOISE)
            hass.services.async_remove(DOMAIN, SERVICE_SET_VOLUME)

        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data and "mqtt" in data:
            await data["mqtt"].disconnect()

    return unload_ok
