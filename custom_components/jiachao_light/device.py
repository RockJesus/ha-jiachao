"""家超睡眠灯 BLE 设备连接管理器"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from bleak import BleakClient, BleakError

from .const import RETRY_DELAY
from .protocol import BLELightProtocol

_LOGGER = logging.getLogger(__name__)


class BLELightDevice:
    """管理单个 BLE 灯设备的连接和通信。"""

    def __init__(
        self,
        address: str,
        service_uuid: str,
        write_uuid: str,
        notify_uuid: str | None,
        protocol: BLELightProtocol,
        name: str = "家超睡眠灯",
    ) -> None:
        self.address = address
        self.service_uuid = service_uuid
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid
        self.protocol = protocol
        self.name = name

        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._connecting = False
        self._disconnect_listener: Callable[[str], None] | None = None

        # 设备状态缓存
        self._is_on = False
        self._brightness = 255
        self._rgb_color: tuple[int, int, int] = (255, 255, 255)
        self._color_temp: int | None = None
        self._effect: str | None = None
        self._color_mode: str = "rgb"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._rgb_color

    @property
    def color_temp(self) -> int | None:
        return self._color_temp

    @property
    def effect(self) -> str | None:
        return self._effect

    @property
    def color_mode(self) -> str:
        return self._color_mode

    def set_disconnect_listener(self, listener: Callable[[str], None]) -> None:
        """设置断开连接回调。"""
        self._disconnect_listener = listener

    async def connect(self) -> bool:
        """连接到 BLE 设备。"""
        if self._connected:
            return True
        if self._connecting:
            # 等待正在进行的连接
            for _ in range(20):
                if self._connected:
                    return True
                await asyncio.sleep(0.5)
            return self._connected

        self._connecting = True
        try:
            self._client = BleakClient(
                self.address,
                disconnected_callback=self._on_disconnected,
            )
            await self._client.connect()
            self._connected = self._client.is_connected
            if self._connected:
                _LOGGER.info("已连接到 %s (%s)", self.name, self.address)
                # 订阅通知
                if self.notify_uuid:
                    try:
                        await self._client.start_notify(
                            self.notify_uuid, self._on_notification
                        )
                    except (BleakError, Exception) as err:  # noqa: BLE001
                        _LOGGER.debug("无法订阅通知: %s", err)
            return self._connected
        except (BleakError, asyncio.TimeoutError, OSError) as err:
            _LOGGER.warning("连接 %s 失败: %s", self.address, err)
            self._connected = False
            return False
        finally:
            self._connecting = False

    async def disconnect(self) -> None:
        """断开连接。"""
        if self._client and self._connected:
            try:
                if self.notify_uuid:
                    await self._client.stop_notify(self.notify_uuid)
            except Exception:  # noqa: BLE001
                pass
            try:
                await self._client.disconnect()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("断开连接出错: %s", err)
        self._connected = False

    async def _ensure_connected(self) -> bool:
        """确保设备已连接，未连接则尝试重连。"""
        if self._connected and self._client and self._client.is_connected:
            return True
        return await self.connect()

    async def _write_command(self, data: bytes) -> bool:
        """向设备写入命令。"""
        async with self._lock:
            if not await self._ensure_connected():
                return False
            try:
                await self._client.write_gatt_char(self.write_uuid, data, response=False)
                return True
            except (BleakError, asyncio.TimeoutError, OSError, AttributeError) as err:
                _LOGGER.warning("写入命令失败: %s", err)
                self._connected = False
                return False

    def _on_disconnected(self, client: BleakClient) -> None:
        """蓝牙断开回调。"""
        _LOGGER.info("设备 %s 已断开连接", self.address)
        self._connected = False
        if self._disconnect_listener:
            try:
                self._disconnect_listener(self.address)
            except Exception:  # noqa: BLE001
                pass

    def _on_notification(self, sender: int, data: bytearray) -> None:
        """处理设备状态通知。"""
        status = self.protocol.parse_status_notification(bytes(data))
        if status:
            if "is_on" in status:
                self._is_on = status["is_on"]
            if "brightness" in status:
                self._brightness = status["brightness"]
            if "r" in status and "g" in status and "b" in status:
                self._rgb_color = (status["r"], status["g"], status["b"])

    # ---- 控制接口 ----

    async def turn_on(self) -> bool:
        """开灯。"""
        cmd = self.protocol.build_power_command(True)
        if await self._write_command(cmd):
            self._is_on = True
            return True
        return False

    async def turn_off(self) -> bool:
        """关灯。"""
        cmd = self.protocol.build_power_command(False)
        if await self._write_command(cmd):
            self._is_on = False
            return True
        return False

    async def set_brightness(self, brightness: int) -> bool:
        """设置亮度 (0-255)。"""
        brightness = max(0, min(255, brightness))
        cmd = self.protocol.build_brightness_command(brightness)
        if await self._write_command(cmd):
            self._brightness = brightness
            if brightness > 0:
                self._is_on = True
            return True
        return False

    async def set_rgb_color(self, r: int, g: int, b: int, brightness: int | None = None) -> bool:
        """设置 RGB 颜色。"""
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        bri = brightness if brightness is not None else self._brightness
        cmd = self.protocol.build_rgb_command(r, g, b, bri)
        if await self._write_command(cmd):
            self._rgb_color = (r, g, b)
            self._color_mode = "rgb"
            self._color_temp = None
            self._effect = None
            self._is_on = True
            return True
        return False

    async def set_color_temp(self, temp: int, brightness: int | None = None) -> bool:
        """设置色温。temp 为 0-255 映射值或 mireds。"""
        bri = brightness if brightness is not None else self._brightness
        # 将 mireds 映射到 0-255 (假设范围 153-500 mireds)
        if temp > 255:
            temp_mapped = int((temp - 153) / (500 - 153) * 255)
            temp_mapped = max(0, min(255, temp_mapped))
        else:
            temp_mapped = temp
        cmd = self.protocol.build_color_temp_command(temp_mapped, bri)
        if await self._write_command(cmd):
            self._color_temp = temp
            self._color_mode = "color_temp"
            self._effect = None
            self._is_on = True
            return True
        return False

    async def set_effect(self, effect_name: str, speed: int = 50) -> bool:
        """设置效果模式。"""
        cmd = self.protocol.build_effect_command(effect_name, speed)
        if await self._write_command(cmd):
            self._effect = effect_name
            self._is_on = True
            return True
        return False

    async def update_status(self) -> bool:
        """尝试读取设备状态（如果设备支持读取特征）。"""
        # 大多数 BLE 灯不支持主动读取，这里仅返回缓存状态
        # 如果设备有 notify，会在 _on_notification 中更新
        return True
