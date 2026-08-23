"""家超睡眠灯 - 配置流程"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

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

_LOGGER = logging.getLogger(__name__)

# 家超设备可能的本地名称前缀
JIACHAO_NAME_PREFIXES = ("JiaChao", "JIACHao", "jiachao", "LT-", "Sleep", "SLEEP")


def _is_jiachao_device(name: str | None) -> bool:
    """判断设备名称是否可能是家超设备。"""
    if not name:
        return False
    return any(name.startswith(prefix) for prefix in JIACHAO_NAME_PREFIXES)


class JiaChaoLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """家超睡眠灯配置流程。"""

    VERSION = 1

    def __init__(self) -> None:
        """初始化配置流程。"""
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._selected_address: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """处理蓝牙发现。"""
        if discovery_info.address is None:
            return self.async_abort(reason="no_address")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        # 检查是否是家超设备
        name = discovery_info.name or "未知设备"
        if not _is_jiachao_device(name):
            # 非明确家超设备也允许用户手动确认
            _LOGGER.debug("发现可能的家超设备: %s (%s)", name, discovery_info.address)

        self.context["title_placeholders"] = {"name": name}
        self._selected_address = discovery_info.address

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """用户手动配置步骤。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input.get(CONF_DEVICE_ADDRESS, "")
            if not address:
                errors[CONF_DEVICE_ADDRESS] = "需要填写设备 MAC 地址"
            else:
                # 检查是否已配置
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                protocol_type = user_input.get(CONF_PROTOCOL, "jiachao_default")

                # 如果选择自定义协议，跳转到自定义 UUID 步骤
                if protocol_type == "custom":
                    self._selected_address = address
                    self.context["device_name"] = user_input.get(CONF_DEVICE_NAME, "家超睡眠灯")
                    self.context["protocol"] = protocol_type
                    return await self.async_step_custom_uuid()

                return self.async_create_entry(
                    title=user_input.get(CONF_DEVICE_NAME, "家超睡眠灯"),
                    data={
                        CONF_DEVICE_ADDRESS: address,
                        CONF_DEVICE_NAME: user_input.get(CONF_DEVICE_NAME, "家超睡眠灯"),
                        CONF_PROTOCOL: protocol_type,
                    },
                )

        # 收集已发现的蓝牙设备
        discovered = []
        for service_info in async_discovered_service_info(self.hass):
            if service_info.address:
                name = service_info.name or "未知设备"
                discovered.append((service_info.address, f"{name} ({service_info.address})"))
                self._discovered_devices[service_info.address] = service_info

        # 构建协议选项
        protocol_options = {
            key: value["name"] for key, value in PROTOCOL_PRESETS.items()
        }

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_ADDRESS,
                    default=self._selected_address or "",
                ): str,
                vol.Optional(
                    CONF_DEVICE_NAME,
                    default="家超睡眠灯",
                ): str,
                vol.Required(
                    CONF_PROTOCOL,
                    default="jiachao_default",
                ): vol.In(protocol_options),
            }
        )

        # 如果有发现的设备，在描述中提示
        description_placeholders = {}
        if discovered:
            device_list = "\n".join(f"- {name}" for _, name in discovered[:5])
            description_placeholders["discovered_devices"] = device_list

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_custom_uuid(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """自定义 UUID 配置步骤。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            service_uuid = user_input.get(CONF_CUSTOM_SERVICE_UUID, "")
            write_uuid = user_input.get(CONF_CUSTOM_WRITE_UUID, "")

            if not service_uuid:
                errors[CONF_CUSTOM_SERVICE_UUID] = "需要填写 Service UUID"
            if not write_uuid:
                errors[CONF_CUSTOM_WRITE_UUID] = "需要填写 Write Characteristic UUID"

            if not errors:
                return self.async_create_entry(
                    title=self.context.get("device_name", "家超睡眠灯"),
                    data={
                        CONF_DEVICE_ADDRESS: self._selected_address,
                        CONF_DEVICE_NAME: self.context.get("device_name", "家超睡眠灯"),
                        CONF_PROTOCOL: "custom",
                        CONF_CUSTOM_SERVICE_UUID: service_uuid,
                        CONF_CUSTOM_WRITE_UUID: write_uuid,
                        CONF_CUSTOM_NOTIFY_UUID: user_input.get(CONF_CUSTOM_NOTIFY_UUID, ""),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CUSTOM_SERVICE_UUID): str,
                vol.Required(CONF_CUSTOM_WRITE_UUID): str,
                vol.Optional(CONF_CUSTOM_NOTIFY_UUID, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="custom_uuid",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "guide": "使用 nRF Connect 连接设备后，查看 GATT 服务列表。\n"
                "Service UUID: 包含控制特征的服务 UUID\n"
                "Write UUID: 用于发送控制命令的特征 UUID\n"
                "Notify UUID: 用于接收设备状态通知的特征 UUID（可选）",
            },
        )
