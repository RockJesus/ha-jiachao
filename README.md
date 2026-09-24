# 家超智能灯 (JiaChao) — Home Assistant 自定义集成 v2.2.0

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

让 Home Assistant 接入「家超」智能灯（Winnermicro W800，WiFi+BLE 双模，App 包名 `com.dc.jiachao`，产品 dtype=LT / pid=25）。

开源发布版：**每个用户独立登录自己的家超账号，互不影响**。

![家超](custom_components/jiachao/icon.png)

## 功能

- **账号密码登录**：使用家超 App 的手机号 + 密码登录（密码经 MD5 摘要传输）
- **独立设备 UUID**：每个用户自动生成独立设备标识并持久化，**不共享、不内置任何固定 UUID**
- **短信二次验证**：首次在新设备登录时，家超服务器会要求短信验证码（发到该用户自己的手机），输入后完成绑定，**之后免验证码**
- **高级选项**：可填入自己家超 App 的设备 UUID（抓包获取），登录直接免短信验证码
- **设备发现**：自动列出账号下的家超灯设备，选择接入
- **灯控制（真实协议，实测验证）**：开关、亮度（0-255）、色温（暖→冷渐变）
- **MQTT(TLS) 直连**：真实 topic `smart/<deviceId>/dc/<dc>/din|dout/...`，低延迟控制 + 状态订阅

## 安装

### 方式一：HACS（推荐）

1. HACS → 右上角三个点 → **自定义存储库**
2. 添加仓库 URL：`https://github.com/RockJesus/ha-jiachao`，类别选择 **集成（Integration）**
3. 下载 → 重启 Home Assistant
4. 「设置 → 设备与服务 → 添加集成」→ 搜索 **家超智能灯**
5. 输入家超 App 手机号 + 密码（设备 UUID 留空即可）→ 若提示短信验证，输入自己手机收到的验证码 → 选择设备 → 完成

### 方式二：手动

1. 将 `custom_components/jiachao/` 整个目录复制到 HA 的 `config/custom_components/` 下
2. 重启 Home Assistant
3. 「设置 → 设备与服务 → 添加集成」→ 搜索 **家超智能灯**
4. 输入家超 App 手机号 + 密码（设备 UUID 留空即可）→ 若提示短信验证，输入自己手机收到的验证码 → 选择设备 → 完成

## 多用户 / 隐私说明（发布版重点）

| 问题 | 说明 |
| --- | --- |
| 其他网友能登录自己的账号吗？ | **能**。每个用户留空 UUID 时，集成自动生成**独立随机 UUID** 并存入各自 HA 配置；服务器按「账号 + UUID」绑定信任，互不干扰 |
| 首次登录要验证码吗？ | 要（发到该用户自己的手机）。验证通过后 UUID 绑定该账号，**之后密码登录免验证码** |
| 内置的 UUID 有影响吗？ | **发布版已移除内置固定 UUID**。固定 UUID 是开发者的私有设备标识，公开后会被他人登录污染信任关系，且对其他用户无益 |
| 我的账号会被他人影响吗？ | 不会。每人用自己的 UUID + 自己的账号；集成内不保存他人任何凭据 |
| 填自己 App 的 UUID 有什么用？ | 高级用户从自己家超 App 抓包得到 UUID（如 `GET /v2/user/login` 请求参数），填入后密码登录**直接免短信验证码** |

## 协议实现依据（2026-09-24 实测锁定 + 用户实机确认）

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

## 已知限制（如实说明）

1. **状态判断**：mo=225/129 为开、224 为关（用户实机确认）。129 为调节模式（灯亮）。
2. **色温映射**：wv=0 → 2700K（暖）、wv=1000 → 6500K（冷），线性映射；HA 色温滑块即暖→冷渐变。
3. 短信验证码发送有频率限制（code=471），连续失败请间隔几分钟再试；若一直收不到，请填自己的 App UUID 绕过验证码。
4. 家超服务器可能对登录做风控，请勿高频重试登录。

## 支持

- HA 版本：2024.x 及以上（2026.9 实测可用）
- 设备：家超 App 下所有 dtype=LT 灯（pid=25 系列，如「睡眠灯」）

## 日志

在 `configuration.yaml` 添加：

```yaml
logger:
  default: warning
  logs:
    custom_components.jiachao: debug
```
