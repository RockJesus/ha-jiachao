# 家超睡眠灯 Home Assistant 集成 (jiachao_light)

基于 BLE 蓝牙的家超睡眠灯自定义集成，支持开关、亮度调节、RGB 颜色、色温、效果模式。

## 功能特性

- 开关控制
- 亮度调节 (0-255)
- RGB 颜色调节 (1600万色)
- 色温调节
- 预设效果模式（彩虹渐变、呼吸、日落伴睡、阅读、放松、夜灯）
- 蓝牙自动发现
- 断线自动重连
- 支持多种 BLE 灯协议预设 + 自定义 UUID

## 支持的协议预设

| 协议标识 | 名称 | 说明 |
|---------|------|------|
| `jiachao_default` | 家超默认（待验证） | 基于常见白牌 BLE 灯方案，默认使用 |
| `magic_blue` | Magic Blue / 魔法蓝灯 | Service=0xffe5, Write=0xffe9 |
| `elk_bledom` | ELK BLEDOM 灯带 | 128-bit UUID 协议 |
| `generic_fff0` | 通用 FFF0 服务 | Service=0xfff0, Write=0xfff3，最常见 |
| `custom` | 自定义协议 | 手动填写抓包得到的 UUID |

## 安装方法

### 方法一：手动安装（推荐）

1. 将 `custom_components/jiachao_light` 整个文件夹复制到你的 HA 配置目录：
   ```
   config/
   └── custom_components/
       └── jiachao_light/
           ├── __init__.py
           ├── config_flow.py
           ├── const.py
           ├── device.py
           ├── light.py
           ├── manifest.json
           ├── protocol.py
           ├── strings.json
           └── translations/
               └── zh-Hans.json
   ```

2. 重启 Home Assistant

3. 进入 **设置 → 设备与服务 → 添加集成**，搜索「家超睡眠灯」

### 方法二：Samba / SSH 上传

如果你通过 SSH 访问 HAOS：

```bash
# 进入配置目录
cd /config

# 创建 custom_components 目录（如果不存在）
mkdir -p custom_components

# 上传 jiachao_light 文件夹到 custom_components/
# （使用 scp / sftp / 或直接编辑文件）

# 重启 HA
ha core restart
```

## 配置步骤

### 第一步：获取设备 MAC 地址

1. 打开家超睡眠灯电源
2. 在 HA 中添加集成时，如果设备在附近，会自动出现在「已发现设备」列表中
3. 如果没有自动发现，使用以下方法之一获取 MAC 地址：
   - **安卓手机**：设置 → 蓝牙 → 已配对设备中查看
   - **nRF Connect**：扫描后点击设备查看 MAC 地址
   - **HA 蓝牙集成**：设置 → 设备与服务 → 蓝牙 → 查看已发现设备

### 第二步：添加集成

1. 设置 → 设备与服务 → 添加集成 → 搜索「家超睡眠灯」
2. 填写：
   - **设备 MAC 地址**：如 `AA:BB:CC:DD:EE:FF`
   - **设备名称**：自定义名称，如「卧室睡眠灯」
   - **协议类型**：先选「家超默认（待验证）」
3. 点击提交

### 第三步：测试控制

1. 在 HA 仪表盘或实体列表中找到新添加的灯
2. 尝试开关、调亮度、换颜色
3. **如果控制无效**，说明默认协议不匹配，需要抓包获取真实协议（见下方抓包指南）

## 抓包逆向指南（默认协议不匹配时必读）

如果安装后灯无法控制，说明家超使用的是私有协议。需要通过抓包获取真实的 UUID 和命令格式。

### 准备工具

- 一部安卓手机（支持蓝牙 HCI 日志）
- nRF Connect APP（Google Play / 应用商店搜索）
- Wireshark（电脑端，用于分析日志）

### 方法一：nRF Connect 直接查看（最简单，获取 UUID）

1. 打开 nRF Connect
2. 点击「SCAN」扫描附近设备
3. 找到你的家超睡眠灯（名称可能是 JiaChao、LT-955、Sleep Light 等），点击「CONNECT」
4. 连接成功后，展开服务列表，你会看到类似这样的结构：
   ```
   Service: 0000fff0-0000-1000-8000-00805f9b34fb
     ├── Characteristic: 0000fff1-... (Properties: WRITE)
     ├── Characteristic: 0000fff2-... (Properties: NOTIFY)
     └── Characteristic: 0000fff3-... (Properties: READ)
   ```
5. **记录以下信息**：
   - Service UUID（包含 WRITE 特征的那个服务）
   - Write Characteristic UUID（属性包含 WRITE 的特征）
   - Notify Characteristic UUID（属性包含 NOTIFY 的特征，可选）

6. 回到 HA，重新添加集成，协议类型选「自定义协议」，填入上面记录的 UUID

### 方法二：HCI Snoop 日志抓包（获取完整命令格式）

如果自定义 UUID 后仍然无法控制，需要抓取完整的命令字节：

1. **启用蓝牙 HCI 日志**：
   - 安卓手机：设置 → 开发者选项 → 启用「蓝牙 HCI 信息收集日志」
   - （如果没有开发者选项：设置 → 关于手机 → 连续点击版本号 7 次）

2. **打开家超 APP**，执行以下操作（每个操作间隔 2-3 秒）：
   - 开灯
   - 关灯
   - 亮度调到 50%
   - 亮度调到 100%
   - 切换到红色
   - 切换到绿色
   - 切换到蓝色
   - 切换到暖白光
   - 切换一个效果模式

