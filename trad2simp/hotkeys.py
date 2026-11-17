"""Hotkey strings, RegisterHotKey pump, and combo recording."""

import ctypes
import os
import threading
import time

from trad2simp.config import log
from trad2simp.win32 import (
    HWND_MESSAGE, SCAN_GRAVE, VK_CONTROL, VK_ESCAPE, VK_LCONTROL, VK_LMENU,
    VK_LSHIFT, VK_LWIN, VK_MENU, VK_RCONTROL, VK_RMENU, VK_RSHIFT, VK_RWIN,
    VK_SHIFT, kernel32, key_is_down, last_error, suppress_hotkey_side_effects,
    user32,
)

# Win32 RegisterHotKey modifiers (stable; not a low-level keyboard hook).
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
HOTKEY_MSG_SET = 0x8001
HOTKEY_MSG_CLEAR = 0x8002
HOTKEY_MSG_STOP = 0x8003
HOTKEY_ID = 1

# Alt+` is free on stock Windows / Greenshot (which uses Alt+PrintScreen).
DEFAULT_HOTKEY = 'alt+`'

_OEM_VK = {
    '`': 0xC0, 'grave': 0xC0, 'tilde': 0xC0,
    '-': 0xBD, '=': 0xBB, '[': 0xDB, ']': 0xDD, '\\': 0xDC,
    ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF,
}
_NAMED_VK = {
    'space': 0x20, 'tab': 0x09, 'enter': 0x0D, 'return': 0x0D,
    'escape': 0x1B, 'esc': 0x1B, 'backspace': 0x08, 'delete': 0x2E,
    'insert': 0x2D, 'home': 0x24, 'end': 0x23, 'page up': 0x21,
    'page down': 0x22, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
}

