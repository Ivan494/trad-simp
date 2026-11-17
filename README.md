# 繁简转换 · Trad2Simp

Windows 便携托盘工具：选中文字，按快捷键，即可原地转换繁体与简体。

[下载最新版本](https://github.com/Ivan494/trad-simp/releases/latest) · [更新记录](CHANGELOG.md) · [安全说明](SECURITY.md)

## 快速开始

1. 下载 **Trad2Simp.exe**，放在固定文件夹，双击运行，无需安装或 Python。
2. 在可编辑文本框内选中文字，按 **Alt + `**。
3. 默认自动判断方向；也可以在窗口中选择 **转为简体** 或 **转为繁体**。

关闭窗口会进入系统托盘，右键托盘图标可显示窗口或退出。再次打开程序会显示已有窗口，不会重复运行。界面标题显示当前版本。

支持 Windows 10/11 x64。下载页同时提供 `SHA256SUMS.txt`、构建来源 `BUILD_INFO.txt` 和第三方许可。可用 PowerShell 的 `Get-FileHash .\Trad2Simp.exe -Algorithm SHA256` 核对校验值。程序尚未使用商业代码签名，校验值用于核对下载完整性。

## 设置

| 设置 | 行为 |
|---|---|
| 快捷键 | 默认 Alt + `；点击「记录」修改，Esc 取消 |
| 自动 | 繁体变简体、简体变繁体；混排按改写字符更多的方向转换，相同则转简体 |
| 转为简体 / 转为繁体 | 固定方向，适合混排文字；下次启动保留 |

已移除开机启动功能，程序不再读写启动注册表。若在 v1.1.0–v1.1.2 中开启过此功能，可在 Windows 终端运行以下命令，仅移除本程序的旧启动项：

```powershell
reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Trad2Simp /f
```

升级时先从托盘退出旧版本，再用新 exe 替换原文件；配置会保留。卸载时退出并删除 exe；如需清除设置，可另行删除 `%APPDATA%\Trad2Simp`。

## 转换与剪贴板

- 支持的标准 Windows **单行**文本框使用直接替换，不接触剪贴板，并保留该控件的撤销操作。
- 浏览器、Electron、富文本和多行输入框使用兼容的复制/粘贴方式。程序先在内存中保存剪贴板，再转换选区，最后还原。
- 保存常见文本、HTML/RTF、位图/DIB、PNG 和文件列表；空剪贴板也会还原为空。如果存在无法安全保存的格式、数据过大或剪贴板锁定，程序会跳过并显示原因。
- 转换期间切换窗口会取消操作；如果其他程序更新剪贴板，不会用旧内容覆盖它。
- 非中文或无选区时不替换。密码框、只读字段及限制自动化的应用可能不支持；不同软件的撤销、格式保留和异步粘贴行为由目标程序决定。
- 管理员窗口通常拒绝普通权限程序注入。请仅在确有需要时以相同权限运行。

## 隐私

桌面程序完全本地运行：无账号、无遥测、无自动更新请求，也不上传选中文字。

配置和有限大小的状态日志位于 `%APPDATA%\Trad2Simp`。日志不保存正文、剪贴板内容或原始异常详情。转换仅在触发快捷键时进行，不持续读取剪贴板。

兼容方式会短暂使用系统剪贴板：虽然程序还原当前内容，并为自身写入设置不进入历史/云同步的标志，但目标应用发出的复制，以及第三方剪贴板管理器或 Windows 历史记录，仍可能保存内容。不能将「还原剪贴板」理解为清除这些外部历史。

## 从源码运行

Windows，Python 3.12+：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m trad2simp
```

回归测试：`python test_all.py`。测试使用临时配置；真实剪贴板测试运行在独立的 Windows 窗口站/桌面，不读写用户当前剪贴板。受限沙箱可能不允许创建测试桌面，此时测试明确失败。

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm Trad2Simp.spec
python scripts/audit.py --artifact dist/Trad2Simp.exe
python scripts/release_assets.py
```

程序版本统一定义于 `trad2simp/version.py`。发布 CI 在干净 Windows runner 上测试、构建、审计并生成校验值；上传后再下载验证，通过后才发布为 Latest。

## 离线网页演示

打开 `index.html`，保留同目录下的 `vendor` 文件夹。JavaScript 与字典已随仓库附带，不依赖 CDN，不上传输入。演示使用 OpenCC JavaScript 的地区规则，与桌面 OpenCC `t2s`/`s2t` 不保证完全相同。浏览器阻止自动复制时，可手动选择结果。

## English

Select Chinese text in an editable field and press **Alt + `**. Choose Auto, To Simplified, or To Traditional. Download the portable Windows x64 executable from [the latest release](https://github.com/Ivan494/trad-simp/releases/latest).

Launch the app manually; closing settings hides it to the tray without a dialog. Startup registration has been removed. If you enabled it in v1.1.0–v1.1.2, use the `reg delete` command above to remove only Trad2Simp's old startup entry.

Supported standard single-line Edit controls convert without using the clipboard. Other apps use a guarded clipboard fallback that restores supported formats and avoids overwriting a newer copy. Unsupported formats cause conversion to be skipped. Clipboard history and external managers may still observe fallback copying.

Offline, no telemetry or automatic updater. Settings and content-free status logs live in `%APPDATA%\Trad2Simp`. Source builds and tests are documented above. Check `SHA256SUMS.txt` and `BUILD_INFO.txt` for integrity and provenance. The executable is unsigned.

## License

MIT · Copyright (c) 2026 Ivan494. OpenCC and other bundled components retain their own licenses; see `THIRD_PARTY_NOTICES.txt` in the release and `vendor/opencc-js/LICENSE` for the demo.
