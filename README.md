# 家超智能灯 · JiaChao Smart Light

把「家超」智能灯接入 Home Assistant：账号密码登录家超云 → 自动发现设备 → MQTT(TLS) 直连控制**开关 / 亮度 / 色温**。

<div align="center">

[![HACS 官方默认仓库](https://img.shields.io/badge/HACS-官方默认仓库已收录-41BDF5.svg)](https://github.com/hacs/default/pull/12368)
[![最新版本](https://img.shields.io/github/v/release/RockJesus/ha-jiachao)](https://github.com/RockJesus/ha-jiachao/releases/latest)
[![GitHub 下载量](https://img.shields.io/github/downloads/RockJesus/ha-jiachao/total)](https://github.com/RockJesus/ha-jiachao/releases)
[![HA 版本](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![许可证](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[![在 HACS 中打开](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RockJesus&repository=ha-jiachao&category=integration)

</div>

> **English** — Custom Home Assistant integration for the JiaChao (家超) smart light (Winnermicro W800, dual-color-temperature, dtype=`LT` / product_id=`25`). Login with your own JiaChao account, devices are discovered automatically, and control goes over MQTT/TLS (on/off, brightness 0-255, color temp 2700-6500K). Unofficial, reverse-engineered from the mobile app. Every user gets an isolated random device UUID — no shared credentials. Requires Home Assistant 2024.1+. Install via HACS (search `jiachao`) or copy `custom_components/jiachao/` into `/config/custom_components/`. This is a personal research project, not affiliated with JiaChao or Winnermicro; use at your own risk.

---

## 📦 安装

**方式一：HACS（推荐）** — 已收录于 HACS 官方默认仓库。点上方按钮，或手动：HACS → 集成 → 搜索「家超智能灯」或 `jiachao` → 下载 → 重启 Home Assistant。

**方式二：手动** — 从 [Releases](https://github.com/RockJesus/ha-jiachao/releases) 下载最新版，把 `custom_components/jiachao/` 复制到 `/config/custom_components/`，重启。

> [!IMPORTANT]
> 需要 **Home Assistant 2024.1 及以上**（HAOS / Supervised / Container / Core 均可，2026.9 实测可用）。

## 🚀 配置

1. 设置 → 设备与服务 → 添加集成 → 搜索「**家超智能灯**」
2. 输入家超 App **手机号 + 密码**（设备 UUID 留空即可）
3. 若提示短信验证，输入自己手机收到的验证码
4. 选择要接入的灯设备 → 完成

> 高级：填入从自己家超 App 抓包得到的设备 UUID（如 `GET /v2/user/login` 请求参数），密码登录可**直接免短信验证码**。

## ✨ 功能

- **登录**：手机号 + 密码（MD5 摘要传输，明文不外泄）
- **独立 UUID**：每用户自动生成并持久化随机 UUID，**不共享、不内置任何固定 UUID**，服务器按「账号 + UUID」绑定信任，多用户互不干扰
- **短信二次验证**：首次在新设备登录需验证码（发到该用户自己的手机），之后密码登录免验证码
- **设备发现**：列出账号下全部家超设备并标注支持状态，待支持型号会明确提示
- **灯控**：开关 / 亮度（0-255）/ 色温（2700K 暖 → 6500K 冷线性渐变），亮度与色温互不影响
- **MQTT(TLS) 直连**：真实 topic `smart/<deviceId>/dc/<dc>/din|dout/...`，低延迟控制 + 状态订阅
- **离线可见**（v2.3.1+）：设备断连时点灯会**明确报错**而不是静默失败；断连超 30 秒实体标记为不可用，重连自动恢复

## 🔌 支持的实体

| 类型 | 实体 | 说明 |
|---|---|---|
| light | 家超智能灯（每设备一个） | 开关 / 亮度（0-255）/ 色温（2700-6500K 线性映射），MQTT 状态订阅低延迟刷新 |

## 🎯 设备支持范围

**当前仅支持双色温灯**（dtype=`LT` / product_id=`25`，W800 芯片）。

账号下的其他型号（RGB 彩灯、灯带、吸顶灯、开关、窗帘、安防等）会显示为「待支持」——它们的 MQTT 协议尚未抓包，没有真实流量数据无法安全实现。如需扩展，请抓取该型号的流量（模拟器 + Reqable，流程同本灯）后提 Issue / PR。

## ❓ 常见问题

| 问题 | 说明 |
|---|---|
| 其他网友能登录自己的账号吗？ | **能**。每人留空 UUID 时集成自动生成**独立随机 UUID** 存入各自 HA 配置，服务器按「账号 + UUID」绑定信任，互不干扰 |
| 首次登录要验证码吗？ | 要（发到该用户自己的手机）。验证通过后 UUID 绑定该账号，**之后密码登录免验证码** |
| 我的账号会被他人影响吗？ | 不会。每人用自己的 UUID + 自己的账号；集成内不保存他人任何凭据 |
| 收不到验证码？ | 家超服务器限频（code=471），连续失败请间隔几分钟再试；也可填自己的 App UUID 绕过 |
| 登录被风控？ | 家超服务器可能对登录做风控，请勿高频重试 |
| 灯的状态色温映射？ | mo=225/129 为开、224 为关（实机确认）；wv=0 → 2700K（暖）、wv=1000 → 6500K（冷）线性映射 |
| 怎么报 bug？ | 集成页面 → 三点菜单 → **下载诊断信息**，内容已自动脱敏（token / 密码 / UUID / 设备号），可直接贴到 Issue |

## 📡 协议实现依据

2026-09-24 抓包实测锁定 + 用户实机确认：

| 层 | 结论 | 来源 |
| --- | --- | --- |
| API 域 | `https://dc02.iotdreamcatcher.net.cn:12443`（/v2/） | mitmproxy 抓包（明文） |
| 登录 | `GET /v2/user/login`，`password=MD5(密码)`；479 需短信验证；464 密码错误 | 实测 |
| 验证码 | `GET /v2/user/login/code`（发码，471 限频）；`GET /v2/user/code/login?code=<码>` | 实测 |
| MQTT | TLS 8883，SNI 域名；username=`<deviceId>_CN<userId>`，password=设备级 token；clientId=`and_<deviceId>_<随机>` | 手写 CONNECT 实测 CONNACK=0 |
| 命令 topic | `smart/<deviceId>/dc/25/din/config` | 订阅 `+/+/#` 抓到 App 流量 |
| 状态 topic | `smart/<deviceId>/dc/25/dout/status`、`/dout/online` | 同上（含设备 IP/MAC 上报） |
| 命令格式 | `{"m":{"req":{"a":"value_set","mo":...,"rand":...}}}` | 实测控制成功 |
| 开关 | `value_set mo=225`（开）/ `mo=224`（关） | 实机确认 |
| 亮度 | `value_set mo=129 lc=<0-255> wv=<当前色温> wh=500` | 实测 lc=60/116/230 生效 |
| 色温 | `value_set mo=129 lc=<当前亮度> wv=<0-1000: 0暖→1000冷> wh=500` | 实机确认，亮度保持不变 |

## ⚠️ 免责声明

1. **非官方项目**：个人逆向研究作品，与「家超」、Winnermicro 及任何官方主体**无任何关联、未经授权**；相关商标归各自权利人所有。
2. **仅供学习研究**：包含逆向所得协议素材（API 端点、MQTT topic、命令载荷），仅限个人学习与自用，请勿商用。
3. **风险自担**：使用本集成可能导致账号风控、功能失效或违反服务条款，**一切风险与责任由使用者自行承担**。
4. **数据本地**：账号与设备数据仅存储在你自己的 Home Assistant 中，除家超官方服务端外不向任何第三方传输。
5. **下架配合**：若相关权利方要求移除，作者将配合下架。

## 💖 支持作者

[![RJ](https://img.shields.io/badge/Rock-Jesus-purple.svg)](https://rockjesus.cn)

## 📜 版本历史

<details>
<summary>完整版本历史（点击展开）</summary>

- **v2.3.2**（2026-11-04）：工程化补强 —— ① **修复 HA 2024.1–2024.2 兼容性 bug**：`config_entries.SOURCE_RECONFIGURE` 在这些版本不存在，直接取属性会让新建配置在选完设备后崩溃（现改为常量兜底）；② 新增 **13 个自动化测试**（config_flow 全分支 + diagnostics 脱敏），并接入 GitHub Actions 每次提交自动运行；③ 新增 `diagnostics` 诊断导出，token / 密码 / UUID 全脱敏，设备 ID 仅保留末 4 位；④ 实体 `sw_version` 改为自动读取 manifest 版本；⑤ 清理 14 个未被引用的常量；⑥ README 精简（合并中英重复段落）
- **v2.3.1**（2026-11-04）：设备离线时不再"假装成功" —— ① MQTT 未连接时下发控制命令会向用户抛出可读错误（此前命令被静默丢弃、UI 却显示已执行）；② 断线超过 30 秒自动将实体标记为不可用，重连后立即恢复（短暂抖动不闪 UI）；③ 错误文案走翻译键，中英文双语提示
- **v2.3.0**（2026-11-03）：完成 HACS 收录 —— manifest 显式声明 `paho-mqtt>=2.1.0`（此前依赖 HA MQTT 集成隐式携带，未配置 MQTT 的环境下集成无法加载）；审计全部 import 确认无其他未声明依赖；**hacs/default#12368 已合并，进入官方默认仓库**
- **v2.2.9**（2026-10-30）：设备支持框架 —— 配置流程不再静默过滤非支持设备，全部列出并标注型号/支持状态
- **v2.2.8**（2026-10-30）：① MQTT 断线后清除连接事件（此前重载时可能误判"已连接"立即返回）；② 支持同时设置亮度+色温（一次命令下发，避免状态跳变）
- **v2.2.7**（2026-10-29）：修复 token 过期触发重新认证时的崩溃 —— `async_update_reload_and_abort` 是同步回调，`await` 会抛 TypeError
- **v2.2.6**（2026-10-26）：修复 HACS 审核两项 —— ① 无灯光设备时 `async_show_form` 误加 `await` 导致崩溃；② reauth / reconfigure 改用 `async_update_reload_and_abort`，token 更新后立即重载
- **v2.2.5**（2026-10-23）：README 全面优化 —— 双语、HACS 安装按钮、实体表、协议依据表、FAQ、免责声明
- **v2.2.4**（2026-10-23）：安装说明改为「HACS 搜索优先」
- **v2.2.3**（2026-10-22）：修复 token 过期不触发 reauth / reauth 换 UUID / MQTT 初连失败不重连 / light 在线状态恒 True 死代码
- **v2.2.2**（2026-10-21）：按 HA 官方规范补齐（ConfigEntryAuthFailed/NotReady + reauth/reconfigure + light 实体名修复 + loggers + brand 8 图 + pyflakes 清理 + translations）
- **v2.2.1**（2026-10-21）：严格按 HA 官方集成发布规范修复（manifest、integration_type、hacs.json、translations/en.json、hassfest + HACS Action CI、brand 图标）
- **v2.2.0**（2026-10-21）：家超智能灯接入（账号密码登录 / 短信二次验证 / 设备发现 / 亮度色温控制 / MQTT TLS 直连）

</details>