MODIFIER_ORDER = {'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3}
MODIFIER_ALIASES = {
    'left ctrl': 'ctrl',
    'right ctrl': 'ctrl',
    'left alt': 'alt',
    'right alt': 'alt',
    'left shift': 'shift',
    'right shift': 'shift',
    'left windows': 'win',
    'right windows': 'win',
    'windows': 'win',
    'control': 'ctrl', 'return': 'enter', 'escape': 'esc',
    'del': 'delete', 'ins': 'insert',
}
STANDALONE_KEYS = {f'f{i}' for i in range(1, 25)}
RESERVED_COMBOS = {
    'alt+tab', 'alt+f4', 'ctrl+esc', 'ctrl+alt+del', 'ctrl+alt+delete', 'ctrl+shift+esc',
    # the app itself injects these during conversion; using them as the hotkey
    # would suppress the user's own copy/paste and deadlock the conversion loop
    'ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+insert', 'shift+insert', 'shift+delete',
}

_MODIFIER_VK_TO_NAME = {
    VK_CONTROL: 'ctrl', VK_LCONTROL: 'ctrl', VK_RCONTROL: 'ctrl',
    VK_MENU: 'alt', VK_LMENU: 'alt', VK_RMENU: 'alt',
    VK_SHIFT: 'shift', VK_LSHIFT: 'shift', VK_RSHIFT: 'shift',
    VK_LWIN: 'win', VK_RWIN: 'win',
}

_VK_TO_NAME = {
    0x20: 'space', 0x09: 'tab', 0x0D: 'enter', 0x08: 'backspace', 0x2E: 'delete',
    0x2D: 'insert', 0x24: 'home', 0x23: 'end', 0x21: 'page up', 0x22: 'page down',
    0x26: 'up', 0x28: 'down', 0x25: 'left', 0x27: 'right',
    0xC0: '`', 0xBD: '-', 0xBB: '=', 0xDB: '[', 0xDD: ']', 0xDC: '\\',
    0xBA: ';', 0xDE: "'", 0xBC: ',', 0xBE: '.', 0xBF: '/',
}


def key_to_vk(key):
    """Map a canonical key name to a Win32 virtual-key code, or None."""
    if not key:
        return None
    key = key.lower().strip()
    if key in ('`', 'grave', 'tilde'):
        # Layout-aware: scan 0x29 is the physical `~ key on standard boards.
        mapped = user32.MapVirtualKeyW(SCAN_GRAVE, 1)  # MAPVK_VSC_TO_VK
        return mapped or 0xC0
    if len(key) == 1:
        if 'a' <= key <= 'z':
            return ord(key.upper())
        if '0' <= key <= '9':
            return ord(key)
        return _OEM_VK.get(key)
    if key.startswith('f') and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return 0x70 + n - 1
    return _NAMED_VK.get(key) or _OEM_VK.get(key)


def vk_to_key_name(vk):
    """Inverse of key_to_vk for recorder output. None if not a usable key."""
    if vk in _MODIFIER_VK_TO_NAME or vk == VK_ESCAPE:
        return None
    if 0x41 <= vk <= 0x5A:
        return chr(vk + 32)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f'f{vk - 0x6F}'
    grave = key_to_vk('`')
    if grave and vk == grave:
        return '`'
    return _VK_TO_NAME.get(vk)


def combo_from_vks(down_vks):
    """Build a canonical combo string from a set of currently-down VKs.

    Returns None if there is no non-modifier key, or 'esc' if Escape is down.
    """
    if VK_ESCAPE in down_vks:
        return 'esc'
    mods = []
    for name in ('ctrl', 'alt', 'shift', 'win'):
        if any(_MODIFIER_VK_TO_NAME.get(vk) == name for vk in down_vks):
            mods.append(name)
    key = None
    for vk in down_vks:
        name = vk_to_key_name(vk)
        if name:
            key = name
            break
    if key is None:
        return None
    return '+'.join(mods + [key])


def hotkey_to_mods_vk(combo):
    """Parse a canonical hotkey string into (RegisterHotKey mods, vk)."""
    parts = [p.strip().lower() for p in combo.split('+') if p.strip()]
    mods = 0
    key = None
    for p in parts:
        p = MODIFIER_ALIASES.get(p, p)
        if p == 'ctrl':
            mods |= MOD_CONTROL
        elif p == 'alt':
            mods |= MOD_ALT
        elif p == 'shift':
            mods |= MOD_SHIFT
        elif p == 'win':
            mods |= MOD_WIN
        else:
            if key is not None:
                raise ValueError('快捷键只能包含一个主键')
            key = p
    if key is None:
        raise ValueError('请包含主键')
    vk = key_to_vk(key)
    if vk is None:
        raise ValueError(f'不支持的按键: {key}')
    return mods, vk


def canonical_hotkey(combo):
    parts = [p.strip().lower() for p in combo.split('+') if p.strip()]
    seen = set()
    out = []
    for part in parts:
        part = MODIFIER_ALIASES.get(part, part)
        if part in seen:
            continue
        seen.add(part)
        out.append(part)
    out.sort(key=lambda p: (MODIFIER_ORDER.get(p, 99), p))
    return '+'.join(out)


def validate_hotkey(combo):
    if not isinstance(combo, str) or not combo.strip():
        raise ValueError('请输入非空快捷键')
    canonical = canonical_hotkey(combo)
    parts = canonical.split('+')
    if not parts:
        raise ValueError('请输入非空快捷键')
    if any(p == 'win' for p in parts):
        raise ValueError('Win 组合键被系统占用，请换一个')
    if any(p in ('print screen', 'printscreen', 'prtsc', 'prt sc') for p in parts):
        raise ValueError('PrintScreen 组合键被系统占用，请换一个')
    mods = [p for p in parts if p in MODIFIER_ORDER]
    if len(parts) == len(mods):
        raise ValueError('请包含主键')
    if not mods and (len(parts) != 1 or parts[0] not in STANDALONE_KEYS):
        raise ValueError('请使用 Ctrl/Alt + 普通键或 F1-F24')
    if canonical in RESERVED_COMBOS:
        raise ValueError('该组合键被系统占用')
    hotkey_to_mods_vk(canonical)
    return canonical


class WinHotkeyPump:
    """System-wide hotkeys via RegisterHotKey on a message-only window.

    Unlike a WH_KEYBOARD_LL hook, RegisterHotKey is delivered through a
    normal message pump and is not silently uninstalled when a callback is
    slow. That was the root cause of "works for a while then dies".
    """

    def __init__(self, on_hotkey, on_pre=None):
        self._on_hotkey = on_hotkey
        self._on_pre = on_pre or suppress_hotkey_side_effects
        self._thread = None
        self._hwnd = None
        self._ready = threading.Event()
        self._start_error = None
        self._lock = threading.Lock()
        self._reg_req = None  # (mods, vk, done_event, result_box)
        self._clear_req = None  # (done_event,)
        self._current = None  # (mods, vk) currently registered
        self._class_name = f'Trad2SimpHotkey_{os.getpid()}_{id(self)}'

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(target=self._thread_main, name='WinHotkeyPump', daemon=True)
        self._thread.start()
        if not self._ready.wait(5.0):
            raise RuntimeError('快捷键线程启动超时')
        if self._start_error:
            raise RuntimeError(self._start_error)

    def register(self, mods, vk, force=False):
        """Register (or re-register) the hotkey.

        Returns True when RegisterHotKey was called, False when the same
        combo is already tracked and force is False (no-op).
        """
        self.start()
        with self._lock:
            if not force and self._current == (mods, vk) and self._hwnd:
                return False
        done = threading.Event()
        result = [None]
        with self._lock:
            self._reg_req = (mods, vk, done, result)
        if not user32.PostMessageW(self._hwnd, HOTKEY_MSG_SET, 0, 0):
            raise RuntimeError('无法向快捷键线程投递注册消息')
        if not done.wait(3.0):
            raise RuntimeError('快捷键注册超时')
        if result[0] is not True:
            raise RuntimeError(result[0] or '快捷键注册失败')
        return True

    def unregister(self):
        if not self._hwnd:
            self._current = None
            return
        done = threading.Event()
        with self._lock:
            self._clear_req = (done,)
        if user32.PostMessageW(self._hwnd, HOTKEY_MSG_CLEAR, 0, 0):
            done.wait(2.0)
        self._current = None

    def stop(self):
        hwnd = self._hwnd
        if hwnd:
            user32.PostMessageW(hwnd, HOTKEY_MSG_STOP, 0, 0)
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None
        self._hwnd = None
        self._current = None

    def _thread_main(self):
        try:
            self._run_pump()
        except Exception as ex:
            self._start_error = str(ex)
            self._ready.set()
            log(f'hotkey pump crashed: {ex}')

    def _run_pump(self):
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_ssize_t)

        @WNDPROC
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_HOTKEY and int(wparam) == HOTKEY_ID:
                # Must run before returning to the message loop: dummy key
                # has to land while physical Alt is still down.
                if self._on_pre:
                    try:
                        self._on_pre()
                    except Exception as ex:
                        log(f'hotkey pre-handler error: {ex}')
                try:
                    self._on_hotkey()
                except Exception as ex:
                    log(f'hotkey callback error: {ex}')
                return 0
            if msg == HOTKEY_MSG_SET:
                self._apply_register()
                return 0
            if msg == HOTKEY_MSG_CLEAR:
                self._apply_clear()
                return 0
            if msg == HOTKEY_MSG_STOP:
                user32.UnregisterHotKey(hwnd, HOTKEY_ID)
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        # Keep a reference so the callback is not GC'd.
        self._wnd_proc = wnd_proc

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ('style', ctypes.c_uint),
                ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', ctypes.c_void_p),
                ('hIcon', ctypes.c_void_p),
                ('hCursor', ctypes.c_void_p),
                ('hbrBackground', ctypes.c_void_p),
                ('lpszMenuName', ctypes.c_wchar_p),
                ('lpszClassName', ctypes.c_wchar_p),
            ]

        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = wnd_proc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = last_error()
            if err != 1410:  # class already exists
                self._start_error = f'RegisterClassW failed ({err})'
                self._ready.set()
                return

        hwnd = user32.CreateWindowExW(
            0, self._class_name, 'Trad2SimpHotkey', 0,
            0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
        if not hwnd:
            self._start_error = f'CreateWindowExW failed ({last_error()})'
            self._ready.set()
            return
        self._hwnd = hwnd
        self._ready.set()

        class MSG(ctypes.Structure):
            _fields_ = [
                ('hwnd', ctypes.c_void_p),
                ('message', ctypes.c_uint),
                ('wParam', ctypes.c_size_t),
                ('lParam', ctypes.c_ssize_t),
                ('time', ctypes.c_uint),
                ('pt_x', ctypes.c_long),
                ('pt_y', ctypes.c_long),
            ]

        msg = MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            user32.UnregisterHotKey(hwnd, HOTKEY_ID)
        except Exception:
            pass
        user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(self._class_name, hinst)
        self._hwnd = None
        self._current = None

    def _apply_register(self):
        with self._lock:
            req = self._reg_req
            self._reg_req = None
        if not req:
            return
        mods, vk, done, result = req
        try:
            user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
            ok = user32.RegisterHotKey(self._hwnd, HOTKEY_ID, mods | MOD_NOREPEAT, vk)
            if not ok:
                # Some older systems reject MOD_NOREPEAT; retry without it.
                ok = user32.RegisterHotKey(self._hwnd, HOTKEY_ID, mods, vk)
            if ok:
                result[0] = True
                self._current = (mods, vk)
            else:
                result[0] = f'快捷键被占用或无效 (err={last_error()})'
                self._current = None
        except Exception as ex:
            result[0] = str(ex)
            self._current = None
        done.set()

    def _apply_clear(self):
        with self._lock:
            req = self._clear_req
            self._clear_req = None
        try:
            user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
        except Exception:
            pass
        self._current = None
        if req:
            req[0].set()


class HotkeyRecorder:
    """Poll GetAsyncKeyState for a new combo. No WH_KEYBOARD_LL hook."""

    def __init__(self, on_combo, on_cancel, poll=None):
        self._on_combo = on_combo
        self._on_cancel = on_cancel
        self._poll = poll or _snapshot_down_vks
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name='HotkeyRecorder', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        # Ignore keys still down from clicking "记录".
        while not self._stop.is_set():
            if not self._poll():
                break
            time.sleep(0.01)
        prev = set()
        while not self._stop.is_set():
            down = self._poll()
            newly = down - prev
            prev = down
            if newly:
                combo = combo_from_vks(down)
                if combo == 'esc':
                    self._on_cancel()
                    return
                if combo:
                    self._on_combo(combo)
                    return
            time.sleep(0.01)


def _snapshot_down_vks():
    down = set()
    for vk in range(1, 256):
        if key_is_down(vk):
            down.add(vk)
    return down
