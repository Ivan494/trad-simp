# Security and privacy

The latest stable GitHub release is supported. Report vulnerabilities through a private GitHub security advisory when available. Do not post selected text, clipboard contents, credentials, personal logs, or unpatched exploit details in public issues.

The desktop app is offline and stores only settings and bounded operational logs locally. It registers a global hotkey and accesses selected text only when triggered. Conversion mode is user-controlled. The app does not read or write Windows startup registration.

Supported single-line Windows Edit controls use direct replacement. The compatibility backend briefly uses the clipboard, preserving supported formats in memory and restoring them conditionally. Unknown formats are rejected before copying. This cannot erase Windows clipboard history or copies retained by other software. Focus and clipboard checks reduce accidental replacement but cannot make arbitrary third-party apps transactional.

Release checks inspect source/history and packaged Python code for common credential and personal-path patterns. Such checks reduce risk; they are not a guarantee that no vulnerability exists. Dependencies and actions are pinned. Build provenance and checksums are published with each release. Releases are currently unsigned.
