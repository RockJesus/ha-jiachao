# 家超智能灯 (JiaChao) Home Assistant 集成

将「家超」智能灯（Winnermicro W800，WiFi+BLE 双模，App 包名 `com.dc.jiachao`，产品 dtype=LT / pid=25）**接入 Home Assistant**：账号密码登录家超云 → 自动发现设备 → MQTT(TLS) 直连控制开关、亮度、色温。

<div align="center">

[![HACS 审核中](https://img.shields.io/badge/HACS-默认仓库收录审核中-41BDF5.svg)](https://github.com/hacs/default/pull/12368)
[![最新版本](https://img.shields.io/github/v/release/RockJesus/ha-jiachao)](https://github.com/RockJesus/ha-jiachao/releases/latest)
[![GitHub 下载量](https://img.shields.io/github/downloads/RockJesus/ha-jiachao/total)](https://github.com/RockJesus/ha-jiachao/releases)
[![HA 版本](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![许可证](https://img.shields.io/github/license/RockJesus/ha-jiachao)](LICENSE)

</div>

Custom Home Assistant integration for the **JiaChao (家超) smart light** (Winnermicro W800, WiFi + BLE dual-mode). Unofficial, reverse-engineered from the JiaChao mobile app. Every user logs in with their own JiaChao account — fully isolated.

## Features

- **Account login** — phone number + password (MD5 digest) of the JiaChao app
- **Per-user device UUID** — a unique random UUID is generated and persisted per user; no shared or embedded fixed UUID
- **SMS two-step verification** — the first login on a new device requires the SMS code sent to the user's own phone; afterwards password login is code-free
- **Device discovery** — automatically lists the JiaChao lights under the account
- **Light control (verified protocol)** — on/off, brightness (0-255), color temperature (2700K warm → 6500K cool), all confirmed by capture + real-device testing
- **MQTT (TLS) direct** — real topics `smart/<deviceId>/dc/<dc>/din|dout/...`, low-latency control & state subscription

## Installation

### Option 1: HACS (recommended)

This integration is under review for the official **HACS default repository**. Click the button below to open HACS on your Home Assistant and install it in one go:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RockJesus&repository=ha-jiachao&category=integration)

> Button not working? Do it manually: HACS → Integrations → search "**家超智能灯**" or `jiachao` → Download → restart Home Assistant. If the default list has not synced yet, add it as a **custom repository** as a fallback.

### Option 2: Manual installation

<details>
<summary>Expand manual install steps</summary>

1. Download the latest release from [Releases](https://github.com/RockJesus/ha-jiachao/releases)
2. Copy the `custom_components/jiachao/` folder into `/config/custom_components/`
3. Restart Home Assistant

</details>

### Requirements

> [!IMPORTANT]
> Requires **Home Assistant 2024.1 or newer** (HAOS / Supervised / Container / Core all supported; verified on 2026.9).

> Disclaimer: This is an independent, non-official project for research and personal use only. Use it at your own risk. No affiliation with JiaChao or Winnermicro.

---
Home Assistant 自定义集成，接入「家超」智能灯：账号密码登录 → 短信二次验证 → 自动发现设备 → MQTT(TLS) 直连控制开关 / 亮度 / 色温。每个用户登录自己的家超账号，独立 UUID 互不影响。

> ⚠️ 本项目为个人逆向研究作品，与「家超」官方无任何关联。使用本集成即表示同意自行承担相关风险与责任。

## ✨ 功能特性

**登录与多用户**
- 账号密码登录（密码经 MD5 摘要传输，明文不外泄）
- 独立设备 UUID：每用户自动生成独立随机 UUID 并持久化——**不共享、不内置任何固定 UUID**，服务器按「账号 + UUID」绑定信任，多用户互不干扰
- 短信二次验证：首次在新设备登录时家超服务器要求短信验证码（发到该用户自己的手机），输入后完成绑定，**之后密码登录免验证码**
- 高级选项：可填自己家超 App 抓包得到的设备 UUID，登录直接免短信验证码

**设备与灯控（真实协议，实测验证）**
- 设备发现：自动列出账号下的家超灯设备（dtype=LT / pid=25，如「睡眠灯」），选择接入
- 开关 / 亮度（0-255）/ 色温（2700K 暖 → 6500K 冷线性渐变），亮度与色温互不影响
- MQTT(TLS) 直连：真实 topic `smart/<deviceId>/dc/<dc>/din|dout/...`，低延迟控制 + 状态订阅
- 断线保留最后已知状态，连接恢复后自动刷新（v2.2.3）

**稳定性与规范（v2.2.x）**
- token 过期正确触发重新认证（`ConfigEntryAuthFailed`），不再静默吞掉 401（v2.2.3）
- 重新认证 / 重新配置沿用已保存设备 UUID，避免重复收验证码（v2.2.3）
- MQTT 初次连接失败自动后台重连，无需手动重载（v2.2.3）
- hassfest + HACS Action CI 全绿（v2.2.1 起）；manifest / translations / brand 均对齐 HA 官方规范（v2.2.1 / v2.2.2）

## 📦 安装方法

### 方式一：通过 HACS 安装（推荐）

本集成正在审核加入 **HACS 官方默认仓库**，点击下方按钮即可在你的 Home Assistant 中直接打开 HACS 并安装：

[![在 HACS 中打开](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RockJesus&repository=ha-jiachao&category=integration)

> 按钮无法使用？也可手动操作：HACS → 集成 → 搜索「**家超智能灯**」或 `jiachao` → 下载 → 重启 Home Assistant。若默认列表尚未同步，可先通过「**自定义存储库**」添加 `https://github.com/RockJesus/ha-jiachao`（类别：集成）。

### 方式二：手动安装

1. 在 [Releases](https://github.com/RockJesus/ha-jiachao/releases) 下载最新版压缩包
2. 解压后将 `custom_components/jiachao/` 整个目录复制到 HA 的 `/config/custom_components/` 下
3. 重启 Home Assistant

### ⚙️ 环境要求

> [!IMPORTANT]
> 需要 **Home Assistant 2024.1 及以上版本**（HAOS / Supervised / Container / Core 均可，2026.9 实测可用）。

## 🚀 配置

1. 设置 → 设备与服务 → 添加集成 → 搜索「**家超智能灯**」
2. 输入家超 App **手机号 + 密码**（设备 UUID 留空即可）
3. 若提示短信验证，输入自己手机收到的验证码
4. 选择要接入的灯设备 → 完成

> 高级：从自己家超 App 抓包得到设备 UUID（如 `GET /v2/user/login` 请求参数），填入后密码登录**直接免短信验证码**（详见下方「多用户 / 隐私说明」）。

## 🔌 支持的实体

| 类型 | 实体 | 说明 |
|---|---|---|
| light | 家超智能灯（每设备一个） | 开关 / 亮度（0-255）/ 色温（2700-6500K 线性映射），MQTT 状态订阅低延迟刷新 |

## 📡 协议实现依据（2026-09-24 实测锁定 + 用户实机确认）

| 层 | 结论 | 来源 |
| --- | --- | --- |
| API 域 | `https://dc02.iotdreamcatcher.net.cn:12443`（/v2/） | mitmproxy 抓包（API 流量全明文） |
| 登录 | `GET /v2/user/login`，`password=MD5(密码)`；479 需短信验证；464 密码错误 | 实测 |
| 验证码 | `GET /v2/user/login/code`（发码，471 限频）；`GET /v2/user/code/login?code=<短信码>`（登录） | 实测 |
| MQTT | TLS 8883，SNI 域名；username=`<deviceId>_CN<userId>`，password=设备级 mqtt token；clientId=`and_<deviceId>_<随机>` | 手写 CONNECT 实测 CONNACK=0 |
| 命令 topic | `smart/<deviceId>/dc/25/din/config` | 订阅 `+/+/#` 实抓到 App 流量 |
| 状态 topic | `smart/<deviceId>/dc/25/dout/status`、`/dout/online` | 同上（含设备 IP/MAC 上报） |
| 命令格式 | `{"m":{"req":{"a":"value_set","mo":...,"rand":...}}}` | 实测控制成功 |
| 开关 | `value_set mo=225`（开）/ `mo=224`（关） | 用户实机确认方向 |
| 亮度 | `value_set mo=129 lc=<0-255> wv=<当前色温> wh=500` | 实测 lc=60/116/230 生效 |
| 色温 | `value_set mo=129 lc=<当前亮度> wv=<0-1000: 0暖→1000冷> wh=500` | 用户实机确认：暖→冷渐变，亮度保持不变 |

## ❓ 常见问题

| 问题 | 说明 |
|---|---|
| 其他网友能登录自己的账号吗？ | **能**。每个用户留空 UUID 时，集成自动生成**独立随机 UUID** 并存入各自 HA 配置；服务器按「账号 + UUID」绑定信任，互不干扰 |
| 首次登录要验证码吗？ | 要（发到该用户自己的手机）。验证通过后 UUID 绑定该账号，**之后密码登录免验证码** |
| 内置的 UUID 有影响吗？ | **发布版已移除内置固定 UUID**。固定 UUID 是开发者的私有设备标识，公开后会被他人登录污染信任关系，且对其他用户无益 |
| 我的账号会被他人影响吗？ | 不会。每人用自己的 UUID + 自己的账号；集成内不保存他人任何凭据 |
| 填自己 App 的 UUID 有什么用？ | 高级用户从自己家超 App 抓包得到 UUID（如 `GET /v2/user/login` 请求参数），填入后密码登录**直接免短信验证码** |
| 灯的状态/色温依据？ | mo=225/129 为开、224 为关（用户实机确认）；wv=0 → 2700K（暖）、wv=1000 → 6500K（冷）线性映射 |
| 收不到验证码？ | 家超服务器限频（code=471），连续失败请间隔几分钟再试；也可填自己的 App UUID 绕过验证码 |
| 登录被风控？ | 家超服务器可能对登录做风控，请勿高频重试登录 |

## ⚠️ 免责声明

1. **非官方项目**：本项目为个人逆向研究作品，与「家超」、Winnermicro 及任何官方主体**无任何关联、未经任何授权**；「家超」等商标归各自权利人所有，本文中引用仅用于识别所对接的服务。
2. **仅供学习研究**：本项目包含逆向工程所得协议素材（API 端点、MQTT topic、命令载荷等），仅限**个人学习研究**与**自用**，请勿用于商业用途。
3. **风险自担**：使用本集成可能导致账号风控、功能失效、违反服务条款等后果，**一切风险与责任由使用者自行承担**；作者不提供任何服务可用性担保。
4. **数据本地**：您的账号与设备数据仅存储在您自己的 Home Assistant 中，集成除家超官方服务端外不向任何第三方传输、共享您的数据。
5. **下架配合**：若相关权利方要求移除逆向素材或本仓库，作者将配合下架。

## 💖 支持作者

[![RJ](https://img.shields.io/badge/Rock-Jesus-purple.svg)](https://rockjesus.cn)

## 📜 版本历史

<details>
<summary>完整版本历史（点击展开）</summary>

- **v2.2.5**（2026-10-23）：**README 按福特派模板全面优化**——双语（中/英）功能特性与安装说明、HACS 官方安装按钮、支持的实体表、协议实现依据表、FAQ、五项免责声明、折叠版本历史；安装说明保持「HACS 搜索优先」
- **v2.2.4**（2026-10-23）：安装说明改为「HACS 搜索优先」：默认列表收录后可直接搜索 `家超智能灯` / `jiachao` 安装，自定义存储库降为备选（对齐 HACS 收录后 README 规范）
- **v2.2.3**（2026-10-22）：修复 token 过期不触发 reauth / reauth 换 UUID / MQTT 初连失败不重连 / light 在线状态恒 True 死代码
- **v2.2.2**（2026-10-21）：按 HA 官方规范补齐（ConfigEntryAuthFailed/NotReady + reauth/reconfigure + light 实体名修复 + loggers + brand 8 图 + pyflakes 清理 + translations）
- **v2.2.1**（2026-10-21）：严格按 HA 官方集成发布规范修复（manifest requirements 移除 paho-mqtt=HA 自带、显式 integration_type、hacs.json 删 domains/iot_class、新增 translations/en.json、新增 hassfest+HACS Action CI、brand 图标规范）
- **v2.2.0**（2026-10-21）：家超智能灯接入（账号密码登录 / 短信二次验证 / 设备发现 / 亮度色温控制 / MQTT TLS 直连）；协议详见「协议实现依据」

</details>