3. **获取日志文件**：
   - 日志位置：`/sdcard/btsnoop_hci.log` 或 `/sdcard/Android/data/btsnoop_hci.log`
   - 通过 USB 连接电脑，复制该文件

4. **用 Wireshark 分析**：
   - 用 Wireshark 打开 `btsnoop_hci.log`
   - 过滤器输入：`btatt.opcode == 0x12`（只显示 Write Command）
   - 你会看到一系列写入操作，每条都有 Value（十六进制字节）
   - 对照你在 APP 中的操作顺序，记录每条命令的字节：
     ```
     开灯:   7e 04 01 00 00 ef
     关灯:   7e 04 00 00 00 ef
     红色:   7e 07 05 03 ff 00 00 ef
     ...
     ```

5. **将抓包结果发给我**，我可以帮你更新协议处理器代码，让集成完美支持家超设备。

### 常见 BLE 灯命令格式参考

很多白牌 BLE 灯使用以下格式之一：

**格式 A（0x7E 开头，0xEF 结尾）**：
```
开灯:   7E 04 01 00 00 EF
关灯:   7E 04 00 00 00 EF
亮度:   7E 04 01 XX 00 EF    (XX = 亮度 00-FF)
RGB:    7E 07 05 03 RR GG BB EF
白光:   7E 05 02 WW TT EF    (WW=亮度, TT=色温)
效果:   7E 04 XX YY 00 EF    (XX=效果编号, YY=速度)
```

**格式 B（0x56 开头，0xAA 结尾）**：
```
开灯:   CC 23 33
关灯:   CC 24 33
RGB:    56 RR GG BB 00 F0 AA
亮度:   56 00 00 00 WW 0A 0A AA
白光:   56 00 00 00 WW 0F 0A AA
```

**格式 C（0xCC 开头，0x33 结尾）**：
```
开灯:   CC 23 33
关灯:   CC 24 33
```

## 故障排查

### 灯无法连接

1. 确认灯已通电且蓝牙已开启（通常通电即开启）
2. 确认 MAC 地址正确（注意大小写不敏感，但冒号不能少）
3. 确认 HA 主机有蓝牙适配器（HAOS 需支持蓝牙的 USB 适配器或内置蓝牙）
4. 检查 HA 日志：设置 → 系统 → 日志，搜索 `jiachao_light`

### 灯能连接但控制无反应

1. 协议不匹配，尝试切换其他协议预设（Magic Blue / ELK BLEDOM / 通用 FFF0）
2. 如果都不行，按上方「抓包逆向指南」获取真实协议
3. 确认 WRITE 特征的 UUID 正确

### 蓝牙适配器被占用

如果 HA 主机上有其他蓝牙集成（如小米 BLE、蓝牙追踪器），可能会冲突。建议：
- 使用独立的 USB 蓝牙适配器专门用于此灯
- 或在 HA 蓝牙集成设置中分配适配器

### 设备频繁掉线

1. 检查灯和 HA 主机之间的距离，蓝牙有效距离通常 5-10 米
2. 避免金属遮挡和 WiFi 2.4GHz 干扰
3. 集成内置自动重连，掉线后会在 5 秒内尝试重连

## 自动化示例

### 日落伴睡场景

```yaml
alias: 日落伴睡
sequence:
  - service: light.turn_on
    target:
      entity_id: light.bedroom_sleep_light
    data:
      effect: 日落伴睡
      brightness: 180
  - delay:
      minutes: 30
  - service: light.turn_off
    target:
      entity_id: light.bedroom_sleep_light
```

### 睡前自动调暗

```yaml
alias: 睡前自动调暗
trigger:
  - platform: time
    at: "22:30:00"
action:
  - service: light.turn_on
    target:
      entity_id: light.bedroom_sleep_light
    data:
      rgb_color: [255, 140, 50]
      brightness: 80
```

### 起床渐亮

```yaml
alias: 起床渐亮
trigger:
  - platform: time
    at: "07:00:00"
action:
  - service: light.turn_on
    target:
      entity_id: light.bedroom_sleep_light
    data:
      brightness: 10
      color_temp: 400
  - delay:
      minutes: 1
  - service: light.turn_on
    target:
      entity_id: light.bedroom_sleep_light
    data:
      brightness: 255
      transition: 600
```

## 文件结构

```
jiachao_light/
├── README.md                          # 本文件
└── custom_components/
    └── jiachao_light/
        ├── __init__.py                # 集成初始化
        ├── config_flow.py             # 配置流程（UI 添加设备）
        ├── const.py                   # 常量和协议预设定义
        ├── device.py                  # BLE 设备连接管理
        ├── light.py                   # HA Light 实体
        ├── manifest.json              # 集成清单
        ├── protocol.py                # BLE 协议处理器
        ├── strings.json               # 界面字符串
        └── translations/
            └── zh-Hans.json           # 中文翻译
```

## 技术说明

- 基于 `bleak` 库进行 BLE 通信
- 使用 HA 内置蓝牙适配器，无需额外蓝牙服务
- 通信方式为本地 BLE，不依赖云端
- 所有控制命令直接发送到设备，无中间服务器

## 已知限制

1. 目前仅支持 BLE 蓝牙版本的家超睡眠灯（WiFi 版本暂不支持）
2. 设备状态读取依赖 Notify 特征，部分设备可能不支持状态回读
3. 音乐播放功能（如果设备支持）暂未集成
4. 固件升级功能不支持

## 反馈与贡献

如果抓包后发现家超使用的是新协议，请将抓包结果（UUID + 命令字节）反馈，以便更新集成代码，让更多用户受益。
