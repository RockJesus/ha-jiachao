"""config_flow 单元测试。

覆盖两类曾在 HACS 评审中出问题的分支：
  1. 账号下无设备时，必须返回带 no_devices 错误的表单而不是崩溃
     （历史问题：`await self.async_show_form(...)` 触发 TypeError）
  2. reauth / reconfigure 必须走 async_update_reload_and_abort 立即重载 entry
     （历史问题：只存 token 不重载，集成保持 AuthFailed 错误态直到重启）
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.jiachao.api import JiaChaoAuthError, JiaChaoCodeRequiredError
from custom_components.jiachao.config_flow import SOURCE_RECONFIGURE
from custom_components.jiachao.const import CONF_DEVICE_ID, DOMAIN

SUPPORTED_DEVICE = {
    "ID": "00002500000000000001",
    "alias": "睡眠灯",
    "product_id": 25,
    "dtype": "LT",
    "mqtt": {
        "domain": "dc02-lvs.iotdreamcatcher.net.cn",
        "port": 8883,
        "token": "mqtt-token",
    },
}
UNSUPPORTED_DEVICE = {
    "ID": "00002500000000000002",
    "alias": "RGB 灯带",
    "product_id": 99,
    "dtype": "RGB",
}

USER_INPUT = {CONF_USERNAME: "13800138000", CONF_PASSWORD: "secret"}
DEVICE_INPUT = {CONF_DEVICE_ID: SUPPORTED_DEVICE["ID"]}

ENTRY_DATA = {
    CONF_USERNAME: "13800138000",
    CONF_PASSWORD: "old",
    "token": "old-token",
    "device_id": SUPPORTED_DEVICE["ID"],
    "device_uuid": "fixed-uuid",
}


@pytest.fixture
def mock_api():
    """Patch JiaChaoAPI，避免真实网络请求。"""
    with patch("custom_components.jiachao.config_flow.JiaChaoAPI") as api_cls:
        api = api_cls.return_value
        api.login = AsyncMock(return_value={"token": "tok", "userId": "42"})
        api.request_login_code = AsyncMock(return_value=None)
        api.login_with_code = AsyncMock(return_value={"token": "tok", "userId": "42"})
        api.get_devices = AsyncMock(return_value=[SUPPORTED_DEVICE])
        api.get_user_info = AsyncMock(return_value={"userId": "42"})
        yield api


def _make_entry(hass: HomeAssistant, entry_id: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="家超 睡眠灯",
        data=dict(ENTRY_DATA),
        source=config_entries.SOURCE_USER,
        unique_id=SUPPORTED_DEVICE["ID"],
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


async def test_user_step_shows_form(hass: HomeAssistant, mock_api) -> None:
    """首次进入应展示账号密码表单。"""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_login_failure_shows_invalid_auth(hass: HomeAssistant, mock_api) -> None:
    """登录失败应回到表单并提示 invalid_auth，而不是抛异常。"""
    mock_api.login.side_effect = JiaChaoAuthError("bad password")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_no_devices_returns_form_without_crash(
    hass: HomeAssistant, mock_api
) -> None:
    """账号下无设备：必须返回带 no_devices 错误的表单。

    回归测试：旧版此处写了 `return await self.async_show_form(...)`，
    async_show_form 不是协程，await 会抛 TypeError 导致流程崩溃。
    """
    mock_api.get_devices.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_full_setup_creates_entry(hass: HomeAssistant, mock_api) -> None:
    """完整流程：登录 → 选设备 → 创建 entry。

    同时回归 HA 2024.1 兼容性：早期版本没有 config_entries.SOURCE_RECONFIGURE，
    直接取属性会让新建流程在走到 device 步骤时抛 AttributeError。
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["step_id"] == "device"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], DEVICE_INPUT)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == SUPPORTED_DEVICE["ID"]
    assert result["data"]["token"] == "tok"


async def test_unsupported_device_rejected(hass: HomeAssistant, mock_api) -> None:
    """选择待支持型号应明确报错，不静默通过。"""
    mock_api.get_devices.return_value = [SUPPORTED_DEVICE, UNSUPPORTED_DEVICE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: UNSUPPORTED_DEVICE["ID"]}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "device_unsupported"}


async def test_code_required_flow(hass: HomeAssistant, mock_api) -> None:
    """新设备登录要求短信验证：应自动进入验证码步骤。"""
    mock_api.login.side_effect = JiaChaoCodeRequiredError("need code")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "code"
    mock_api.request_login_code.assert_awaited_once()


async def test_reauth_reloads_entry(hass: HomeAssistant, mock_api) -> None:
    """reauth 成功后必须重载 entry（回归：旧版只存 token 不重载）。"""
    entry = _make_entry(hass, "test-entry")

    # reauth 没有独立的表单步骤：async_init 传入的 data 会直接喂给 async_step_user
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=dict(USER_INPUT),
    )
    assert result["step_id"] == "device"

    with patch(
        "custom_components.jiachao.config_flow.JiaChaoConfigFlow."
        "async_update_reload_and_abort"
    ) as mocked:
        mocked.return_value = {
            "type": FlowResultType.ABORT,
            "reason": "reauth_successful",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_INPUT
        )
        assert mocked.called, "reauth 必须调用 async_update_reload_and_abort"
        kwargs = mocked.call_args.kwargs
        assert kwargs["unique_id"] == SUPPORTED_DEVICE["ID"], "unique_id 应匹配所选设备"
        assert kwargs["reason"] == "reauth_successful"

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_keeps_saved_device_uuid(hass: HomeAssistant, mock_api) -> None:
    """reauth 应沿用已保存的 device_uuid，避免用户再次收验证码。"""
    entry = _make_entry(hass, "test-entry-uuid")

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=dict(USER_INPUT),
    )

    uuid_used = mock_api.login.await_args.kwargs["uuid_val"]
    assert uuid_used == "fixed-uuid", "应沿用 entry 中已保存的 device_uuid"


async def test_reconfigure_reloads_entry(hass: HomeAssistant, mock_api) -> None:
    """reconfigure 成功后同样必须重载 entry。"""
    entry = _make_entry(hass, "test-entry-2")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["step_id"] == "device"

    with patch(
        "custom_components.jiachao.config_flow.JiaChaoConfigFlow."
        "async_update_reload_and_abort"
    ) as mocked:
        mocked.return_value = {
            "type": FlowResultType.ABORT,
            "reason": "reconfigure_successful",
        }
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEVICE_INPUT
        )
        assert mocked.called, "reconfigure 必须调用 async_update_reload_and_abort"

    assert result["reason"] == "reconfigure_successful"
