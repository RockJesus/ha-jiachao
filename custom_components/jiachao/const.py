"""家超智能灯 (JiaChao) 集成常量定义。

家超 = 福建创高智联技术股份有限公司旗下的智能照明生态（App 包名 com.dc.jiachao）。
设备芯片为 Winnermicro W800（WiFi + BLE 双模），dtype=LT（灯），product_id=25。

本集成基于对家超 App v2.2.2 的真实抓包逆向结果开发：
  - API 域: dc02.iotdreamcatcher.net.cn:12443（/v2/ 前缀，token 认证）
  - MQTT:  TLS 8883，每设备独立 username/password（由 deviceInfo 下发）
  - 控制协议:  DML 命令（cmdType/cmd/parms），topic 按设备 ID 授权
"""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "jiachao"
DOMAIN_TITLE = "家超智能灯"

# 配置项
CONF_USERNAME = "username"          # 家超 App 登录手机号
CONF_PASSWORD = "password"          # 家超 App 登录密码
CONF_DEVICE_ID = "device_id"        # 选择的设备 ID（00002500... 20 位数字串）
CONF_SMS_CODE = "sms_code"          # 短信验证码（二次验证时输入）
CONF_SCAN_INTERVAL = "scan_interval"

# 内部默认使用的设备 UUID（家超 App 正在使用的受信任设备标识）。
# 使用受信任 UUID 密码登录可免短信二次验证（实测 code=479 不会触发），
# 且 HA 与 App 多 token 并存互不踢线（实测）。
DEFAULT_TRUST_UUID = "12e178fb-972a-4df1-bee6-805b46a8fbc9"

PLATFORMS: list[Platform] = [Platform.LIGHT]

# ---------------------------------------------------------------------------
# 云端 API（真实抓包结果，2026-09-24 验证）
# ---------------------------------------------------------------------------
API_BASE_URL = "https://dc02.iotdreamcatcher.net.cn:12443"
API_ALT_URLS = [
    "https://dc03.iotdreamcatcher.net:12448",
    "https://query.iotdreamcatcher.net.cn:12082",
]
API_PATH_LOGIN = "/v2/user/login"
API_PATH_LOGIN_CODE = "/v2/user/login/code"
API_PATH_CODE_LOGIN = "/v2/user/code/login"
API_PATH_INFO = "/v2/user/info"
API_PATH_HOMES = "/v2/group/homes"
API_PATH_ROOMS = "/v2/group/home/rooms"
API_PATH_DEVICES = "/v2/user/device/list"
API_PATH_DEVICE_INFO = "/v2/user/device/deviceInfo"
API_PATH_APP_DATA = "/v2/user/app/data"
API_PATH_ZONE = "/v2/server/zone"
API_PATH_LIGHT_MODES = "/v2/product/light/modes"

# 家超 API 请求头
API_HEADERS = {
    "brand": "jiachao",
    "appver": "2.2.2",
    "lang": "zh",
    "tz": "Asia/Shanghai",
    "user-agent": "Dart/3.4 (dart:io)",
    "content-type": "application/json",
}

# ---------------------------------------------------------------------------
# MQTT（deviceInfo 下发的服务器参数）
# ---------------------------------------------------------------------------
MQTT_PORT = 8883  # TLS
# clientId 格式（App 实测）: and_<deviceId>_<随机后缀>
MQTT_CLIENT_ID_PREFIX = "and_"
# username 格式（App 实测）: <deviceId>_<zone><userId>
MQTT_USERNAME_ZONE = "CN"

# 默认 MQTT 服务器（deviceInfo 会返回实际地址，此为兜底）
MQTT_DEFAULT_HOST = "47.96.228.34"
MQTT_DEFAULT_SNI = "dc02-lvs.iotdreamcatcher.net.cn"
MQTT_DEFAULT_PORT = 8883

# ---------------------------------------------------------------------------
# MQTT Topics（2026-09-24 实测锁定：smart/<deviceId>/dc/<dc>/dout|din/<动作>）
# ---------------------------------------------------------------------------
# 真实协议（实测验证）：
#   命令（App -> 设备）: smart/<deviceId>/dc/25/din/config
#   状态（设备 -> 端）:  smart/<deviceId>/dc/25/dout/status | online | info
#   payload: {"m":{"req":{...}}} 命令 / {"m":{"res":{...}}} 状态
#   dc 编号 = 产品类别（灯 LT 为 25，与 product_id 一致）
def light_topics(device_id: str, dc: str = "25") -> tuple[str, str]:
    """返回 (命令 topic, 状态订阅前缀)。"""
    return (
        f"smart/{device_id}/dc/{dc}/din/config",
        f"smart/{device_id}/dc/{dc}/dout/#",
    )


# DML 命令（实测验证 + 用户实机确认）
# 开关: value_set mo=225(开) / 224(关)   —— 用户实机确认：点开灯灭=224 是关，225 是开
# 亮度/色温: value_set mo=129 lc=<0-255> wv=<色温0-1000> wh=500（129=亮灯调节模式）
# wv 为色温编码（用户实机确认：只做暖色到冷色渐变，非 RGB 彩色）：
#   wv=0 → 最暖（2700K）；wv=1000 → 最冷（6500K）
CMD_OPEN_MODE = 225      # 开（用户实机确认）
CMD_CLOSE_MODE = 224     # 关（用户实机确认）
CMD_NORMAL_MODE = 129    # 亮度/色温调节模式（灯亮，状态回执 129=亮）
CMD_WH_WHITE = 500       # 白光分量（App 实测固定 500）
BRIGHTNESS_MAX = 255     # lc 亮度范围 0-255（实测 60/116/230）
WV_MAX = 1000            # wv 色温编码范围 0-1000（0=暖 1000=冷）


# ---------------------------------------------------------------------------
# 设备状态字段（App JSON -> HA 实体）
# ---------------------------------------------------------------------------
ATTR_POWER = "power"
ATTR_BRIGHTNESS = "brightness"
ATTR_COLOR_TEMP = "color_temp"
ATTR_RGB = "rgb"
ATTR_ONLINE = "online"
ATTR_MODEL = "model"
ATTR_DEVICE_NAME = "alias"
ATTR_DEVICE_ID = "ID"

# 亮度归一化：家超 App 0-100
BRIGHTNESS_SCALE = 100
# 色温范围（开尔文）—— wv 0-1000 线性映射 2700K-6500K
COLOR_TEMP_MIN_K = 2700
COLOR_TEMP_MAX_K = 6500
# 初始默认色温（wv=500 → 4600K 自然白）
DEFAULT_WV = 500

# 默认轮询间隔（秒）——MQTT 状态为主，轮询为兜底
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

# 产品场景模式（/v2/product/light/modes 实测，pid=25 部分）
# 9000 冥想 / 9001 办公 / 9002 夜灯 / 9003 娱乐 / 9004 阅读 / 9005 休闲 /
# 9006 温馨 / 9105 森林 / 9107 浪漫 / 9108 柔和色彩 ...
SCENE_MODES: dict[int, str] = {
    9000: "冥想模式", 9001: "办公模式", 9002: "夜灯模式", 9003: "娱乐模式",
    9004: "阅读模式", 9005: "休闲模式", 9006: "温馨模式",
    9105: "森林", 9107: "浪漫", 9108: "柔和色彩",
}
