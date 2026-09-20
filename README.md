# 家超 Home Assistant 集成

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Home Assistant 自定义集成，用于连接家超智能家居平台。

## 功能特性

- ✅ 用户名密码登录
- ✅ Token 自动刷新（长期有效）
- ✅ 用户信息传感器
- ✅ 设备自动发现
- 🚧 灯光控制（开发中）
- 🚧 开关控制（开发中）
- 🚧 窗帘控制（开发中）

## 安装

### 方法一：HACS 安装（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中搜索 "家超" 或 "jiachao"
3. 点击下载并重启 Home Assistant

### 方法二：手动安装

1. 下载 `custom_components/jiachao/` 文件夹
2. 将其复制到 Home Assistant 的 `custom_components/` 目录
3. 重启 Home Assistant

## 配置

1. 在 Home Assistant 中，进入 **设置** > **设备与服务**
2. 点击 **添加集成**
3. 搜索 "家超"
4. 输入用户名和密码
5. 点击提交

## 实体说明

### 传感器实体

- **用户信息** - 当前登录用户昵称
  - 属性：user_id、nickname、avatar

### 灯光实体（开发中）

- **名称**：根据设备名称自动命名
- **控制**：开关、亮度、色温

### 开关实体（开发中）

- **名称**：根据设备名称自动命名
- **控制**：开关

## API 说明

本集成基于家超 App 抓包分析，主要接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v2/user/login` | POST | 登录 |
| `/v2/user/logout` | POST | 登出 |
| `/v2/user/account/now` | GET | 获取当前用户信息 |
| `/v2/user/device/list` | GET | 获取设备列表 |
| `/v2/group/homes` | GET | 获取家庭列表 |

## 注意事项

- 本集成仅供学习交流使用
- 请遵守家超相关服务条款
- 如有问题请提交 Issue

## License

MIT License
