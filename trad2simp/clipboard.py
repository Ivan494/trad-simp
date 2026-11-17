"""In-memory, format-aware clipboard snapshots with conditional restoration."""

from contextlib import contextmanager
import ctypes
import time

from trad2simp import win32 as w
from trad2simp.selection import Skipped

u, k = w.user32, w.kernel32
gdi = ctypes.WinDLL('gdi32', use_last_error=True)
u.EnumClipboardFormats.argtypes = [ctypes.c_uint]
u.EnumClipboardFormats.restype = ctypes.c_uint
u.GetClipboardFormatNameW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_int]
u.GetClipboardFormatNameW.restype = ctypes.c_int
u.GetClipboardOwner.restype = ctypes.c_void_p
u.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
u.RegisterClipboardFormatW.restype = ctypes.c_uint
u.CopyImage.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
u.CopyImage.restype = ctypes.c_void_p
k.GlobalSize.argtypes = [ctypes.c_void_p]
k.GlobalSize.restype = ctypes.c_size_t
gdi.DeleteObject.argtypes = [ctypes.c_void_p]
gdi.DeleteObject.restype = ctypes.c_int

MEMORY_FORMATS = {1, 7, 8, 13, 15, 16, 17}  # text, OEM, DIB, Unicode, files, locale, DIBV5
REGISTERED_FORMATS = {'HTML Format', 'Rich Text Format', 'Rich Text Format Without Objects',
                      'PNG', 'image/png', 'CanIncludeInClipboardHistory',
                      'CanUploadToCloudClipboard', 'ExcludeClipboardContentFromMonitorProcessing'}
MAX_BYTES = 64 * 1024 * 1024


def allocate(data):
    handle = k.GlobalAlloc(w.GMEM_MOVEABLE, max(1, len(data)))
    if not handle:
        raise OSError('Clipboard allocation failed')
    ptr = k.GlobalLock(handle)
    if not ptr:
        k.GlobalFree(handle)
        raise OSError('Clipboard lock failed')
    try:
        ctypes.memmove(ptr, data, len(data))
    finally:
        k.GlobalUnlock(handle)
    return handle


class Clipboard:
    def __init__(self):
        self.hwnd = u.CreateWindowExW(0, 'STATIC', 'Trad2SimpClipboard', 0,
                                      0, 0, 0, 0, w.HWND_MESSAGE, None, None, None)
        if not self.hwnd:
            raise Skipped('无法准备剪贴板，已取消转换')
        self.entries = []
        self.sequence = None
        self.last_write_sequence = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for fmt, data in self.entries:
            if fmt == 2:
                gdi.DeleteObject(data)
        self.entries.clear()
        u.DestroyWindow(self.hwnd)

    @contextmanager
    def opened(self):
        for attempt in range(6):
            if u.OpenClipboard(self.hwnd):
                break
            time.sleep(0.03)
        else:
            raise Skipped('剪贴板正忙，请稍后重试')
        try:
            yield
        finally:
            u.CloseClipboard()

    def snapshot(self):
        with self.opened():
            total, fmt = 0, 0
            while True:
                ctypes.set_last_error(0)
                fmt = u.EnumClipboardFormats(fmt)
                if not fmt:
                    if w.last_error():
                        raise Skipped('无法保存剪贴板，已跳过转换')
                    break
                if fmt not in MEMORY_FORMATS and fmt != 2:
                    name = ctypes.create_unicode_buffer(256)
                    u.GetClipboardFormatNameW(fmt, name, len(name))
                    if name.value not in REGISTERED_FORMATS:
                        raise Skipped('剪贴板含无法安全还原的格式，已跳过转换')
                handle = u.GetClipboardData(fmt)
                if not handle:
                    raise Skipped('无法保存剪贴板，已跳过转换')
                if fmt == 2:  # CF_BITMAP is a GDI object, never GlobalLock it.
                    data = u.CopyImage(handle, 0, 0, 0, 0x2000)
                    if not data:
                        raise Skipped('无法保存剪贴板图片，已跳过转换')
                else:
                    size = k.GlobalSize(handle)
                    total += size
                    if not size or total > MAX_BYTES:
                        raise Skipped('剪贴板数据无法安全保存，已跳过转换')
                    ptr = k.GlobalLock(handle)
                    if not ptr:
                        raise Skipped('无法保存剪贴板，已跳过转换')
                    try:
                        data = ctypes.string_at(ptr, size)
                    finally:
                        k.GlobalUnlock(handle)
                self.entries.append((fmt, data))
            self.sequence = w.clipboard_sequence()
            if self.sequence is None:
                raise Skipped('无法确认剪贴板状态，已跳过转换')

    def owner_matches(self, target):
        owner = u.GetClipboardOwner()
        if not owner:
            return False
        a, b = ctypes.c_uint(), ctypes.c_uint()
        u.GetWindowThreadProcessId(owner, ctypes.byref(a))
        u.GetWindowThreadProcessId(target, ctypes.byref(b))
        return a.value != 0 and a.value == b.value

    def read_text(self, expected):
        with self.opened():
            if w.clipboard_sequence() != expected:
                raise Skipped('剪贴板已改变，已取消转换')
            handle = u.GetClipboardData(w.CF_UNICODETEXT)
            if not handle:
                return ''
            size = k.GlobalSize(handle)
            if not size or size > MAX_BYTES:
                raise Skipped('选区过大，已取消转换')
            ptr = k.GlobalLock(handle)
            if not ptr:
                raise Skipped('无法读取选中文字')
            try:
                return ctypes.string_at(ptr, size).decode('utf-16-le').split('\0', 1)[0]
            finally:
                k.GlobalUnlock(handle)

    def _replace(self, entries, expected):
        # Prepare every handle before EmptyClipboard; ownership transfers only
        # after SetClipboardData succeeds. Keep original snapshots for retry.
        handles = []
        try:
            for fmt, data in entries:
                handle = u.CopyImage(data, 0, 0, 0, 0x2000) if fmt == 2 else allocate(data)
                if not handle:
                    raise OSError('Clipboard allocation failed')
                handles.append([fmt, handle])
            cleared = False
            try:
                with self.opened():
                    if w.clipboard_sequence() != expected:
                        return None
                    if not u.EmptyClipboard():
                        raise OSError('Clipboard clear failed')
                    cleared = True
                    for entry in handles:
                        fmt, handle = entry
                        if not u.SetClipboardData(fmt, handle):
                            raise OSError('Clipboard write failed')
                        entry[1] = None
            finally:
                # Windows may synthesize formats on CloseClipboard, advancing
                # the sequence. Read it AFTER close, and verify our ownership.
                if cleared and u.GetClipboardOwner() == self.hwnd:
                    self.last_write_sequence = w.clipboard_sequence()
            return self.last_write_sequence if u.GetClipboardOwner() == self.hwnd else None
        finally:
            for fmt, handle in handles:
                if handle:
                    (gdi.DeleteObject if fmt == 2 else k.GlobalFree)(handle)

    def write_text(self, text, expected):
        entries = [(w.CF_UNICODETEXT, text.encode('utf-16-le') + b'\0\0')]
        for name in ('CanIncludeInClipboardHistory', 'CanUploadToCloudClipboard'):
            fmt = u.RegisterClipboardFormatW(name)
            if not fmt:
                raise Skipped('无法准备剪贴板保护，已取消转换')
            entries.append((fmt, b'\0\0\0\0'))
        sequence = self._replace(entries, expected)
        if sequence is None:
            raise Skipped('剪贴板已改变，已取消转换')
        return sequence

    def restore(self, expected):
        return self._replace(self.entries, expected) is not None
