# 家超睡眠灯 Home Assistant 集成

通过 WiFi 连接控制家超（Jiachao）睡眠灯的 Home Assistant 自定义集成。

## 功能特性

- **灯光控制**：开关、亮度调节（0-100%）
- **色温调节**：冷暖色温调节（2000K-6500K）
- **RGB 颜色**：全彩颜色控制
- **场景模式**：阅读、放松、睡眠、夜灯、专注、暖光、冷光、浪漫、派对等 9 种预设场景
- **白噪音**：通过服务调用控制白噪音播放
- **音量控制**：通过服务调用调节设备音量
- **状态同步**：通过 MQTT 实时同步设备状态
- **自动发现**：登录后自动列出账号下绑定的睡眠灯设备

## 支持的设备

基于 APK 逆向分析，以下设备类型已识别：

| 设备型号 | 类型代码 | 说明 |
|---------|---------|------|
| LT800 | lt800 | 家超睡眠灯（基础款） |
| LT800P / LT800P Pro | lt800p | 家超睡眠灯（增强款，支持白噪音、番茄钟等） |
| LS301 | ls301 | 家超智能灯 |
| LT955 | lt955 | 家超爱心灯 |

## 安装方法

### 方法一：手动安装

1. 将 `jiachao` 文件夹复制到 Home Assistant 的 `custom_components` 目录：
   ```
   config/
   └── custom_components/
       └── jiachao/
           ├── __init__.py
           ├── api.py
           ├── config_flow.py
           ├── const.py
           ├── light.py
           ├── manifest.json
           ├── mqtt_client.py
           ├── services.yaml
           ├── strings.json
           └── translations/
               └── zh-Hans.json
   ```

2. 重启 Home Assistant

### 方法二：HACS（待发布）

将本仓库添加到 HACS 自定义仓库，然后搜索"家超睡眠灯"安装。

## 依赖项

集成会自动安装以下 Python 依赖：
- `paho-mqtt>=1.6.1` - MQTT 客户端
- `pycryptodome>=3.18.0` - AES 加密库

## 配置方法

1. 进入 **设置 → 设备与服务 → 添加集成**
2. 搜索并选择 **"家超睡眠灯"**
3. 输入家超 APP 的登录信息：
   - **用户名**：手机号或邮箱
   - **密码**：家超 APP 登录密码
4. 点击提交，集成会自动登录并获取设备列表
5. 从下拉列表中选择要控制的睡眠灯设备
6. 完成配置，设备将出现在实体列表中

## 实体说明

配置完成后，将创建以下实体：

| 实体类型 | 实体 ID 格式 | 说明 |
|---------|-------------|------|
| 灯 | `light.jiachao_<device_id>_light` | 主灯控制实体 |

灯实体支持的属性：
- `brightness` - 亮度（0-255）
- `color_temp` - 色温（mireds）
- `hs_color` - HSV 颜色
- `effect` - 当前场景模式
- `volume` - 设备音量（额外属性）
- `white_noise` - 当前白噪音（额外属性）

## 服务调用

除了标准灯控制外，集成还提供以下自定义服务：

### `jiachao.set_white_noise` - 设置白噪音

```yaml
service: jiachao.set_white_noise
target:
  entity_id: light.jiachao_xxxx_light
data:
  noise_id: 1  # 白噪音 ID，0 为关闭
```

### `jiachao.set_volume` - 设置音量

```yaml
service: jiachao.set_volume
target:
  entity_id: light.jiachao_xxxx_light
data:
  volume: 50  # 音量百分比 0-100
```

## 自动化示例

### 睡前自动开启睡眠模式

```yaml
automation:
  - alias: "睡前开启睡眠灯"
    trigger:
      - platform: time
        at: "22:30:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.jiachao_xxxx_light
        data:
          brightness: 30
          effect: "睡眠"
      - service: jiachao.set_white_noise
        target:
          entity_id: light.jiachao_xxxx_light
        data:
          noise_id: 1
      - service: jiachao.set_volume
        target:
          entity_id: light.jiachao_xxxx_light
        data:
          volume: 20
```

### 早晨模拟日出唤醒

```yaml
automation:
  - alias: "早晨日出唤醒"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.jiachao_xxxx_light
        data:
          brightness: 10
          color_temp: 500  # 暖光
      - delay:
          minutes: 5
      - service: light.turn_on
        target:
          entity_id: light.jiachao_xxxx_light
        data:
          brightness: 128
          color_temp: 350
      - delay:
          minutes: 5
      - service: light.turn_on
        target:
          entity_id: light.jiachao_xxxx_light
        data:
          brightness: 255
          color_temp: 200  # 冷白光
```

