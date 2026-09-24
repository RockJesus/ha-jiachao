"""家超智能灯（JiaChao）Home Assistant 集成。

账号密码登录家超云 → 发现设备 → MQTT(TLS) 连接 → 控制开关/亮度/颜色。
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JiaChaoAPI
from .const import DOMAIN, PLATFORMS
from .coordinator import JiaChaoCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置集成入口：建 API、取设备详情、连 MQTT。"""
    api = JiaChaoAPI(async_get_clientsession(hass))
    token = entry.data.get("token", "")
    user_id = entry.data.get("user_id", "")
    if token:
        api._token = token  # 使用配置保存的登录 token
    else:
        # 无 token 时用账号密码重新登录（沿用配置里持久化的用户独立 uuid，减少二次验证）
        try:
            device_uuid = entry.data.get("device_uuid", "")
            login_result = await api.login(
                entry.data["username"], entry.data["password"],
                uuid_val=device_uuid or None,
            )
            token = login_result.get("token", "")
            user_id = login_result.get("userId", user_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "jiachao 重新登录失败（若提示需要短信验证码，请在集成配置里重新输入账号密码"
                "或填入自己的设备 UUID）: %s", err)
            return False

    # 设备信息（含 mqtt 凭据）
    try:
        device_info = await api.get_device_info(entry.data.get("device_id", ""))
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("jiachao deviceInfo failed: %s", err)
        device_info = {}

    # 设备对象：优先从配置保存的列表里取，其次 deviceInfo
    device = entry.data.get("_device") or {}
    if not device and device_info:
        device = device_info.get("device", device_info)

    options = {
        "user_id": str(user_id),
    }
    coordinator = JiaChaoCoordinator(hass, api, device, device_info, options)

    # MQTT 连接放执行器线程（阻塞握手）
    await hass.async_add_executor_job(coordinator.connect_mqtt)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载：断开 MQTT。"""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator:
        await hass.async_add_executor_job(coordinator.mqtt.disconnect)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
