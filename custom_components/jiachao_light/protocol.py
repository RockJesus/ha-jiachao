"""家超睡眠灯 BLE 协议处理器

支持多种常见 BLE 灯协议，并允许自定义命令格式。
命令格式说明：
  {r} {g} {b} - RGB 颜色分量 (0-255)
  {w} - 白光亮度 (0-255)
  {brightness} - 亮度 (0-255)
  {on} - 开关状态 (0/1)
  {effect} - 效果编号 (0-255)
  {speed} - 速度 (0-255)
  {temp} - 色温 (0-255, 映射到 2000-6500K)
  十六进制直接写，如 0x56 或 \x56
"""
from __future__ import annotations

import logging
import struct
from typing import Any

from homeassistant.components.light import ColorMode

from .const import (
    EFFECT_BREATH,
    EFFECT_NIGHT,
    EFFECT_RAINBOW,
    EFFECT_READ,
    EFFECT_RELAX,
    EFFECT_SUNSET,
)

_LOGGER = logging.getLogger(__name__)


def _hex_byte(value: int) -> str:
    """将整数转为两位十六进制字符串，用于命令格式替换。"""
    return f"{value & 0xFF:02x}"


class BLELightProtocol:
    """BLE 灯协议处理器，根据预设或自定义格式构造控制命令。"""

    def __init__(
        self,
        protocol_type: str = "jiachao_default",
        custom_format: str | None = None,
    ) -> None:
        self.protocol_type = protocol_type
        self.custom_format = custom_format

    # ---- 公共接口 ----

    def build_power_command(self, is_on: bool) -> bytes:
        """构造开关命令。"""
        if self.protocol_type == "magic_blue":
            return self._magic_blue_power(is_on)
        if self.protocol_type == "elk_bledom":
            return self._elk_bledom_power(is_on)
        if self.protocol_type == "generic_fff0":
            return self._generic_fff0_power(is_on)
        # jiachao_default 和自定义走通用格式
        return self._generic_power(is_on)

    def build_brightness_command(self, brightness: int) -> bytes:
        """构造亮度命令 (0-255)。"""
        if self.protocol_type == "magic_blue":
            return self._magic_blue_brightness(brightness)
        if self.protocol_type == "elk_bledom":
            return self._elk_bledom_brightness(brightness)
        if self.protocol_type == "generic_fff0":
            return self._generic_fff0_brightness(brightness)
        return self._generic_brightness(brightness)

    def build_rgb_command(self, r: int, g: int, b: int, brightness: int = 255) -> bytes:
        """构造 RGB 颜色命令。"""
        if self.protocol_type == "magic_blue":
            return self._magic_blue_rgb(r, g, b)
        if self.protocol_type == "elk_bledom":
            return self._elk_bledom_rgb(r, g, b)
        if self.protocol_type == "generic_fff0":
            return self._generic_fff0_rgb(r, g, b, brightness)
        return self._generic_rgb(r, g, b, brightness)

    def build_color_temp_command(self, temp: int, brightness: int = 255) -> bytes:
        """构造色温命令。temp 为 mireds 或 0-255 映射值。"""
        if self.protocol_type == "magic_blue":
            return self._magic_white_temp(temp, brightness)
        if self.protocol_type == "elk_bledom":
            return self._elk_bledom_white(temp, brightness)
        if self.protocol_type == "generic_fff0":
            return self._generic_fff0_white(temp, brightness)
        return self._generic_white(temp, brightness)

    def build_effect_command(self, effect_name: str, speed: int = 50) -> bytes:
        """构造效果模式命令。"""
        effect_map = {
            EFFECT_RAINBOW: 0x25,
            EFFECT_BREATH: 0x26,
            EFFECT_SUNSET: 0x27,
            EFFECT_READ: 0x28,
            EFFECT_RELAX: 0x29,
            EFFECT_NIGHT: 0x2a,
        }
        effect_id = effect_map.get(effect_name, 0x25)
        speed_byte = int(speed * 2.55) & 0xFF

        if self.protocol_type == "magic_blue":
            return bytes([0x56, 0x00, 0x00, 0x00, 0x00, effect_id, speed_byte, 0xAA])
        if self.protocol_type == "elk_bledom":
            return bytes([0x7E, 0x07, effect_id, speed_byte, 0x03, 0xFF, 0xFF, 0xEF])
        if self.protocol_type == "generic_fff0":
            return bytes([0xCC, 0x24, effect_id, speed_byte, 0x33])
        # 通用 / 家超默认
        return bytes([0x7E, 0x04, effect_id, speed_byte, 0x01, 0xEF])

    def parse_status_notification(self, data: bytes) -> dict[str, Any] | None:
        """解析设备状态通知（如果设备支持主动上报）。"""
        if not data or len(data) < 4:
            return None
        try:
            # 尝试常见格式解析
            if data[0] == 0x66 and len(data) >= 7:
                # Magic Blue 状态回包
                return {
                    "is_on": data[2] == 0x23,
                    "mode": data[3],
                    "r": data[4],
                    "g": data[5],
                    "b": data[6],
                    "brightness": data[7] if len(data) > 7 else 255,
                }
            if data[0] == 0x7E and len(data) >= 8:
                # ELK / 通用格式
                return {
                    "is_on": data[2] == 0x01,
                    "r": data[4],
                    "g": data[5],
                    "b": data[6],
                    "brightness": data[7] if len(data) > 7 else 255,
                }
        except (IndexError, ValueError):
            pass
        return None

    # ---- 自定义格式解析 ----

    def _apply_custom_format(self, template: str, variables: dict[str, int]) -> bytes:
        """将自定义命令模板中的占位符替换为实际字节值。

        模板格式示例：
          "56 {r} {g} {b} {w} 00 f0 aa"
          "7e 04 {effect} {speed} 01 ef"
        """
        result = bytearray()
        parts = template.strip().split()
        for part in parts:
            part_lower = part.lower().strip("{}")
            if part_lower in variables:
                result.append(variables[part_lower] & 0xFF)
            else:
                # 尝试解析为十六进制
                try:
                    val = int(part, 16)
                    result.append(val & 0xFF)
                except ValueError:
                    _LOGGER.warning("无法解析命令片段: %s", part)
        return bytes(result)

    # ============ Magic Blue 协议 ============

    @staticmethod
    def _magic_blue_power(is_on: bool) -> bytes:
        return bytes([0xCC, 0x23 if is_on else 0x24, 0x33])

    @staticmethod
    def _magic_blue_brightness(brightness: int) -> bytes:
        return bytes([0x56, 0x00, 0x00, 0x00, brightness & 0xFF, 0x0A, 0x0A, 0xAA])

    @staticmethod
    def _magic_blue_rgb(r: int, g: int, b: int) -> bytes:
        return bytes([0x56, r & 0xFF, g & 0xFF, b & 0xFF, 0x00, 0xF0, 0xAA])

    @staticmethod
    def _magic_white_temp(temp: int, brightness: int) -> bytes:
        # temp 映射: 0-255 -> 暖白到冷白
        return bytes([0x56, 0x00, 0x00, 0x00, brightness & 0xFF, 0x0F, 0x0A, 0xAA])

    # ============ ELK BLEDOM 协议 ============

    @staticmethod
    def _elk_bledom_power(is_on: bool) -> bytes:
        return bytes([0x7E, 0x04, 0x01 if is_on else 0x00, 0x00, 0x00, 0xEF])

    @staticmethod
    def _elk_bledom_brightness(brightness: int) -> bytes:
        return bytes([0x7E, 0x04, 0x01, brightness & 0xFF, 0x00, 0xEF])

    @staticmethod
    def _elk_bledom_rgb(r: int, g: int, b: int) -> bytes:
        return bytes([0x7E, 0x07, 0x05, 0x03, r & 0xFF, g & 0xFF, b & 0xFF, 0xEF])

    @staticmethod
    def _elk_bledom_white(temp: int, brightness: int) -> bytes:
        return bytes([0x7E, 0x05, 0x02, brightness & 0xFF, temp & 0xFF, 0xEF])

    # ============ 通用 FFF0 协议 ============

    @staticmethod
    def _generic_fff0_power(is_on: bool) -> bytes:
        return bytes([0xCC, 0x23 if is_on else 0x24, 0x33])

    @staticmethod
    def _generic_fff0_brightness(brightness: int) -> bytes:
        return bytes([0x56, 0x00, 0x00, 0x00, brightness & 0xFF, 0x0A, 0x0A, 0xAA])

    @staticmethod
    def _generic_fff0_rgb(r: int, g: int, b: int, brightness: int) -> bytes:
        return bytes([0x56, r & 0xFF, g & 0xFF, b & 0xFF, 0x00, 0xF0, 0xAA])

    @staticmethod
    def _generic_fff0_white(temp: int, brightness: int) -> bytes:
        return bytes([0x56, 0x00, 0x00, 0x00, brightness & 0xFF, 0x0F, 0x0A, 0xAA])

    # ============ 通用 / 家超默认协议 ============

    @staticmethod
    def _generic_power(is_on: bool) -> bytes:
        return bytes([0x7E, 0x04, 0x01 if is_on else 0x00, 0x00, 0x00, 0xEF])

    @staticmethod
    def _generic_brightness(brightness: int) -> bytes:
        return bytes([0x7E, 0x04, 0x01, brightness & 0xFF, 0x00, 0xEF])

    @staticmethod
    def _generic_rgb(r: int, g: int, b: int, brightness: int) -> bytes:
        return bytes([0x7E, 0x07, 0x05, 0x03, r & 0xFF, g & 0xFF, b & 0xFF, 0xEF])

    @staticmethod
    def _generic_white(temp: int, brightness: int) -> bytes:
        return bytes([0x7E, 0x05, 0x02, brightness & 0xFF, temp & 0xFF, 0xEF])
