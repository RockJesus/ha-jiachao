"""家超 MQTT 客户端（TLS 直连家超云端 broker，真实协议实测版 2026-09-24）。

实测协议（2026-09-24 用真实凭据连 broker 验证）：
  - broker: dc02-lvs.iotdreamcatcher.net.cn:8883（TLS, SNI=域名）
  - 凭据: username=<deviceId>_<zone><userId>, password=设备级 mqtt token
  - clientId: and_<deviceId>_<随机后缀>
  - 命令 topic: smart/<deviceId>/dc/25/din/config
  - 状态 topic: smart/<deviceId>/dc/25/dout/#  (status/online/info)
  - payload: {"m":{"req":{...}}} 命令；{"m":{"res":{...}}} 状态
  - 开关: value_set mo=224(开)/225(关)；亮度/颜色: value_set mo=129 lc/wv/wh
"""
from __future__ import annotations

import json
import logging
import random
import ssl
import threading

import paho.mqtt.client as mqtt

from .const import (
    MQTT_CLIENT_ID_PREFIX,
    MQTT_DEFAULT_HOST,
    MQTT_DEFAULT_PORT,
    MQTT_DEFAULT_SNI,
    MQTT_USERNAME_ZONE,
    light_topics,
    CMD_OPEN_MODE,
    CMD_CLOSE_MODE,
    CMD_NORMAL_MODE,
    CMD_WH_WHITE,
    BRIGHTNESS_MAX,
    WV_MAX,
    COLOR_TEMP_MIN_K,
    COLOR_TEMP_MAX_K,
    DEFAULT_WV,
)

_LOGGER = logging.getLogger(__name__)


