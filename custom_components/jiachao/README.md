# 家超智能灯 (JiaChao) — Home Assistant 自定义集成 v1.4.2

让 Home Assistant 接入「家超」智能灯（Winnermicro W800，WiFi+BLE 双模，App 包名 `com.dc.jiachao`，产品 dtype=LT / pid=25）。

## 功能

- **账号密码登录**：使用家超 App 的手机号 + 密码登录（密码经 MD5 摘要传输）；内置受信任设备 UUID，**免短信验证码**
- **短信二次验证（后备）**：若受信任 UUID 失效被要求短信验证（code=479），自动进入验证码步骤
- **设备发现**：自动列出账号下的家超灯设备，选择接入
- **灯控制（真实协议，实测验证）**：开关、亮度（0-255）、**色温（暖→冷渐变，用户实机确认本灯为双色温灯）**
- **MQTT(TLS) 直连**：真实 topic `smart/<deviceId>/dc/<dc>/din|dout/...`，低延迟控制 + 状态订阅

## 安装

1. 将 `custom_components/jiachao/` 整个目录复制到 HA 的 `config/custom_components/` 下
2. 重启 Home Assistant
3. 「设置 → 设备与服务 → 添加集成」→ 搜索 **家超智能灯**
4. 输入家超 App 手机号 + 密码 → 选择设备 → 完成（正常情况无需短信验证码）

## 协议实现依据（2026-09-24 实测锁定 + 用户实机确认）

| 层 | 结论 | 来源 |
| --- | --- | --- |
| API 域 | `https://dc02.iotdreamcatcher.net.cn:12443`（/v2/） | mitmproxy 抓包（API 流量全明文） |
| 登录 | `GET /v2/user/login`，`password=MD5(密码)`；信任 UUID 免验证码；479 需短信验证 | 实测 |
| MQTT | TLS 8883，SNI 域名；username=`<deviceId>_CN<userId>`，password=设备级 mqtt token；clientId=`and_<deviceId>_<随机>` | 手写 CONNECT 实测 CONNACK=0 |
| 命令 topic | `smart/<deviceId>/dc/25/din/config` | 订阅 `+/+/#` 实抓到 App 流量 |
| 状态 topic | `smart/<deviceId>/dc/25/dout/status`、`/dout/online` | 同上（含设备 IP/MAC 上报） |
| 命令格式 | `{"m":{"req":{"a":"value_set","mo":...,"rand":...}}}` | 实测控制成功 |
| 开关 | `value_set mo=225`（开）/ `mo=224`（关） | 用户实机确认方向 |
| 亮度 | `value_set mo=129 lc=<0-255> wv=<当前色温> wh=500` | 实测 lc=60/116/230 生效 |
| 色温 | `value_set mo=129 lc=<亮度> wv=<0-1000: 0暖→1000冷> wh=500` | 用户实机确认：暖→冷渐变 |

## 已知限制（如实说明）

1. **状态判断**：mo=225/129 为开、224 为关（用户实机确认）。129 为调节模式（灯亮）。
2. **色温映射**：wv=0 → 2700K（暖）、wv=1000 → 6500K（冷），线性映射；HA 色温滑块即暖→冷渐变。
3. 短信验证码发送有频率限制（code=471），连续失败请间隔几分钟再试。

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
