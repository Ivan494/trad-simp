# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **Windows-only** desktop tray app (Traditional ↔ Simplified Chinese via OpenCC). There is no backend, database, Docker, or network service to start.

### What runs where

| Surface | How to run | Notes |
|---------|------------|--------|
| Desktop app | `python -m trad2simp` (Windows) | Needs Win32 APIs (`user32`/`kernel32`); import fails on Linux/macOS |
| Tests | `python test_all.py` (Windows) | CI uses `windows-latest` (see `.github/workflows/ci.yml`) |
| Convert-only check | import `trad2simp.convert.flip_script` | Pure OpenCC; usable on Linux if you load the module without package `__init__` |
| Browser demo | open `index.html` | Optional CDN OpenCC-js demo; not required for the desktop app |
| Packaging | `python -m PyInstaller --noconfirm Trad2Simp.spec` | Produces `dist/Trad2Simp.exe` |

### Gotchas

- Do **not** expect `python -m trad2simp` or `test_all.py` to pass on non-Windows Cloud Agent VMs: `trad2simp/win32.py` loads `ctypes.WinDLL('user32')` at import time, and `trad2simp/__init__.py` imports hotkeys/win32 eagerly.
- Standard commands and build steps are documented in `README.md`. Lint is not separately configured (no ruff/flake8/eslint); rely on `test_all.py` + CI.
- Runtime user data lives under `%APPDATA%\Trad2Simp` (`config.json`, `log.txt`) — never commit those. Logs must not include selected text (lengths/status only).
