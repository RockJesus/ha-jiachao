"""Constants for the 家超睡眠灯 integration."""
from __future__ import annotations

DOMAIN = "jiachao"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_CODE = "code"

# API endpoints (base URLs defined in api.py)
API_LOGIN = "/v2/user/login"
API_SEND_LOGIN_CODE = "/v2/user/login/code"
API_CODE_LOGIN = "/v2/user/code/login"
API_DEVICE_LIST = "/v2/user/device/list"
API_DEVICE_INFO = "/v2/user/device/info"
API_USER_CONFIG = "/v2/user/config"
API_DEVICE_EXEC = "/v2/smart/device/exec"

# MQTT defaults
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_KEEPALIVE = 60

# Device types
DEVICE_TYPE_LT800 = "lt800"
DEVICE_TYPE_LT800P = "lt800p"
DEVICE_TYPE_LS301 = "ls301"
DEVICE_TYPE_LT955 = "lt955"

LIGHT_DEVICE_TYPES = [DEVICE_TYPE_LT800, DEVICE_TYPE_LT800P, DEVICE_TYPE_LS301, DEVICE_TYPE_LT955]

# Packet constants
PACKET_MAX_LENGTH = 800
PACKET_HEADER_FLAG = 0xAA
PACKET_HEADER_LEN = 4  # flag(1) + seq(2) + len(1) or similar

# MQTT topic patterns (reconstructed from APK analysis)
TOPIC_DEVICE_STATUS = "jc/{device_id}/status"
TOPIC_DEVICE_CONTROL = "jc/{device_id}/control"
TOPIC_DEVICE_ONLINE = "jc/{device_id}/online"
TOPIC_APP_PREFIX = "jc/app/"

# Light features
SUPPORT_BRIGHTNESS = 1
SUPPORT_COLOR_TEMP = 2
SUPPORT_RGB_COLOR = 4
SUPPORT_EFFECT = 8
SUPPORT_WHITE_NOISE = 16
SUPPORT_VOLUME = 32

# Scene/effect names
EFFECT_READING = "reading"
EFFECT_RELAX = "relax"
EFFECT_SLEEP = "sleep"
EFFECT_NIGHT = "night"
EFFECT_FOCUS = "focus"
EFFECT_WARM = "warm"
EFFECT_COOL = "cool"
EFFECT_ROMANTIC = "romantic"
EFFECT_PARTY = "party"

# Data keys
DATA_POWER = "power"
DATA_BRIGHTNESS = "brightness"
DATA_COLOR_TEMP = "colorTemp"
DATA_COLOR = "color"
DATA_SCENE = "scene"
DATA_VOLUME = "volume"
DATA_WHITE_NOISE = "whiteNoise"
DATA_ONLINE = "online"
DATA_DEVICE_ID = "deviceId"
DATA_DEVICE_NAME = "deviceName"
DATA_DEVICE_TYPE = "deviceType"
DATA_MODEL = "model"
DATA_FW_VERSION = "fwVersion"
DATA_HW_VERSION = "hwVersion"
