# SEU Campus Auto Login

适用于 Windows 10/11 的东南大学校园网自动登录工具。



> [!IMPORTANT]
> 仅支持登录页为 `http://10.9.10.100/` 的网络环境。

> [!WARNING]
> 当前门户使用 HTTP，密码传输不具备 TLS 保护。本工具无法改变门户本身的传输方式。

## 使用方法

1. 从 Releases 下载 `SEUCampusAutoLoginOSS-0.1.1-windows-x64.zip` 并**全部解压**；不要下载 `Source code`，也不要单独复制 EXE；

   [![Download Latest Release](https://img.shields.io/badge/Download-Latest%20Release-2ea44f?style=for-the-badge&logo=github)](https://github.com/Flynn-woo/seu-campus-autologin-windows/releases/latest)

2. 双击 `安装.cmd`，在本机窗口输入账号和密码；
3. 安装完成后，程序会在登录 Windows、网络重连、睡眠唤醒后检查校园网，并每两分钟补查。

**从旧版升级：**在原来使用的 Windows 账户中运行新版 `安装.cmd` 即可，默认保留凭据并更新任务。无需先卸载，也无需切换管理员账户。重启后需先登录此 Windows 账户，程序才会运行。

若系统限制任务注册，安装器会自动改用“登录触发＋周期检查”或“启动项持续监测”。正常情况下无需手动打开测试窗口；补查最多需等待约两分钟，再加网络认证耗时。

压缩包里只保留三个入口：

```text
安装.cmd    安装或升级自动登录，保留已有凭据
测试.cmd    检查环境和自动启动，可手动认证并生成诊断报告
卸载.cmd    删除公开版任务、凭据、程序和日志
```

安装后的配置、检查和立即运行功能也可以从开始菜单的 `SEU Campus Auto Login OSS` 中使用。

## 特点

- 无需安装 Python，调用电脑已有的 Microsoft Edge；
- 密码保存在 Windows Credential Manager，不写入脚本和日志；
- 已联网时直接退出，不读取密码、不重复登录；
- 只允许向 `10.9.10.100` 提交凭据；
- 错误密码不会连续重试；
- 服务器明确拒绝后暂停后续后台提交，重新配置凭据后恢复；
- 后台静默检查，任务注册失败时仍可监测重连；
- 无遥测、无广告、无自动上传。


## 隐私与安全

请勿在 Issue 中提交账号、密码、Cookie、学号或完整日志。

- [安全政策](.github/SECURITY.md)
- [隐私说明](docs/PRIVACY.md)

## 开发

- [开发、测试与发布](docs/DEVELOPMENT.md)
- [参与贡献](.github/CONTRIBUTING.md)
- [更新记录](docs/CHANGELOG.md)


项目采用 [MIT License](LICENSE)，第三方组件见 [说明](docs/THIRD_PARTY_NOTICES.md)。

## 手动测试成功，但自动登录不工作

先用新版 `安装.cmd` 更新，再运行 `测试.cmd`。它会显示自动启动模式、实际触发器、任务是否启用、上次运行时间和结果码，并生成本机脱敏报告。结果码 `0` 为本次检查完成，`3` 为未配置凭据，`4` 为网关或认证失败，`6` 为后台认证已暂停；`267009`（`0x41301`）表示任务正在运行。

需要反馈时，只提供 `diagnostics-*.json`。报告不会包含账号、密码、学号、SSID、MAC 或用户路径。若显示后台暂停，请从开始菜单“配置凭据”修正信息后再测试；单纯重新安装并保留旧凭据不会解除暂停。
