"""家超集成：数据协调器（持有 API + MQTT + 设备信息）。"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .api import JiaChaoAPI
from .mqtt_client import JiaChaoMQTT
from .const import (
    MQTT_USERNAME_ZONE,
    MQTT_DEFAULT_HOST,
    MQTT_DEFAULT_PORT,
    MQTT_DEFAULT_SNI,
)

_LOGGER = logging.getLogger(__name__)


class JiaChaoCoordinator:
    """协调 API 与 MQTT，向 light 实体提供状态。"""

    def __init__(self, hass: HomeAssistant, api: JiaChaoAPI,
                 device: dict, device_info: dict, options: dict):
        self.hass = hass
        self.api = api
        self.device = device
        self.device_info = device_info
        self.options = options
        self.device_id = str(device.get("ID", ""))
        self.device_alias = str(device.get("alias", device.get("name", "家超智能灯")))
        self.device_model = str(device.get("model", device.get("mpid", "")))
        self._state_listener = None

        # MQTT 参数（优先取配置时保存的设备 JSON 里的 mqtt，其次 deviceInfo，兜底默认值）
        mqtt_cfg = device.get("mqtt") or device_info.get("mqtt") or {}
        # host 优先用域名（SNI），避免 IP 直连证书校验失败（真实证书只对域名有效）
        host = mqtt_cfg.get("domain") or MQTT_DEFAULT_SNI
        port = int(mqtt_cfg.get("port") or MQTT_DEFAULT_PORT)
        sni = mqtt_cfg.get("domain") or MQTT_DEFAULT_SNI
        mqtt_token = mqtt_cfg.get("token") or ""
        user_id = options.get("user_id", "")
        username = f"{self.device_id}_{MQTT_USERNAME_ZONE}{user_id}"

        # dc 编号（topic 中 smart/<deviceId>/dc/<dc>/...）：灯=25（与 product_id 一致）
        dc = str(device.get("dc") or device.get("product_id") or device.get("mpid") or "25")
        self.mqtt = JiaChaoMQTT(
            device_id=self.device_id,
            device_id_int=int(device.get("devIdInt", 0)),
            username=username,
            password=mqtt_token,
            host=host,
            port=port,
            sni=sni,
            home_id=int(device.get("homeID", 0)),
            room_id=int(device.get("roomID", 0)),
            dc=dc,
        )

    def set_state_listener(self, cb):
        self._state_listener = cb
        self.mqtt.set_state_callback(cb)

    def connect_mqtt(self) -> None:
        """连接 MQTT（阻塞调用，放执行器线程）。"""
        try:
            self.mqtt.connect()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("jiachao mqtt connect failed: %s", err)
