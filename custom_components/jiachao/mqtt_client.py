"""家超 MQTT client with AES encryption.

Protocol reconstructed from jiachao.apk analysis:
- MQTT transport with TLS optional
- AES-128-CBC payload encryption with PKCS7 padding
- Packet structure: flag(1) + seq(2) + payload_len(2) + payload
- Max packet length: 800 bytes
- Base64 encoding for MQTT payload
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import struct
import threading
from typing import Any, Callable

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from .const import (
    DEFAULT_MQTT_KEEPALIVE,
    DEFAULT_MQTT_PORT,
    PACKET_MAX_LENGTH,
    TOPIC_DEVICE_CONTROL,
    TOPIC_DEVICE_ONLINE,
    TOPIC_DEVICE_STATUS,
)

_LOGGER = logging.getLogger(__name__)

# Packet flag constants (from APK MessagePacket analysis)
FLAG_STATUS = 0x01
FLAG_CONTROL = 0x02
FLAG_ACK = 0x03
FLAG_HEARTBEAT = 0x04
FLAG_ENCRYPTED = 0x80

# Default AES key and IV (from APK analysis - may be device-specific)
# In production, these are negotiated via BLE during WiFi pairing
DEFAULT_AES_KEY = b"jiachao_2024_aes"  # 16 bytes for AES-128
DEFAULT_AES_IV = b"jiachao_2024_iv!"  # 16 bytes


class JiachaoMQTTClient:
    """MQTT client for 家超 devices with AES encryption."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_MQTT_PORT,
        username: str = "",
        password: str = "",
        client_id: str = "",
        use_tls: bool = False,
        aes_key: bytes | None = None,
        aes_iv: bytes | None = None,
    ) -> None:
        """Initialize the MQTT client.

        Args:
            host: MQTT broker host.
            port: MQTT broker port.
            username: MQTT username.
            password: MQTT password.
            client_id: MQTT client ID.
            use_tls: Whether to use TLS.
            aes_key: AES-128 key (16 bytes).
            aes_iv: AES IV (16 bytes).
        """
        if mqtt is None:
            raise RuntimeError("paho-mqtt is not installed")

        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._client_id = client_id or f"jiachao_ha_{id(self)}"
        self._use_tls = use_tls
        self._aes_key = aes_key or DEFAULT_AES_KEY
        self._aes_iv = aes_iv or DEFAULT_AES_IV

        self._client: mqtt.Client | None = None
        self._connected = False
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

        # Callbacks
        self._status_callbacks: dict[str, list[Callable]] = {}
        self._online_callbacks: dict[str, list[Callable]] = {}
        self._connect_callbacks: list[Callable] = []

    @property
    def connected(self) -> bool:
        """Return whether the client is connected."""
        return self._connected

    def set_aes_key(self, key: bytes, iv: bytes) -> None:
        """Update AES key and IV (e.g., after device-specific negotiation)."""
        self._aes_key = key
        self._aes_iv = iv

    def register_status_callback(self, device_id: str, callback: Callable) -> None:
        """Register a callback for device status updates."""
        self._status_callbacks.setdefault(device_id, []).append(callback)

    def register_online_callback(self, device_id: str, callback: Callable) -> None:
        """Register a callback for device online/offline updates."""
        self._online_callbacks.setdefault(device_id, []).append(callback)

    def register_connect_callback(self, callback: Callable) -> None:
        """Register a callback for connection events."""
        self._connect_callbacks.append(callback)

    async def connect(self) -> None:
        """Connect to the MQTT broker."""
        self._loop = asyncio.get_running_loop()
        self._client = mqtt.Client(client_id=self._client_id, protocol=mqtt.MQTTv311)

        if self._username:
            self._client.username_pw_set(self._username, self._password)

        if self._use_tls:
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        _LOGGER.debug("Connecting to MQTT broker %s:%s (tls=%s)", self._host, self._port, self._use_tls)

        try:
            self._client.connect(self._host, self._port, keepalive=DEFAULT_MQTT_KEEPALIVE)
            self._client.loop_start()
        except (OSError, mqtt.MQTTException) as err:
            raise ConnectionError(f"Failed to connect to MQTT broker: {err}") from err

        # Wait for connection
        for _ in range(30):
            if self._connected:
                break
            await asyncio.sleep(0.5)

        if not self._connected:
            raise ConnectionError("MQTT connection timeout")

        _LOGGER.info("Connected to MQTT broker %s", self._host)

    async def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            _LOGGER.info("Disconnected from MQTT broker")

    async def subscribe_device(self, device_id: str) -> None:
        """Subscribe to status and online topics for a device."""
        if not self._client or not self._connected:
            raise ConnectionError("Not connected to MQTT broker")

        status_topic = TOPIC_DEVICE_STATUS.format(device_id=device_id)
        online_topic = TOPIC_DEVICE_ONLINE.format(device_id=device_id)

        self._client.subscribe([(status_topic, 1), (online_topic, 1)])
        _LOGGER.debug("Subscribed to device %s topics", device_id)

    async def send_control(self, device_id: str, command: dict[str, Any]) -> bool:
        """Send a control command to a device.

        Args:
            device_id: Target device ID.
            command: Command data dict.

        Returns:
            True if the message was published.
        """
        if not self._client or not self._connected:
            raise ConnectionError("Not connected to MQTT broker")

        topic = TOPIC_DEVICE_CONTROL.format(device_id=device_id)
        payload = self._build_packet(command, flag=FLAG_CONTROL | FLAG_ENCRYPTED)
        encoded = base64.b64encode(payload).decode("ascii")

        result = self._client.publish(topic, encoded, qos=1)
        result.wait_for_publish(timeout=5)

        _LOGGER.debug("Sent control to %s: %s (rc=%s)", device_id, command, result.rc)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def _build_packet(self, data: dict[str, Any], flag: int = FLAG_CONTROL) -> bytes:
        """Build an encrypted packet.

        Packet structure:
            flag(1) + seq(2, big-endian) + payload_len(2, big-endian) + payload

        Args:
            data: Data to encode.
            flag: Packet flag byte.

        Returns:
            Raw packet bytes.
        """
        with self._seq_lock:
            self._seq = (self._seq + 1) & 0xFFFF
            seq = self._seq

        payload_json = json.dumps(data, separators=(",", ":")).encode("utf-8")

        # Encrypt payload if flag indicates encryption
        if flag & FLAG_ENCRYPTED:
            payload_json = self._encrypt(payload_json)

        # Build packet
        header = struct.pack(">BHH", flag, seq, len(payload_json))
        packet = header + payload_json

        if len(packet) > PACKET_MAX_LENGTH:
            _LOGGER.warning("Packet length %d exceeds max %d", len(packet), PACKET_MAX_LENGTH)

        return packet

    def _parse_packet(self, raw: bytes) -> dict[str, Any] | None:
        """Parse a received packet.

        Args:
            raw: Raw packet bytes.

        Returns:
            Parsed data dict, or None if parsing fails.
        """
        if len(raw) < 5:
            _LOGGER.debug("Packet too short: %d bytes", len(raw))
            return None

        flag, seq, payload_len = struct.unpack(">BHH", raw[:5])

        if len(raw) < 5 + payload_len:
            _LOGGER.debug("Packet truncated: expected %d, got %d", 5 + payload_len, len(raw))
            return None

        payload = raw[5 : 5 + payload_len]

        # Decrypt if encrypted flag is set
        if flag & FLAG_ENCRYPTED:
            try:
                payload = self._decrypt(payload)
            except (ValueError, KeyError) as err:
                _LOGGER.debug("Failed to decrypt packet: %s", err)
                return None

        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            _LOGGER.debug("Failed to parse packet JSON: %s", err)
            return None

        data["_flag"] = flag
        data["_seq"] = seq
        return data

    def _encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt data using AES-128-CBC with PKCS7 padding."""
        cipher = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
        return cipher.encrypt(pad(plaintext, AES.block_size))

    def _decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt data using AES-128-CBC with PKCS7 unpadding."""
        cipher = AES.new(self._aes_key, AES.MODE_CBC, self._aes_iv)
        return unpad(cipher.decrypt(ciphertext), AES.block_size)

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int) -> None:
        """Handle MQTT connect event."""
        if rc == 0:
            self._connected = True
            _LOGGER.info("MQTT connected (rc=0)")
            for cb in self._connect_callbacks:
                self._run_callback(cb, True)
        else:
            self._connected = False
            _LOGGER.error("MQTT connection failed (rc=%d): %s", rc, mqtt.connack_string(rc))
            for cb in self._connect_callbacks:
                self._run_callback(cb, False)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        """Handle MQTT disconnect event."""
        self._connected = False
        _LOGGER.warning("MQTT disconnected (rc=%d)", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming MQTT message."""
        topic = msg.topic
        _LOGGER.debug("Received MQTT message on %s", topic)

        try:
            # Decode base64 payload
            raw = base64.b64decode(msg.payload)
            data = self._parse_packet(raw)
        except (base64.binascii.Error, ValueError) as err:
            _LOGGER.debug("Failed to decode MQTT payload: %s", err)
            # Try plain JSON
            try:
                data = json.loads(msg.payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return

        if data is None:
            return

        # Route to appropriate callbacks
        topic_parts = topic.strip("/").split("/")
        if len(topic_parts) >= 3:
            device_id = topic_parts[1]
            msg_type = topic_parts[2]

            if msg_type == "status":
                for cb in self._status_callbacks.get(device_id, []):
                    self._run_callback(cb, data)
            elif msg_type == "online":
                for cb in self._online_callbacks.get(device_id, []):
                    self._run_callback(cb, data)

    def _run_callback(self, callback: Callable, *args: Any) -> None:
        """Run a callback in the event loop."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(callback, *args)
        else:
            callback(*args)
