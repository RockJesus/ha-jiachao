"""家超 API 客户端（基于抓包逆向的真实接口）。"""
from __future__ import annotations

import hashlib
import logging
import uuid

import aiohttp

from .const import (
    API_ALT_URLS,
    API_BASE_URL,
    API_HEADERS,
    API_PATH_CODE_LOGIN,
    API_PATH_DEVICE_INFO,
    API_PATH_DEVICES,
    API_PATH_HOMES,
    API_PATH_INFO,
    API_PATH_LOGIN,
    API_PATH_LOGIN_CODE,
    API_PATH_ROOMS,
)

_LOGGER = logging.getLogger(__name__)


class JiaChaoError(Exception):
    """家超 API 通用错误。"""


class JiaChaoAuthError(JiaChaoError):
    """登录/认证失败。"""


class JiaChaoCodeRequiredError(JiaChaoAuthError):
    """服务器要求短信二次验证（code=479 需要二次验证）。"""


class JiaChaoAPI:
    """封装家超云端 HTTP API。"""

    def __init__(self, session: aiohttp.ClientSession, token: str | None = None):
        self._session = session
        self._token = token
        self._base = API_BASE_URL

    @property
    def token(self) -> str | None:
        return self._token

    async def _request(self, method: str, path: str, params: dict | None = None,
                       json: dict | None = None, _retry: bool = True) -> dict:
        headers = dict(API_HEADERS)
        if self._token:
            headers["token"] = self._token
        url = self._base + path
        try:
            async with self._session.request(method, url, params=params, json=json,
                                             headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 401:
                    raise JiaChaoAuthError("token 无效或已过期")
                text = await resp.text()
                data = await resp.json(content_type=None)
        except JiaChaoAuthError:
            raise
        except (aiohttp.ClientError, ValueError) as err:
            # 主域名失败时尝试备用域名
            if _retry and self._base == API_BASE_URL:
                for alt in API_ALT_URLS:
                    self._base = alt
                    try:
                        return await self._request(method, path, params, json, _retry=False)
                    except JiaChaoError:
                        continue
                self._base = API_BASE_URL
            raise JiaChaoError(f"请求 {path} 失败: {err}") from err

        code_raw = data.get("code", 200) if isinstance(data, dict) else 200
        # 错误码为 int（464/471/479/...）；str 类型的 code 是会话标识（如 login/code 返回），放行
        if isinstance(data, dict) and isinstance(code_raw, int) and code_raw not in (200, 0):
            msg = data.get("msg") or data.get("message") or ""
            if code_raw in (401, 10001, 10002):
                raise JiaChaoAuthError(msg or f"认证失败(code={code_raw})")
            if code_raw == 479:
                raise JiaChaoCodeRequiredError(msg or "需要短信二次验证")
            if code_raw == 464:
                raise JiaChaoAuthError(msg or "用户密码不匹配")
            if code_raw == 471:
                raise JiaChaoError(msg or "验证码请求过于频繁，请稍后再试")
            raise JiaChaoError(msg or f"{path} 错误(code={code_raw})")
        return data

    # -- 登录 ----------------------------------------------------------------
    @staticmethod
    def _base_params(account: str, uuid_val: str) -> dict:
        return {
            "countryCode": "+86",
            "name": account,
            "os": "android",
            "osVer": "15",
            "app": "com.dc.jiachao",
            "appVer": "2.2.2",
            "phoneBrand": "HA",
            "pushToken": "",
            "uuid": uuid_val,
            "lang": "zh",
        }

    async def login(self, account: str, password: str,
                    uuid_val: str | None = None) -> dict:
        """账号密码登录（GET + MD5 密码，实测协议）。

        响应成功: {"expireAt":..., "role":0, "token":"<JWT>", "userInfo":{...}}
        若 uuid 未受信任，服务器返回 code=479 需要短信二次验证
        （此时抛 JiaChaoCodeRequiredError，由配置流程引导输验证码）。
        """
        md5_pwd = hashlib.md5(password.encode("utf-8")).hexdigest()
        params = self._base_params(account, uuid_val or str(uuid.uuid4()))
        params["password"] = md5_pwd
        data = await self._request("GET", API_PATH_LOGIN, params=params)
        return self._parse_login(data)

    async def request_login_code(self, account: str, uuid_val: str) -> None:
        """触发短信验证码（GET /v2/user/login/code，无 password）。

        服务器会向用户手机发送验证码短信，并返回一个会话 code
        （该响应中的 code 字段是 32 位会话标识，不是错误码，不能走通用检查）。
        """
        params = self._base_params(account, uuid_val)
        params["region"] = "CN"
        url = self._base + API_PATH_LOGIN_CODE
        headers = dict(API_HEADERS)
        async with self._session.get(
            url, params=params, headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise JiaChaoError(f"发送验证码失败(HTTP {resp.status})")
            data = await resp.json(content_type=None)
            code = data.get("code") if isinstance(data, dict) else 200
            if isinstance(code, int) and code not in (200, 0):
                raise JiaChaoError(data.get("msg") or f"发送验证码失败(code={code})")

    async def login_with_code(self, account: str, sms_code: str,
                              uuid_val: str) -> dict:
        """短信验证码登录（GET /v2/user/code/login，实测成功）。"""
        params = self._base_params(account, uuid_val)
        params["code"] = sms_code
        params["region"] = "CN"
        data = await self._request("GET", API_PATH_CODE_LOGIN, params=params)
        return self._parse_login(data)

    def _parse_login(self, data: dict) -> dict:
        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            raise JiaChaoAuthError("登录响应中未找到 token")
        self._token = str(token)
        user_info = data.get("userInfo") or {}
        return {
            "token": str(token),
            "userId": str(user_info.get("userId", "")),
            "userInfo": user_info,
            "expire_at": data.get("expireAt"),
        }

    async def set_token(self, token: str) -> bool:
        """校验并设置 token。"""
        self._token = token
        try:
            info = await self.get_user_info()
            return bool(info)
        except JiaChaoError:
            self._token = None
            return False

    async def get_user_info(self) -> dict:
        data = await self._request("GET", API_PATH_INFO)
        return data.get("data", data) if isinstance(data, dict) else {}

    async def get_homes(self) -> list[dict]:
        data = await self._request("GET", API_PATH_HOMES)
        return data if isinstance(data, list) else data.get("list", [])

    async def get_rooms(self, home_id: int, home_db: str = "CN") -> list[dict]:
        data = await self._request("GET", API_PATH_ROOMS,
                                   params={"homeID": home_id, "homeDB": home_db})
        return data.get("list", []) if isinstance(data, dict) else []

    async def get_devices(self) -> list[dict]:
        """返回设备列表（App 实测返回 {list:[...]}）。"""
        data = await self._request("GET", API_PATH_DEVICES)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list", []) or data.get("devices", [])
        return []

    async def get_device_info(self, device_id: str) -> dict:
        """获取设备详情（含 mqtt 服务器与凭据）。"""
        data = await self._request("GET", API_PATH_DEVICE_INFO,
                                   params={"ID": device_id})
        return data.get("data", data) if isinstance(data, dict) else {}