## 协议逆向分析摘要

本集成基于对 `jiachao.apk`（约 176MB，Flutter 应用）的逆向分析开发。

### 应用架构
- **框架**：Flutter（Dart AOT 编译，核心逻辑在 `libapp.so`）
- **包名**：`com.dc.jiachao`
- **云服务器**：`iotdreamcatcher.net` / `iotdreamcatcher.net.cn`

### 通信协议
- **传输层**：MQTT（`libflutter_mqtt.so`），支持 TLS
- **加密层**：
  - AES-128-CBC 加密 payload（PKCS7 填充）
  - RSA 用于配网时的密钥协商（`librsa_bridge.so`，fast_rsa 库）
- **数据包结构**：
  ```
  flag(1字节) + seq(2字节, 大端) + payload_len(2字节, 大端) + payload
  ```
  - flag 高位置 1 表示 payload 已加密
  - 最大包长：800 字节
- **编码**：MQTT payload 为 Base64 编码的加密数据包

### MQTT Topic 格式
- 状态上报：`jc/{device_id}/status`
- 控制命令：`jc/{device_id}/control`
- 在线状态：`jc/{device_id}/online`

### 配网流程
1. 手机通过 BLE 连接设备
2. 协商 AES 密钥（`BleWiFiNegotiateSecretKeyResult`）
3. 通过 BLE 发送 WiFi SSID 和密码
4. 设备连接 WiFi 后，通过云 MQTT 上报上线

### 设备控制字段
| 字段 | 类型 | 说明 |
|------|------|------|
| `power` | bool | 开关状态 |
| `brightness` | int | 亮度（0-100） |
| `colorTemp` | int | 色温（Kelvin） |
| `color` | object | RGB/HSV 颜色 `{hue, saturation}` |
| `scene` | string | 场景模式 ID |
| `volume` | int | 音量（0-100） |
| `whiteNoise` | int | 白噪音 ID（0=关闭） |

## 注意事项与限制

1. **云依赖**：当前版本通过家超云 MQTT 服务器控制设备，需要设备和 HA 均能访问互联网。局域网直连模式待开发。

2. **AES 密钥**：APK 中使用的默认 AES 密钥可能不适用于所有设备。部分设备在配网时会协商设备特定密钥。如遇控制无响应，可能需要通过 BLE 抓包获取设备特定密钥。

3. **设备兼容性**：已针对 LT800 系列优化，其他型号（LS301、LT955 等）的字段可能略有差异，如遇问题请提供设备型号和 APP 版本。

4. **状态延迟**：MQTT 状态同步通常在 1-2 秒内完成，极端网络情况下可能更长。

5. **多设备**：每个设备需要单独添加配置条目。

## 故障排查

### 设备显示不可用
- 检查 HA 能否访问 `iotdreamcatcher.net` 的 MQTT 端口
- 检查设备是否在线（家超 APP 中查看）
- 查看 HA 日志中的 MQTT 连接错误

### 控制无响应
- 确认设备在家超 APP 中可以正常控制
- 检查 HA 日志中是否有加密/解密错误
- 尝试重新配置集成（重新登录获取最新 MQTT 配置）

### 登录失败
- 确认用户名密码正确（家超 APP 可登录）
- 检查网络连接
- 部分账号可能需要验证码登录，当前版本仅支持密码登录

## 开发说明

### 文件结构
```
jiachao/
├── __init__.py       # 集成初始化、服务注册
├── api.py             # 家超云 HTTP API 客户端
├── config_flow.py     # 配置流程（登录+设备选择）
├── const.py           # 常量定义
├── light.py           # 灯实体实现
├── manifest.json      # 集成清单
├── mqtt_client.py     # MQTT 客户端+AES 加密协议
├── services.yaml      # 服务定义
├── strings.json       # 字符串资源
└── translations/
    └── zh-Hans.json   # 中文翻译
```

### 调试
在 `configuration.yaml` 中启用调试日志：
```yaml
logger:
  default: info
  logs:
    custom_components.jiachao: debug
```

## 许可证

MIT License

## 免责声明

本集成基于对官方 APP 的逆向分析开发，与家超官方无关联。使用本集成产生的任何风险由用户自行承担。请遵守相关法律法规。
