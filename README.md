# 家超 Home Assistant 集成

Home Assistant 自定义集成，用于连接家超智能家居平台。

## 功能特性

- ✅ 用户名密码登录
- ✅ 用户信息传感器
- 🚧 设备列表（开发中）
- 🚧 灯光控制（开发中）
- 🚧 开关控制（开发中）

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

## API 说明

本集成基于家超 App 抓包分析，主要接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v2/user/login` | POST | 登录 |
| `/v2/user/account/now` | GET | 获取用户信息 |
| `/v2/user/device/list` | GET | 获取设备列表 |

## 注意事项

- 本集成仅供学习交流使用
- 请遵守家超相关服务条款
- 如有问题请提交 Issue

## License

MIT License
