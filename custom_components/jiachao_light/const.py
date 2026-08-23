"""家超睡眠灯 BLE 集成 - 常量定义"""
from homeassistant.components.light import (
    ColorMode,
    LightEntityFeature,
)

DOMAIN = "jiachao_light"

# 设备默认名称前缀
DEFAULT_NAME = "家超睡眠灯"

# 重连间隔（秒）
RETRY_DELAY = 5
SCAN_INTERVAL = 30

# 支持的效果模式
EFFECT_RAINBOW = "彩虹渐变"
EFFECT_BREATH = "呼吸"
EFFECT_SUNSET = "日落伴睡"
EFFECT_READ = "阅读"
EFFECT_RELAX = "放松"
EFFECT_NIGHT = "夜灯"

SUPPORTED_EFFECTS = [
    EFFECT_RAINBOW,
    EFFECT_BREATH,
    EFFECT_SUNSET,
    EFFECT_READ,
    EFFECT_RELAX,
    EFFECT_NIGHT,
]

# 颜色模式
SUPPORTED_COLOR_MODES = [
    ColorMode.RGB,
    ColorMode.COLOR_TEMP,
    ColorMode.BRIGHTNESS,
    ColorMode.ONOFF,
]

# 支持的特性
SUPPORTED_FEATURES = LightEntityFeature.EFFECT

# ============ BLE 协议预设 ============
# 每种协议定义: service_uuid, write_uuid, notify_uuid, 命令构造函数标识

PROTOCOL_PRESETS = {
    "jiachao_default": {
        "name": "家超默认（待验证）",
        "service_uuid": "0000fff0-0000-1000-8000-00805f9b34fb",
        "write_uuid": "0000fff1-0000-1000-8000-00805f9b34fb",
        "notify_uuid": "0000fff2-0000-1000-8000-00805f9b34fb",
        "description": "家超睡眠灯默认协议，基于常见白牌 BLE 灯方案。如不工作请使用抓包指南获取真实 UUID。",
    },
    "magic_blue": {
        "name": "Magic Blue / 魔法蓝灯",
        "service_uuid": "0000ffe5-0000-1000-8000-00805f9b34fb",
        "write_uuid": "0000ffe9-0000-1000-8000-00805f9b34fb",
        "notify_uuid": "0000ffe4-0000-1000-8000-00805f9b34fb",
        "description": "Magic Blue 灯泡协议，命令格式 0x56 RR GG BB WW 0x00 0xf0 0xaa",
    },
    "elk_bledom": {
        "name": "ELK BLEDOM 灯带",
        "service_uuid": "00010203-0405-0607-0809-0a0b0c0d1912",
        "write_uuid": "00010203-0405-0607-0809-0a0b0c0d1912",
        "notify_uuid": "00010203-0405-0607-0809-0a0b0c0d1912",
        "description": "ELK BLEDOM 灯带控制器协议",
    },
    "generic_fff0": {
        "name": "通用 FFF0 服务",
        "service_uuid": "0000fff0-0000-1000-8000-00805f9b34fb",
        "write_uuid": "0000fff3-0000-1000-8000-00805f9b34fb",
        "notify_uuid": "0000fff4-0000-1000-8000-00805f9b34fb",
        "description": "最常见的白牌 BLE 灯协议，Service=0xfff0, Write=0xfff3",
    },
    "custom": {
        "name": "自定义协议（手动填写 UUID）",
        "service_uuid": "",
        "write_uuid": "",
        "notify_uuid": "",
        "description": "通过 nRF Connect 抓包获取真实 UUID 后手动填写",
    },
}

# 配置流程中的字段
CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME = "device_name"
CONF_PROTOCOL = "protocol"
CONF_CUSTOM_SERVICE_UUID = "custom_service_uuid"
CONF_CUSTOM_WRITE_UUID = "custom_write_uuid"
CONF_CUSTOM_NOTIFY_UUID = "custom_notify_uuid"
CONF_COMMAND_FORMAT = "command_format"
