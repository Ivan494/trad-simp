"""Win32 bindings: SendInput, clipboard, focus, and hotkey side-effect suppression."""

import ctypes
import os
import sys
import time

# WinDLL(..., use_last_error=True) snapshots GetLastError immediately after
# each call. windll.kernel32.GetLastError() is not reliable: ctypes may
# issue other APIs first and clear ERROR_ALREADY_EXISTS, which lets a
# second instance skip the mutex and stay alive.
_user32 = ctypes.WinDLL('user32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
try:
    _imm32 = ctypes.WinDLL('imm32', use_last_error=True)
except OSError:
    _imm32 = None

user32 = _user32
kernel32 = _kernel32


def last_error():
    return ctypes.get_last_error()


def clear_stale_tcl_env():
    """Source runs only: a stale TCL_LIBRARY/TK_LIBRARY left by another Tcl
    install makes tkinter boot the wrong Tcl data and die with
    `invalid command name "tcl_findLibrary"` at Tk(). Frozen builds must
    NOT clear these — the PyInstaller rthook points them at bundled Tcl."""
    if getattr(sys, 'frozen', False):
        return
    for var in ('TCL_LIBRARY', 'TK_LIBRARY', 'TCL_TCLSH', 'TCL_PKG_PATH', 'TK_PKG_PATH'):
        os.environ.pop(var, None)


# --- prototypes that must be pinned so HWND/pointers are not truncated on x64 ---

_kernel32.GetLastError.restype = ctypes.c_uint
_kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype = ctypes.c_int
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.restype = ctypes.c_void_p
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateEventW.restype = ctypes.c_void_p
_kernel32.SetEvent.argtypes = [ctypes.c_void_p]
_kernel32.SetEvent.restype = ctypes.c_int
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.restype = ctypes.c_int
_kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_kernel32.WaitForSingleObject.restype = ctypes.c_uint32

# INPUT union must include MOUSEINPUT so sizeof(INPUT) is 40 on x64.
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong),
        ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.c_void_p),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', ctypes.c_ushort), ('wScan', ctypes.c_ushort), ('dwFlags', ctypes.c_ulong),
        ('time', ctypes.c_ulong), ('dwExtraInfo', ctypes.c_void_p),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', ctypes.c_ulong), ('wParamL', ctypes.c_ushort), ('wParamH', ctypes.c_ushort)]


class INPUTUNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('union', INPUTUNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MAPVK_VK_TO_VSC = 0
MAPVK_VSC_TO_VK = 1

_user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
_user32.SendInput.restype = ctypes.c_uint
_user32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
_user32.MapVirtualKeyW.restype = ctypes.c_uint
_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_user32.GetAsyncKeyState.restype = ctypes.c_short
_user32.GetForegroundWindow.restype = ctypes.c_void_p
_user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.GetWindowThreadProcessId.restype = ctypes.c_uint
_user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_user32.GetClipboardSequenceNumber.restype = ctypes.c_uint
_user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
_user32.IsClipboardFormatAvailable.restype = ctypes.c_int
_user32.OpenClipboard.argtypes = [ctypes.c_void_p]
_user32.OpenClipboard.restype = ctypes.c_int
_user32.CloseClipboard.restype = ctypes.c_int
_user32.EmptyClipboard.restype = ctypes.c_int
_user32.GetClipboardData.argtypes = [ctypes.c_uint]
_user32.GetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SendMessageTimeoutW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
    ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_size_t),
]
_user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t

# RegisterHotKey / message-only window
_user32.RegisterClassW.restype = ctypes.c_ushort
_user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
_user32.CreateWindowExW.restype = ctypes.c_void_p
_user32.DestroyWindow.argtypes = [ctypes.c_void_p]
_user32.DestroyWindow.restype = ctypes.c_int
_user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.GetMessageW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
_user32.GetMessageW.restype = ctypes.c_int
_user32.TranslateMessage.argtypes = [ctypes.c_void_p]
_user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
_user32.DispatchMessageW.restype = ctypes.c_ssize_t
_user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.PostMessageW.restype = ctypes.c_int
_user32.PostQuitMessage.argtypes = [ctypes.c_int]
_user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
_user32.RegisterHotKey.restype = ctypes.c_int
_user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.UnregisterHotKey.restype = ctypes.c_int
_user32.UnregisterClassW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
_user32.UnregisterClassW.restype = ctypes.c_int

