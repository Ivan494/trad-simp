"""Real Win32 clipboard tests in a PRIVATE window station, never the user's."""
import ctypes
from pathlib import Path
import struct
import sys
import uuid
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

u = ctypes.WinDLL('user32', use_last_error=True)
u.CreateWindowStationW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
u.CreateWindowStationW.restype = ctypes.c_void_p
u.GetProcessWindowStation.restype = ctypes.c_void_p
u.SetProcessWindowStation.argtypes = [ctypes.c_void_p]
u.CloseWindowStation.argtypes = [ctypes.c_void_p]
u.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p]
u.CreateDesktopW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
u.CreateDesktopW.restype = ctypes.c_void_p
u.SetThreadDesktop.argtypes = [ctypes.c_void_p]
u.GetThreadDesktop.argtypes = [ctypes.c_uint]
u.GetThreadDesktop.restype = ctypes.c_void_p
u.CloseDesktop.argtypes = [ctypes.c_void_p]
k = ctypes.WinDLL('kernel32')
original = u.GetProcessWindowStation()
original_desktop = u.GetThreadDesktop(k.GetCurrentThreadId())
station = u.CreateWindowStationW(None, 0, 0x37f, None)
def station_name(handle):
    buffer = ctypes.create_unicode_buffer(256)
    if not u.GetUserObjectInformationW(handle, 2, buffer, ctypes.sizeof(buffer), None):
        raise RuntimeError('Cannot identify clipboard station')
    return buffer.value
if not station or station_name(station) == station_name(original):
    raise RuntimeError('No isolated station available; no clipboard accessed')
if not u.SetProcessWindowStation(station):
    raise RuntimeError('Cannot switch station; no clipboard accessed')
desktop = u.CreateDesktopW('Trad2SimpTest' + uuid.uuid4().hex, None, None, 0, 0x1ff, None)
if not desktop or not u.SetThreadDesktop(desktop):
    raise RuntimeError('Cannot switch test desktop; no clipboard accessed')

