"""diagnostics 脱敏测试。

诊断包会被用户直接粘贴到 issue 里，必须确保不泄漏 token / 密码 / 设备 UUID。
"""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.jiachao.const import DOMAIN
from custom_components.jiachao.diagnostics import (
    _mask_topic,
    _redact,
    async_get_config_entry_diagnostics,
)


def test_redact_nested_fields() -> None:
    """嵌套结构里的敏感键也必须打码。"""
    payload = {
        "token": "secret-token",
        "username": "13800138000",
        "password": "pwd",
        "device_uuid": "uuid-1234",
        "device_id": "00002500000000000001",
        "nested": {"mqtt_token": "abc", "port": 8883},
        "list": [{"token": "x"}, {"port": 1}],
    }
    out = _redact(payload)

    assert out["token"] == "**REDACTED**"
    assert out["username"] == "**REDACTED**"
    assert out["password"] == "**REDACTED**"
    assert out["device_uuid"] == "**REDACTED**"
    assert out["nested"]["mqtt_token"] == "**REDACTED**"
    assert out["list"][0]["token"] == "**REDACTED**"
    # 非敏感字段保留
    assert out["nested"]["port"] == 8883
    assert out["list"][1]["port"] == 1
    # device_id 部分打码（保留末 4 位）
    assert out["device_id"] == "****************0001"


def test_mask_topic_hides_device_id() -> None:
    """topic 中的 deviceId 应被替换为长度占位符。"""
    masked = _mask_topic("smart/00002500000000000001/dc/25/din/config")
    assert "00002500000000000001" not in masked
    assert masked.startswith("smart/<device:")
    assert masked.endswith("/dc/25/din/config")
    # 非 smart 前缀原样返回
    assert _mask_topic("other/topic") == "other/topic"


async def test_diagnostics_redacts_entry_data(hass: HomeAssistant) -> None:
    """诊断输出中不得出现明文 token / 密码 / UUID。"""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": "super-secret-token",
            "username": "13800138000",
            "password": "super-secret-pwd",
            "device_uuid": "super-secret-uuid",
            "user_id": "42",
            "device_id": "00002500000000000001",
        },
        entry_id="diag-entry",
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.device_model = "W800 Smart Light (LT)"
    coordinator.device_alias = "睡眠灯"
    coordinator.is_mqtt_connected.return_value = True
    coordinator.mqtt._cmd_topic = "smart/00002500000000000001/dc/25/din/config"
    coordinator.mqtt._state_prefix = "smart/00002500000000000001/dc/25/dout/#"
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    diag = await async_get_config_entry_diagnostics(hass, entry)
    dumped = str(diag)

    assert "super-secret-token" not in dumped
    assert "super-secret-pwd" not in dumped
    assert "super-secret-uuid" not in dumped
    assert "13800138000" not in dumped
    # device_id 部分打码：保留末 4 位便于对照日志，完整值不得出现
    assert "00002500000000000001" not in dumped
    assert diag["entry"]["data"]["device_id"].endswith("0001")
    # 排查所需信息仍保留
    assert diag["coordinator"]["mqtt_connected"] is True
    assert diag["coordinator"]["device_model"] == "W800 Smart Light (LT)"


async def test_diagnostics_without_coordinator(hass: HomeAssistant) -> None:
    """集成未加载时也应返回可用的诊断结果，而不是抛异常。"""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "t", "device_id": "x"},
        entry_id="diag-missing",
    )
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["coordinator"] is None
    assert diag["entry"]["data"]["token"] == "**REDACTED**"