if _imm32 is not None:
    _imm32.ImmGetContext.argtypes = [ctypes.c_void_p]
    _imm32.ImmGetContext.restype = ctypes.c_void_p
    _imm32.ImmNotifyIME.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    _imm32.ImmNotifyIME.restype = ctypes.c_int
    _imm32.ImmReleaseContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _imm32.ImmReleaseContext.restype = ctypes.c_int


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('flags', ctypes.c_uint),
        ('hwndActive', ctypes.c_void_p),
        ('hwndFocus', ctypes.c_void_p),
        ('hwndCapture', ctypes.c_void_p),
        ('hwndMenuOwner', ctypes.c_void_p),
        ('hwndMoveSize', ctypes.c_void_p),
        ('hwndCaret', ctypes.c_void_p),
        ('rcCaretLeft', ctypes.c_long),
        ('rcCaretTop', ctypes.c_long),
        ('rcCaretRight', ctypes.c_long),
        ('rcCaretBottom', ctypes.c_long),
    ]


_user32.GetGUIThreadInfo.argtypes = [ctypes.c_uint, ctypes.POINTER(GUITHREADINFO)]
_user32.GetGUIThreadInfo.restype = ctypes.c_int

# Virtual keys
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_INSERT = 0x2D
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1
VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
VK_LMENU, VK_RMENU = 0xA4, 0xA5
# Undefined VK used by AutoHotkey-style Alt-menu suppression.
VK_DUMMY = 0xE8
# Scan code of the physical grave/tilde key (left of 1 on standard boards).
SCAN_GRAVE = 0x29

EXTENDED_VKS = {
    VK_INSERT, VK_RCONTROL, VK_RMENU, VK_LWIN, VK_RWIN,
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2E,  # pgup/pgdn/end/home/arrows/del
}

MODIFIER_VKS = (
    VK_LSHIFT, VK_RSHIFT, VK_SHIFT,
    VK_LCONTROL, VK_RCONTROL, VK_CONTROL,
    VK_LMENU, VK_RMENU, VK_MENU,
    VK_LWIN, VK_RWIN,
)

WM_CANCELMODE = 0x001F
WM_COPY = 0x0301
WM_PASTE = 0x0302
SMTO_ABORTIFHUNG = 0x0002
CF_UNICODETEXT = 13
CF_TEXT = 1
GMEM_MOVEABLE = 0x0002
NI_COMPOSITIONSTR = 0x15
CPS_CANCEL = 0x4

# ((HWND)-3) as a pointer-sized value — plain -3 breaks CreateWindowEx on x64.
HWND_MESSAGE = ctypes.c_void_p(-3).value

WAIT_OBJECT_0 = 0
WAIT_ABANDONED = 0x80
WAIT_TIMEOUT = 0x102


def _fill_key(event, vk, up=False):
    scan = _user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_KEYUP if up else 0
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    event.type = INPUT_KEYBOARD
    event.union.ki = KEYBDINPUT(vk, scan, flags, 0, None)


def send_vk_chord(vks):
    """Press vks in order, then release in reverse order."""
    if not vks:
        return False
    n = len(vks) * 2
    events = (INPUT * n)()
    i = 0
    for vk in vks:
        _fill_key(events[i], vk, up=False)
        i += 1
    for vk in reversed(vks):
        _fill_key(events[i], vk, up=True)
        i += 1
    return _user32.SendInput(n, events, ctypes.sizeof(INPUT)) == n


def send_dummy_key():
    """Tap an undefined VK so a still-held Alt is not seen as a bare Alt (menu)."""
    events = (INPUT * 2)()
    _fill_key(events[0], VK_DUMMY, up=False)
    _fill_key(events[1], VK_DUMMY, up=True)
    return _user32.SendInput(2, events, ctypes.sizeof(INPUT)) == 2


def release_modifiers():
    """Force key-up on all modifiers so a still-held hotkey chord (esp. Alt)
    does not combine with the injected Ctrl+C/V."""
    n = len(MODIFIER_VKS)
    events = (INPUT * n)()
    for i, vk in enumerate(MODIFIER_VKS):
        _fill_key(events[i], vk, up=True)
    return _user32.SendInput(n, events, ctypes.sizeof(INPUT)) == n


