"""pytest 公共配置。"""
from __future__ import annotations

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """让 HA 能发现 custom_components/jiachao。"""
    yield
