"""家超智能灯配置流程：账号密码登录 →（如需）短信验证码 → 选择设备。

发布版说明（v1.5.0）：
  - 每个用户【独立设备 UUID】：留空时自动随机生成并持久化，
    首次登录需短信验证码（发到该用户自己的手机），成功后该 UUID 绑定信任，之后免验证码。
  - 高级用户可填自己家超 App 的设备 uuid（抓包获取），密码登录直接免验证码。
  - 不内置任何固定 uuid，避免公开账号的信任关系被其他用户污染。
"""
from __future__ import annotations

import logging
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JiaChaoAPI, JiaChaoCodeRequiredError
from .const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_ID,
    CONF_DEVICE_UUID,
    CONF_SMS_CODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_TRUST_UUID,
    DOMAIN,
    DOMAIN_TITLE,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class JiaChaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """家超集成配置流。"""

    VERSION = 1

    def __init__(self):
        self._api: JiaChaoAPI | None = None
        self._token: str = ""
        self._username: str = ""
        self._password: str = ""
        self._user_id: str = ""
        self._device_uuid: str = ""
        self._devices: list[dict] = []

    # -- 第一步：账号密码 ------------------------------------------------
    async def async_step_user(self, user_input=None):
        """第一步：家超账号密码登录。

        设备 UUID 可留空（自动随机生成，每个用户独立）；
        高级用户可填自己 App 的设备 uuid 直接免验证码。
        若服务器要求短信验证（code=479），自动触发验证码并进入第二步。
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api = JiaChaoAPI(async_get_clientsession(self.hass))
            self._username = user_input.get(CONF_USERNAME, "").strip()
            self._password = user_input.get(CONF_PASSWORD, "")
            # 用户填了 uuid 用用户的；留空自动生成独立随机 uuid
            self._device_uuid = (
                (user_input.get(CONF_DEVICE_UUID) or "").strip()
                or DEFAULT_TRUST_UUID
                or str(uuid.uuid4())
            )
            try:
                login_result = await self._api.login(
                    self._username, self._password,
                    uuid_val=self._device_uuid,
                )
                self._token = login_result.get("token", "")
                self._user_id = login_result.get("userId", "")
            except JiaChaoCodeRequiredError:
                # 新设备需要短信二次验证：触发验证码，进入第二步
                try:
                    await self._api.request_login_code(self._username, self._device_uuid)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("request_login_code error: %s", err)
                    errors["base"] = "code_send_failed"
                if not errors:
                    return await self.async_step_code()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("login error: %s", err)
                errors["base"] = "invalid_auth"
            if not errors and self._token:
                return await self._proceed_to_device()
            if not errors:
                errors["base"] = "invalid_auth"

        schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_DEVICE_UUID, default=""): str,
        })
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"title": DOMAIN_TITLE},
        )

    # -- 第二步：短信验证码 ------------------------------------------------
    async def async_step_code(self, user_input=None):
        """第二步：输入手机收到的短信验证码完成登录。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            sms_code = user_input.get(CONF_SMS_CODE, "").strip()
            try:
                login_result = await self._api.login_with_code(
                    self._username, sms_code, uuid_val=self._device_uuid,
                )
                self._token = login_result.get("token", "")
                self._user_id = login_result.get("userId", "")
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("code login error: %s", err)
                errors["base"] = "invalid_code"
            if self._token:
                return await self._proceed_to_device()

        schema = vol.Schema({
            vol.Required(CONF_SMS_CODE): str,
        })
        return self.async_show_form(
            step_id="code",
            data_schema=schema,
            errors=errors,
            description_placeholders={"title": DOMAIN_TITLE},
        )

    # -- 设备选择 -----------------------------------------------------------
    async def _proceed_to_device(self):
        try:
            self._devices = await self._api.get_devices()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("device list error: %s", err)
            self._devices = []
        lights = [
            d for d in self._devices
            if str(d.get("dtype", "")).upper() in ("LT", "LIGHT")
            or str(d.get("product_id", "")).upper() in ("25",)
        ]
        if lights:
            self._devices = lights
        if not self._devices:
            return await self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_DEVICE_UUID, default=self._device_uuid or ""): str,
                }),
                errors={"base": "no_devices"},
                description_placeholders={"title": DOMAIN_TITLE},
            )
        return await self.async_step_device()

    async def async_step_device(self, user_input=None):
        """选择要接入的灯设备。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            dev_id = user_input.get(CONF_DEVICE_ID, "")
            device = next((d for d in self._devices if str(d.get("ID", "")) == dev_id), None)
            if device is None:
                errors["base"] = "device_not_found"
            else:
                user_id = self._user_id
                if not user_id:
                    try:
                        info = await self._api.get_user_info()
                        user_id = str(info.get("userId", info.get("uid", "")))
                    except Exception:  # noqa: BLE001
                        pass
                return self.async_create_entry(
                    title=f"家超 {device.get('alias', device.get('name', '智能灯'))}",
                    data={
                        "token": self._token,
                        "username": self._username,
                        "password": self._password,
                        "user_id": user_id,
                        "device_id": dev_id,
                        "device_uuid": self._device_uuid,
                        "_device": device,
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )

        dev_choices = {
            str(d.get("ID", "")): f"{d.get('alias', d.get('name', '?'))} ({d.get('ID', '')})"
            for d in self._devices
        }
        schema = vol.Schema({
            vol.Required(CONF_DEVICE_ID): vol.In(dev_choices),
        })
        return self.async_show_form(
            step_id="device",
            data_schema=schema,
            errors=errors,
            description_placeholders={"title": DOMAIN_TITLE},
        )

    async def async_step_import(self, import_config):
        """支持 yaml 导入（可选）。"""
        return await self.async_step_user(import_config)
