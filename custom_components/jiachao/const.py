"""Constants for the 家超 integration."""
from __future__ import annotations

DOMAIN = "jiachao"
PLATFORMS: list[str] = ["sensor", "light", "switch"]

# API Configuration
DEFAULT_BASE_URL = "https://dc02.iotdreamcatcher.net.cn"

# API Endpoints
API_LOGIN = "/v2/user/code/login"
API_LOGOUT = "/v2/user/logout"
API_USER_INFO = "/v2/user/account/now"
API_DEVICE_LIST = "/v2/user/device/list"
API_GROUP_HOMES = "/v2/group/homes"
API_GROUP_HOME = "/v2/group/home"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BASE_URL = "base_url"

# Version
VERSION = "1.7.4"
