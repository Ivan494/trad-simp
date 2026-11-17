## 繁简转换 v1.1.1

下载 **Trad2Simp.exe** 即可使用，无需安装。升级前请从托盘退出旧版本，再替换原 exe；设置会保留。

### 新增与改进
- 关闭窗口直接进入托盘，不再弹出提示。
- 可选开机启动，登录后安静进入托盘；默认关闭。
- 自动 / 转为简体 / 转为繁体，适合混排文字。
- 支持的单行 Windows 文本框直接转换，不接触剪贴板。
- 其他应用使用保护性复制/粘贴，保存并还原常见剪贴板格式和空状态；焦点改变或检测到新复制时停止操作。
- 修复设置、快捷键与线程退出问题；演示页完全离线。

### 下载验证
`SHA256SUMS.txt` 提供校验值，`BUILD_INFO.txt` 标明版本与源码提交，`THIRD_PARTY_NOTICES.txt` 包含第三方许可。Windows x64；exe 未进行商业代码签名。

未知剪贴板格式会安全跳过。兼容方式的复制可能被 Windows 历史或第三方剪贴板软件记录；应用自身不记录正文、不联网。

## English

Closing the window now goes straight to the tray without any confirmation dialog.

Portable Windows x64 release with opt-in startup to tray, Auto / To Simplified / To Traditional modes, direct conversion in supported single-line fields, and protected clipboard fallback elsewhere.

Exit the previous version before replacing the executable. Existing settings are retained. Verify downloads against `SHA256SUMS.txt`; `BUILD_INFO.txt` identifies the source commit. The executable is unsigned. Unsupported clipboard formats are skipped; external clipboard history may observe fallback copying. No telemetry, uploads, or automatic update traffic.
