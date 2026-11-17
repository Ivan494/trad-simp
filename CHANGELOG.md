# 更新记录 / Changelog

## 1.1.3

- 移除导致界面卡住的开机启动设置及全部启动注册表访问。
- 保留 v1.1.2 已验证的 Alt + ` 快捷键、Ego/Chromium 剪贴板兼容修复和转换方式。
- 关闭窗口继续直接进入托盘，再次运行显示已有窗口。
- 补充旧版启动项的移除说明。

English: remove startup registration, retain the verified hotkey and Chromium clipboard fixes, and document removal of older startup entries.

## 1.1.2

- 修复 Ego 等 Chromium 浏览器复制后，剪贴板来源元数据导致转换被跳过的问题；完整保留这些格式。
- 浏览器直接使用快捷键复制，省去不受支持的窗口消息等待；先检查全部剪贴板格式，再读取内容。
- 增加转换耗时和跳过原因的运行日志，不记录选中文字、剪贴板内容或个人路径。

English: fix conversion being skipped after Chromium/Ego copies, preserve browser clipboard metadata, remove an unnecessary copy delay, and add content-free timing diagnostics.

## 1.1.1

- 关闭窗口直接进入托盘，首次关闭也不弹出提示。
- Closing the window now goes straight to the tray without a first-close dialog.

## 1.1.0

- 新增可选开机启动，登录后静默进入托盘。
- 新增自动、转简体、转繁体三种模式，保留用户设置。
- 支持的单行 Windows 文本框直接转换，不使用剪贴板。
- 兼容方式保护剪贴板常见格式和空状态；检测焦点改变与并发复制。
- 修复设置损坏、快捷键冲突/录制、后台线程访问界面和退出时序问题。
- 网页演示可离线使用，修复原 CDN 路径和复制失败提示。
- 统一版本元数据，锁定依赖与 CI actions，新增隐私审计、构建来源和 SHA-256 校验。

English: opt-in startup to tray, persistent conversion modes, direct conversion for supported single-line controls, guarded clipboard fallback, reliability fixes, offline demo, and verified release packaging.

## 1.0.1

Hotkey recovery, repeated-launch handling, failed hotkey change recovery, isolated settings tests, release workflow, packaging metadata, and privacy documentation.

## 1.0.0

Initial portable Windows tray release with automatic bidirectional conversion.
