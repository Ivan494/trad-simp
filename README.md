# 繁简转换

Windows tray app that flips selected Chinese text between Traditional and Simplified with a global hotkey.

Select text anywhere, press the hotkey (default `Alt+\``), and the selection is replaced in place. Traditional becomes Simplified; Simplified becomes Traditional.

## Install

Download **Trad2Simp.exe** from the [latest release](https://github.com/Ivan494/trad-simp/releases/latest) and run it. No installer. Settings live in `%APPDATA%\Trad2Simp`.

The first close minimizes to the tray. Right-click the tray icon to quit.

## Usage

1. Start `Trad2Simp.exe`. Listening begins immediately.
2. Select Chinese text in any window.
3. Press `Alt+\`` (or the combo you recorded).
4. The selection is replaced with the other script.

| | |
|---|---|
| Default hotkey | `Alt+\`` |
| Record a new combo | Click **记录**, then press the keys |
| Mixed text | Follows whichever direction rewrites more characters |
| Non-Chinese | Left unchanged |

Works in editors, browsers, and most desktop apps. Elevated (admin) windows will not receive injected copy/paste unless this app is also elevated.

## Run from source

Windows, Python 3.12+:

```powershell
pip install -r requirements.txt
python -m trad2simp
```

Tests:

```powershell
python test_all.py
```

Build a one-file exe:

```powershell
pip install pyinstaller
python -m PyInstaller --noconfirm Trad2Simp.spec
```

The binary is written to `dist\Trad2Simp.exe`.

## How it works

- Global hotkey via `RegisterHotKey` (not a low-level keyboard hook).
- Selection is copied, converted with [OpenCC](https://github.com/BYVoid/OpenCC) (`t2s` / `s2t`), and pasted back. The previous clipboard is restored.
- A dummy key + `WM_CANCELMODE` on fire so an `Alt` combo does not open the target app’s menu bar.
- Copy is retried (`WM_COPY`, `Ctrl+C`, `Ctrl+Insert`) if the first attempt is swallowed.

## License

MIT