def key_is_down(vk):
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def wait_modifiers_up(timeout=0.12):
    """Wait until the user has released modifier keys from the hotkey chord.
    Falls back to synthetic key-ups if they are still held past timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(key_is_down(vk) for vk in MODIFIER_VKS):
            return True
        time.sleep(0.008)
    release_modifiers()
    time.sleep(0.02)
    return not any(key_is_down(vk) for vk in MODIFIER_VKS)


def inject_named_combo(combo):
    """Inject a chord like 'ctrl+c' or 'ctrl+insert' via SendInput."""
    aliases = {
        'control': 'ctrl', 'left ctrl': 'ctrl', 'right ctrl': 'ctrl',
        'left alt': 'alt', 'right alt': 'alt',
        'left shift': 'shift', 'right shift': 'shift',
    }
    parts = [aliases.get(p.strip().lower(), p.strip().lower())
             for p in combo.split('+') if p.strip()]
    vks = []
    for p in parts:
        if p == 'ctrl':
            vks.append(VK_CONTROL)
        elif p == 'alt':
            vks.append(VK_MENU)
        elif p == 'shift':
            vks.append(VK_SHIFT)
        elif p == 'insert':
            vks.append(VK_INSERT)
        elif len(p) == 1 and 'a' <= p <= 'z':
            vks.append(ord(p.upper()))
        else:
            raise ValueError(f'cannot inject key: {p}')
    return send_vk_chord(vks)


# --- clipboard ---

def clipboard_sequence():
    try:
        return int(_user32.GetClipboardSequenceNumber())
    except Exception:
        return None


def clipboard_has_text():
    try:
        return bool(
            _user32.IsClipboardFormatAvailable(CF_UNICODETEXT)
            or _user32.IsClipboardFormatAvailable(CF_TEXT)
        )
    except Exception:
        return True


def read_clipboard():
    if not _user32.OpenClipboard(None):
        raise OSError(f'OpenClipboard failed ({last_error()})')
    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ''
        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            return ''
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


def write_clipboard(text):
    payload = (text or '').encode('utf-16-le') + b'\x00\x00'
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        raise OSError('GlobalAlloc failed')
    ptr = _kernel32.GlobalLock(handle)
    if not ptr:
        _kernel32.GlobalFree(handle)
        raise OSError('GlobalLock failed')
    ctypes.memmove(ptr, payload, len(payload))
    _kernel32.GlobalUnlock(handle)
    if not _user32.OpenClipboard(None):
        _kernel32.GlobalFree(handle)
        raise OSError(f'OpenClipboard failed ({last_error()})')
    try:
        _user32.EmptyClipboard()
        if not _user32.SetClipboardData(CF_UNICODETEXT, handle):
            _kernel32.GlobalFree(handle)
            raise OSError(f'SetClipboardData failed ({last_error()})')
        handle = None  # system owns it now
    finally:
        _user32.CloseClipboard()


# --- focus / messages ---

def focused_hwnd():
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    tid = _user32.GetWindowThreadProcessId(hwnd, None)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if _user32.GetGUIThreadInfo(tid, ctypes.byref(info)) and info.hwndFocus:
        return info.hwndFocus
    return hwnd


def window_class_name(hwnd):
    if not hwnd:
        return ''
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def send_message_timeout(hwnd, msg, wparam=0, lparam=0, timeout_ms=120):
    if not hwnd:
        return False
    result = ctypes.c_size_t()
    ret = _user32.SendMessageTimeoutW(
        hwnd, msg, wparam, lparam, SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result))
    return bool(ret)


def cancel_ime(hwnd):
    if not hwnd or _imm32 is None:
        return
    himc = _imm32.ImmGetContext(hwnd)
    if not himc:
        return
    try:
        _imm32.ImmNotifyIME(himc, NI_COMPOSITIONSTR, CPS_CANCEL, 0)
    finally:
        _imm32.ImmReleaseContext(hwnd, himc)


def try_wm_copy():
    hwnd = focused_hwnd()
    if not hwnd:
        return False
    cancel_ime(hwnd)
    return send_message_timeout(hwnd, WM_COPY, timeout_ms=120)


def try_wm_paste():
    hwnd = focused_hwnd()
    if not hwnd:
        return False
    cls = window_class_name(hwnd).lower()
    if 'edit' not in cls and 'text' not in cls:
        return False
    return send_message_timeout(hwnd, WM_PASTE, timeout_ms=120)


def suppress_hotkey_side_effects():
    """Run on the hotkey thread the instant WM_HOTKEY arrives.

    RegisterHotKey swallows the non-Alt key, so the target app often sees a
    bare Alt down/up and opens the menu bar. The first Ctrl+C then goes to
    the menu (clipboard never changes) and the user has to press again.
    A dummy VK while Alt is still down, plus WM_CANCELMODE, prevents that.
    """
    send_dummy_key()
    hwnd = focused_hwnd()
    if hwnd:
        send_message_timeout(hwnd, WM_CANCELMODE, timeout_ms=50)
        cancel_ime(hwnd)
