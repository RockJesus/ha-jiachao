# 家超集成修复说明（v2.3.0）

针对 hacs/default PR #12368 最新评审意见的修复。

## 评审依据

frenck 于 2026-11-02T12:32:44Z 的 CHANGES_REQUESTED：

> One thing is left. `custom_components/jiachao/mqtt_client.py` line 20 does `import paho.mqtt.client as mqtt`,
> but `manifest.json` has `"requirements": []`. paho-mqtt is a requirement of Home Assistant's own MQTT integration,
> not of Home Assistant core, so it is only present where that integration has been set up or pre-installed.

同时确认：前两轮的两个问题（`await self.async_show_form(...)`、reauth/reconfigure 未 reload entry）已在 v2.2.6 解决，评审已认可，无需再动。

## 改动内容

只改 `custom_components/jiachao/manifest.json` 一个文件：

```diff
   "requirements": [],
-  "version": "2.2.9"
+  "requirements": [
+    "paho-mqtt>=2.1.0"
+  ],
+  "version": "2.3.0"
```

- `requirements` 新增 `paho-mqtt>=2.1.0`，与评审给出的示例一致。
- `version` 从 `2.2.9` 升到 `2.3.0`，遵循仓库版本规则“遇 10 进 1”：末位达到 9 后再递增即进位到上位并归零（2.2.9 → 2.3.0），不出现 2.2.10。已确认 `v2.3.0` tag 在仓库中未被占用。
- `loggers` 已包含 `paho.mqtt`，无需改动。

## 为什么选 `>=2.1.0` 而不是固定版本

`mqtt_client.py` 中已写了 paho 1.x / 2.x 双兼容逻辑：

```python
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, ...)   # paho 2.x
except (AttributeError, TypeError):
    client = mqtt.Client(...)                                    # paho 1.x
```

因此下限放到 2.1.0 即可保证 2.x 的 `CallbackAPIVersion` 可用，同时不会和 HA 自带 MQTT 集成的 `paho-mqtt==2.1.0`
产生版本冲突。若后续 hassfest 或评审要求固定版本，再改为 `paho-mqtt==2.1.0` 即可。

## 依赖自查

对 `custom_components/jiachao/*.py` 做了 AST 级导入扫描，第三方依赖只有两个：

| 模块 | 来源 | 是否需要写进 requirements |
|---|---|---|
| `paho` | paho-mqtt | **需要**（本次补齐） |
| `aiohttp` | HA 核心自带（`homeassistant.helpers.aiohttp_client`） | 不需要 |

`api.py` 用 `aiohttp`，属于 HA 内置；`coordinator.py` 只依赖 HA 和本项目内部模块。补齐 paho-mqtt 后不存在其他未声明依赖。

## 验证结果

- manifest.json JSON 语法校验通过
- `requirements` 非空，包含 paho-mqtt
- `loggers` 正确覆盖 `paho.mqtt`
- 静态扫描未发现其他未声明第三方依赖

> 尚未执行：hassfest / HACS Action 实跑（需在仓库 CI 中触发），以及无 paho-mqtt 环境下的实机加载验证。
> 推 release 后请确认两个 action 均为绿色再申请重新评审。

## 后续操作清单

1. 提交本 manifest 改动到仓库主分支
2. 打 tag `v2.3.0` 并创建 Release
3. 等待 HACS Action + hassfest Action 全绿，确认 hacs.json 中未出现 `ignore` 键
4. 回到 PR #12368：将 PR 从 draft 转为 Ready for review，并回复 frenck 说明已声明 paho-mqtt