try:
    from trad2simp import clipboard as cb, win32 as w
    from trad2simp.selection import Skipped
    with cb.Clipboard() as clip:
        clip._replace([], w.clipboard_sequence())
        clip.snapshot()
        assert clip.entries == []
        changed = clip.write_text('synthetic', clip.sequence)
        assert clip.read_text(changed) == 'synthetic'
        assert clip.restore(changed)
        clip.snapshot()
        assert clip.entries == []

    html = u.RegisterClipboardFormatW('HTML Format')
    rtf = u.RegisterClipboardFormatW('Rich Text Format')
    png = u.RegisterClipboardFormatW('PNG')
    rfh = u.RegisterClipboardFormatW('Chromium internal source RFH token')
    source_url = u.RegisterClipboardFormatW('Chromium internal source URL')
    custom_mime = u.RegisterClipboardFormatW('Chromium Web Custom MIME Data Format')
    web_mime = u.RegisterClipboardFormatW('Web Custom MIME Data Format')
    # DIB 1x1, file list DROPFILES (UTF-16), text, HTML and RTF all use HGLOBAL.
    dib = struct.pack('<IiiHHIIiiII', 40, 1, 1, 1, 24, 0, 4, 0, 0, 0, 0) + b'\0\0\xff\0'
    drop = struct.pack('<IiiII', 20, 0, 0, 0, 1) + 'C:\\Synthetic\\sample.txt\0\0'.encode('utf-16-le')
    fixture = [(13, '原始😀\0'.encode('utf-16-le')), (8, dib), (15, drop),
               (html, b'<p>synthetic</p>\0'), (rtf, b'{\\rtf1 synthetic}\0'),
               (png, b'synthetic PNG format payload'),
               (rfh, b'synthetic frame token'), (source_url, b'https://example.test/\0'),
               (custom_mime, b'synthetic custom MIME data'), (web_mime, b'synthetic web MIME data')]
    with cb.Clipboard() as writer:
        writer._replace(fixture, w.clipboard_sequence())
    with cb.Clipboard() as snapshot:
        snapshot.snapshot()
        before = dict(snapshot.entries)
        assert set(dict(fixture)).issubset(before)
        sequence = snapshot.write_text('converted', snapshot.sequence)
        assert snapshot.restore(sequence)
    with cb.Clipboard() as check:
        check.snapshot()
        after = dict(check.entries)
        assert set(after) == set(before)
        assert {f: d for f, d in after.items() if f != 2} == {f: d for f, d in before.items() if f != 2}
        # A newer clipboard owner must win over old restoration.
        sequence = check.write_text('operation', check.sequence)
        with cb.Clipboard() as other:
            newer = other.write_text('new copy', sequence)
            assert not check.restore(sequence)
            assert other.read_text(newer) == 'new copy'

    unknown = u.RegisterClipboardFormatW('Trad2Simp synthetic unsupported format')
    with cb.Clipboard() as writer:
        writer._replace([(13, 'synthetic\0'.encode('utf-16-le')),
                         (unknown, b'synthetic\0')], w.clipboard_sequence())
    with cb.Clipboard() as snapshot:
        # Validate the whole format list before triggering delayed rendering of
        # even a supported format. Unsupported clipboard data must be left alone.
        with patch.object(cb.u, 'GetClipboardData') as get_data:
            try:
                snapshot.snapshot()
            except Skipped:
                pass
            else:
                raise AssertionError('Unknown format was not rejected')
            get_data.assert_not_called()

    cb.gdi.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
    cb.gdi.CreateBitmap.restype = ctypes.c_void_p
    bitmap = cb.gdi.CreateBitmap(1, 1, 1, 32, ctypes.create_string_buffer(b'\0\0\xff\0'))
    assert bitmap
    try:
        with cb.Clipboard() as writer:
            writer._replace([(2, bitmap)], w.clipboard_sequence())
        with cb.Clipboard() as snapshot:
            snapshot.snapshot()
            assert any(fmt == 2 for fmt, _ in snapshot.entries)
            sequence = snapshot.write_text('converted', snapshot.sequence)
            assert snapshot.restore(sequence)
    finally:
        cb.gdi.DeleteObject(bitmap)
    # Exercise real native copy/paste and undo without the interactive clipboard.
    from trad2simp import selection as s
    rich_edit = ctypes.WinDLL('msftedit')
    hwnd = u.CreateWindowExW(0, 'RICHEDIT50W', '繁體\r\n測試😀', 4,
                             0, 0, 200, 100, None, None, None, None)
    assert hwnd
    try:
        with cb.Clipboard() as writer:
            writer._replace([(13, 'saved\0'.encode('utf-16-le'))], w.clipboard_sequence())
        s.message(hwnd, 0xB1, 0, -1)
        with patch.object(s, 'capture_target', return_value=(hwnd, hwnd)), \
                patch.object(w, 'try_wm_copy', side_effect=lambda: (s.message(hwnd, 0x301), True)[1]), \
                patch.object(w, 'try_wm_paste', side_effect=lambda: (s.message(hwnd, 0x302), True)[1]):
            s.clipboard_convert((hwnd, hwnd), 't2s', lambda: False)
        text = ctypes.create_unicode_buffer(100)
        s.message(hwnd, 0xD, 100, ctypes.addressof(text))
        assert text.value.replace('\r\n', '\n').replace('\r', '\n') == '繁体\n测试😀'
        s.message(hwnd, 0xC7)
        s.message(hwnd, 0xD, 100, ctypes.addressof(text))
        assert text.value.replace('\r\n', '\n').replace('\r', '\n') == '繁體\n測試😀'
        with cb.Clipboard() as reader:
            assert reader.read_text(w.clipboard_sequence()) == 'saved'
    finally:
        u.DestroyWindow(hwnd)
    print('Isolated clipboard: empty, text, DIB/bitmap, files, HTML/RTF, conflicts, unknown formats PASS')
finally:
    u.SetThreadDesktop(original_desktop)
    u.CloseDesktop(desktop)
    u.SetProcessWindowStation(original)
    u.CloseWindowStation(station)
