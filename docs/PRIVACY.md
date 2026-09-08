# 隐私说明

本项目没有遥测、统计分析、广告、云端账号、自动上传或自动更新功能。

本地仅保存：

- Windows Credential Manager 中的校园网账号和密码；
- `%LOCALAPPDATA%\SEUCampusAutoLoginOSS\logs` 中的滚动日志；
- 自动启动模式及认证被拒绝后的暂停标记，不含账号密码；
- 用户主动运行 `diagnose` 或 `测试.cmd` 时生成的脱敏诊断报告，包括任务触发器类别、最近运行时间及结果码。

日志和诊断报告不应包含账号、密码、Cookie、完整请求参数、MAC 或 SSID。项目不会读取其他 Windows 凭据、浏览器密码、Wi-Fi 密码或个人文件。
