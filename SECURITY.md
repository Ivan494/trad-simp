# Security Policy

## Scope

Trad2Simp is a local Windows utility. It does not dial home, collect telemetry, or require accounts.

## Reporting

If you find a vulnerability (for example unexpected network access, logging of clipboard contents, or privilege issues), please open a GitHub issue or contact the maintainer via GitHub.

## Notes for reviewers

- The app reads/writes the clipboard only to convert the current selection and restore prior clipboard text.
- Global hotkeys use `RegisterHotKey` (not a low-level keyboard hook). Key injection uses `SendInput` for copy/paste.
- Logs under `%APPDATA%\Trad2Simp\log.txt` record status and lengths, not selected text.
