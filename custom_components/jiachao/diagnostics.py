"""诊断信息导出（用户报 bug 时可在「集成 → 三点 → 下载诊断信息」一键获取）。

脱敏原则：token / 密码 / MQTT 凭据 / 设备 UUID 一律不上传，
只保留排查问题必需的结构性信息（版本、设备型号、连接状态、脱敏后的 topic）。
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# 不导出明文的敏感字段（完全打码）
REDACTED_KEYS = {
    "token",
    "password",
    "username",
    "device_uuid",
    "mqtt_token",
    "user_id",
}

# 部分打码：保留末 4 位便于对照日志，其余遮蔽
PARTIALLY_REDACTED_KEYS = {"device_id"}


def _mask_id(value: str) -> str:
    """长 ID 只保留末 4 位。"""
    value = str(value)
    if len(value) <= 4:
        return "****"
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _redact(value: Any) -> Any:
    """递归脱敏：字典按键名打码，字符串保留首尾用于比对但不泄漏全文。"""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = k.lower()
            if key in REDACTED_KEYS:
                out[k] = "**REDACTED**"
            elif key in PARTIALLY_REDACTED_KEYS and isinstance(v, str):
                out[k] = _mask_id(v)
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _mask_topic(topic: str) -> str:
    """topic 中的 deviceId 打码，保留结构便于排查订阅是否正常。"""
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0] == "smart":
        parts[1] = f"<device:{len(parts[1])}>"
    return "/".join(parts)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """返回单个配置条目的诊断信息。"""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = _redact(dict(entry.data))
    options = _redact(dict(entry.options))

    if coordinator is None:
        return {
            "entry": {"data": data, "options": options},
            "coordinator": None,
            "note": "集成未加载（coordinator 不存在）",
        }

    mqtt = coordinator.mqtt
    return {
        "entry": {
            "data": data,
            "options": options,
            "version": entry.version,
            "minor_version": entry.minor_version,
        },
        "coordinator": {
            "device_model": coordinator.device_model,
            "device_alias": coordinator.device_alias,
            "mqtt_connected": coordinator.is_mqtt_connected(),
            "command_topic": _mask_topic(mqtt._cmd_topic),
            "state_topic_prefix": _mask_topic(mqtt._state_prefix),
            "keepalive": 60,
        },
    }
