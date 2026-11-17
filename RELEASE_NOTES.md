## 繁简转换 v1.1.3

下载 **Trad2Simp.exe** 即可使用，无需安装。升级前请从托盘退出旧版本，再替换原 exe；设置会保留。

### 本次修复
- 移除导致界面卡住的开机启动设置及全部启动注册表访问。
- 保留 v1.1.2 已验证的 **Alt + `** 快捷键和 Ego / Chromium 兼容修复。
- 保留自动 / 转为简体 / 转为繁体，以及剪贴板保护。
- 关闭窗口继续直接进入托盘，不弹出提示；再次运行显示已有窗口。

若曾在 v1.1.0–v1.1.2 开启过开机启动，请在 Windows 终端运行以下命令，仅移除本程序的旧启动项：

```powershell
reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Trad2Simp /f
```

### 下载验证
`SHA256SUMS.txt` 提供校验值，`BUILD_INFO.txt` 标明版本与源码提交，`THIRD_PARTY_NOTICES.txt` 包含第三方许可。Windows x64；exe 未进行商业代码签名。

未知剪贴板格式会安全跳过。兼容方式的复制可能被 Windows 历史或第三方剪贴板软件记录；应用自身不记录正文、不联网。

## English

Removes Start with Windows and all startup-registry access after reports of the settings window freezing. Retains the verified Alt+` shortcut, Ego/Chromium clipboard compatibility, conversion modes, clipboard protection, and silent close to tray.

If startup was enabled in v1.1.0–v1.1.2, the command above removes only Trad2Simp's old startup entry.

Exit the previous version before replacing the executable. Existing settings are retained. Verify downloads against `SHA256SUMS.txt`; `BUILD_INFO.txt` identifies the source commit. The executable is unsigned. Unsupported clipboard formats are skipped; external clipboard history may observe fallback copying. No telemetry, uploads, or automatic update traffic.
