# 繁简转换

Windows 托盘小工具：选中中文，按全局快捷键，繁体 ↔ 简体原地互换。

任意窗口选中文字，按下快捷键（默认 `Alt+\``），选中内容即被替换。繁体变简体，简体变繁体。

## 安装

从 [最新 Release](https://github.com/Ivan494/trad-simp/releases/latest) 下载 **Trad2Simp.exe**，双击运行即可，无需安装。配置保存在 `%APPDATA%\Trad2Simp`。

第一次关闭窗口会最小化到托盘。右键托盘图标可退出。

## 用法

1. 启动 `Trad2Simp.exe`，启动后立即开始监听。
2. 在任意窗口选中中文。
3. 按 `Alt+\``（或你自己记录的组合键）。
4. 选中文字替换为另一种写法。

| | |
|---|---|
| 默认快捷键 | `Alt+\`` |
| 更换快捷键 | 点 **记录**，再按下组合键 |
| 繁简混排 | 按改写字符更多的方向转换 |
| 非中文 | 保持不变 |

编辑器、浏览器和大多数桌面软件都可用。以管理员身份运行的窗口收不到注入的复制/粘贴，除非本程序也以管理员运行。

## 从源码运行

Windows，Python 3.12+：

```powershell
pip install -r requirements.txt
python -m trad2simp
```

测试：

```powershell
python test_all.py
```

仅校验繁简转换（任意平台）：

```powershell
python -c "from trad2simp.convert import flip_script; print(flip_script('臺灣'))"
```

打包单文件 exe：

```powershell
pip install pyinstaller
python -m PyInstaller --noconfirm Trad2Simp.spec
```

生成文件在 `dist\Trad2Simp.exe`。

## 浏览器演示

打开仓库根目录的 `index.html` 可在浏览器里试用同一套繁简互转逻辑（不依赖本机托盘程序）。

## 原理

- 用 `RegisterHotKey` 注册全局快捷键（不是底层键盘钩子）。
- 复制选区，经 [OpenCC](https://github.com/BYVoid/OpenCC)（`t2s` / `s2t`）转换后再粘贴回去，并恢复原来的剪贴板。
- 触发时补发空键并发送 `WM_CANCELMODE`，避免 `Alt` 组合键把目标程序的菜单栏拉开。
- 第一次复制被吞掉时会自动重试（`WM_COPY`、`Ctrl+C`、`Ctrl+Insert`）。

## 隐私与安全

- 纯本地运行：不联网、无账号、无遥测。
- 转换时短暂读写剪贴板（含原先**文本**内容），用完即恢复；若原先剪贴板是图片等非文本格式，转换后通常无法恢复。
- 日志（`%APPDATA%\Trad2Simp\log.txt`）只记长度与状态，不写选中正文。
- 使用 `RegisterHotKey` 与 `SendInput`，不是底层键盘钩子；以管理员运行的窗口需要本程序同样提权才能注入。

## License

MIT

---

## English

Windows tray app that flips selected Chinese between Traditional and Simplified with a global hotkey (default `Alt+\``). Download **Trad2Simp.exe** from [Releases](https://github.com/Ivan494/trad-simp/releases/latest). First close minimizes to the tray.

Fully offline — no network, accounts, or telemetry. Clipboard text is restored after conversion; non-text clipboard formats (e.g. images) generally cannot be restored. Logs store lengths/status, not selected text.

See the Chinese sections above for usage, source build, browser demo (`index.html`), and implementation notes.