class JiaChaoMQTT:
    """管理一个设备的 MQTT 连接。"""

    def __init__(
        self,
        device_id: str,
        device_id_int: int,
        username: str,
        password: str,
        host: str = MQTT_DEFAULT_HOST,
        port: int = MQTT_DEFAULT_PORT,
        sni: str = MQTT_DEFAULT_SNI,
        home_id: int = 0,
        room_id: int = 0,
        dc: str = "25",
    ):
        self.device_id = device_id
        self.device_id_int = device_id_int
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.sni = sni
        self.home_id = home_id
        self.room_id = room_id
        self.dc = dc or "25"
        self._cmd_topic, self._state_prefix = light_topics(device_id, self.dc)
        self.client: mqtt.Client | None = None
        self._connected = threading.Event()
        self._state_callback = None  # callable(topic, payload)
        self._last_message: dict | None = None
        # 当前色温（wv 0-1000，0=暖 1000=冷），初始自然白
        self._last_wv = DEFAULT_WV
        # 当前亮度（lc 0-255）：改色温时保持亮度不变
        self._last_lc = BRIGHTNESS_MAX

    def set_state_callback(self, cb):
        self._state_callback = cb

    # -- 连接 ----------------------------------------------------------------
    def connect(self) -> None:
        """建立 MQTT 连接并订阅状态 topics（阻塞，在 HA 执行器线程调用）。"""
        if self.client and self.client.is_connected():
            return
        cid = f"{MQTT_CLIENT_ID_PREFIX}{self.device_id}_{random.randint(100000, 999999)}"
        # paho-mqtt 2.x 必须传 callback_api_version；1.x 不支持该参数 → 兼容写法
        try:
            client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=cid,
                protocol=mqtt.MQTTv311,
                transport="tcp",
            )
        except (AttributeError, TypeError):
            client = mqtt.Client(
                client_id=cid,
                protocol=mqtt.MQTTv311,
                transport="tcp",
            )
        ctx = ssl.create_default_context()
        client.tls_set_context(ctx)
        client.tls_insecure_set(False)
        client.username_pw_set(self.username, self.password)
        # host 传域名（SNI），真实 broker 证书只对域名有效；IP 直连会证书校验失败
        host = self.sni or self.host

        def on_connect(cl, userdata, flags, rc, *args):
            # paho 1.x: rc 是 int；paho 2.x VERSION2: rc 是 ReasonCode 对象
            try:
                rc_val = rc.value if hasattr(rc, "value") else rc
            except AttributeError:
                rc_val = rc
            if rc_val == 0:
                _LOGGER.debug("jiachao mqtt connected")
                self._connected.set()
                cl.subscribe(self._state_prefix, qos=0)
                _LOGGER.debug("subscribed %s", self._state_prefix)
            else:
                _LOGGER.warning("jiachao mqtt connect rc=%s", mqtt.connack_string(rc_val) if isinstance(rc_val, int) else rc_val)

        def on_message(cl, userdata, msg):
            _LOGGER.debug("jiachao mqtt msg %s = %s", msg.topic, msg.payload[:500])
            self._last_message = {"topic": msg.topic, "payload": msg.payload.decode("utf-8", "replace")}
            if self._state_callback:
                try:
                    self._state_callback(self._last_message)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("state callback error: %s", err)

        client.on_connect = on_connect
        client.on_message = on_message
        client.reconnect_delay_set(min_delay=5, max_delay=60)
        try:
            client.connect(host, self.port, keepalive=60)
        except Exception as err:
            raise ConnectionError(f"MQTT 连接失败 {host}:{self.port}: {err}") from err
        client.loop_start()
        self.client = client
        # 等待连接（最长 15 秒）
        if not self._connected.wait(timeout=15):
            raise ConnectionError("MQTT 连接超时")

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None

    # -- 控制（真实协议，实测 2026-09-24） -------------------------------------
    def _publish(self, payload: dict) -> None:
        if not self.client or not self.client.is_connected():
            return
        data = json.dumps({"m": {"req": payload}}, separators=(",", ":"))
        _LOGGER.debug("jiachao publish %s = %s", self._cmd_topic, data)
        self.client.publish(self._cmd_topic, data, qos=0)

    def _req(self, action: str, **fields) -> dict:
        req = {"a": action, "rand": random.randint(100000, 999999)}
        req.update(fields)
        return req

    def turn_on(self) -> int:
        """开灯（value_set mo=224）。"""
        self._publish(self._req("value_set", mo=CMD_OPEN_MODE))
        return 1

    def turn_off(self) -> int:
        """关灯（value_set mo=225）。"""
        self._publish(self._req("value_set", mo=CMD_CLOSE_MODE))
        return 1

    def set_brightness(self, brightness_0_255: int) -> int:
        """调亮度（value_set mo=129 lc=<0-255>，保持当前色温 wv）。"""
        b = max(0, min(BRIGHTNESS_MAX, int(brightness_0_255)))
        self._last_lc = b
        self._publish(self._req(
            "value_set", mo=CMD_NORMAL_MODE,
            lc=b, wv=self._last_wv, wh=CMD_WH_WHITE,
        ))
        return 1

    def set_last_brightness(self, brightness_0_255: int) -> None:
        """状态同步：记录设备实际亮度（供改色温时保持）。"""
        self._last_lc = max(0, min(BRIGHTNESS_MAX, int(brightness_0_255)))

    def set_color_temp(self, kelvin: int) -> int:
        """调色温（暖→冷渐变）：kelvin 2700-6500 → wv 0-1000。

        用户实机确认：本灯为双色温灯，wv 是色温编码，非 RGB 彩色。
        亮度保持当前值（_last_lc），避免调色温时亮度跳变。
        """
        k = max(COLOR_TEMP_MIN_K, min(COLOR_TEMP_MAX_K, int(kelvin)))
        wv = int(round((k - COLOR_TEMP_MIN_K) / (COLOR_TEMP_MAX_K - COLOR_TEMP_MIN_K) * WV_MAX))
        wv = max(0, min(WV_MAX, wv))
        self._last_wv = wv
        self._publish(self._req(
            "value_set", mo=CMD_NORMAL_MODE,
            lc=self._last_lc, wv=wv, wh=CMD_WH_WHITE,
        ))
        return 1
