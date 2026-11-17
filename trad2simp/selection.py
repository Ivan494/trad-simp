"""Guarded selection conversion; no content is persisted or logged."""

import ctypes
import time

from trad2simp import win32 as w
from trad2simp.convert import convert_text


class Skipped(Exception):
    """A safe, user-facing reason to leave the target unchanged."""


def capture_target():
    return (w.user32.GetForegroundWindow(), w.focused_hwnd())


def require_target(target, cancelled):
    if cancelled() or not all(target) or capture_target() != target:
        raise Skipped('焦点已改变，已取消转换')


def message(hwnd, msg, wp=0, lp=0):
    result = ctypes.c_size_t()
    if not w.user32.SendMessageTimeoutW(hwnd, msg, wp, lp, w.SMTO_ABORTIFHUNG,
                                       250, ctypes.byref(result)):
        raise Skipped('目标窗口未响应，已停止转换')
    return result.value


def direct_selection(target):
    """Only standard Unicode Edit controls use the direct backend.

    RichEdit/custom/browser controls use the clipboard backend; pointer-bearing
    WM_USER messages cannot safely be sent into another process.
    """
    hwnd = target[1]
    if w.window_class_name(hwnd).lower() != 'edit' or not w.user32.IsWindowUnicode(hwnd):
        return None
    style = w.user32.GetWindowLongW(hwnd, -16)
    if style & (0x20 | 0x800):  # ES_PASSWORD | ES_READONLY
        raise Skipped('密码或只读输入框不支持转换')
    if style & 0x4:  # Legacy multiline Edit loses deleted text in EM_REPLACESEL undo.
        return None
    start, end = ctypes.c_uint(), ctypes.c_uint()
    message(hwnd, 0xB0, ctypes.addressof(start), ctypes.addressof(end))  # EM_GETSEL
    length = message(hwnd, 0xE)  # WM_GETTEXTLENGTH
    if length > 1_000_000:
        raise Skipped('文本过长，已跳过转换')
    buf = ctypes.create_unicode_buffer(length + 1)
    message(hwnd, 0xD, length + 1, ctypes.addressof(buf))
    # Windows indices count UTF-16 units, not Python Unicode code points.
    raw = buf.value.encode('utf-16-le')
    selected = raw[start.value * 2:end.value * 2].decode('utf-16-le')
    return start.value, end.value, selected


def convert_selection(mode, cancelled=lambda: False):
    target = capture_target()
    require_target(target, cancelled)
    w.wait_modifiers_up()
    require_target(target, cancelled)
    direct = direct_selection(target)
    if direct is not None:
        start, end, text = direct
        converted = convert_text(text, mode)
        if converted == text:
            return '所选文字无需转换'
        require_target(target, cancelled)
        if direct_selection(target) != direct:
            raise Skipped('选区已改变，已取消转换')
        buf = ctypes.create_unicode_buffer(converted)
        # No fallback after sending a replacement: timeout is ambiguous.
        message(target[1], 0xC2, 1, ctypes.addressof(buf))  # EM_REPLACESEL, undoable
        return '已转换（未使用剪贴板）'
    return clipboard_convert(target, mode, cancelled)


def clipboard_convert(target, mode, cancelled):
    from trad2simp.clipboard import Clipboard
    with Clipboard() as clip:
        clip.snapshot()  # Fails BEFORE copy if any format cannot be preserved.
        expected = clip.sequence
        copied = False
        try:
            for method in (None, 'ctrl+c', 'ctrl+c', 'ctrl+insert'):
                require_target(target, cancelled)
                if w.clipboard_sequence() != expected:
                    raise Skipped('剪贴板已改变，已取消转换')
                if method is None:
                    if not w.try_wm_copy():
                        continue
                elif not w.inject_named_combo(method):
                    raise Skipped('无法访问目标窗口，请检查权限')
                deadline = time.monotonic() + 0.15
                while time.monotonic() < deadline:
                    sequence = w.clipboard_sequence()
                    if sequence != expected:
                        # Only accept copy results from the original app.
                        if not clip.owner_matches(target[0]):
                            raise Skipped('剪贴板被其他程序修改，已取消转换')
                        expected = sequence
                        copied = True
                        break
                    time.sleep(0.01)
                if copied:
                    break
            if not copied:
                return '未读取到选中文字'
            require_target(target, cancelled)
            text = clip.read_text(expected)
            converted = convert_text(text, mode)
            if not text or converted == text:
                return '所选文字无需转换'
            require_target(target, cancelled)
            expected = clip.write_text(converted, expected)
            require_target(target, cancelled)
            if w.clipboard_sequence() != expected:
                raise Skipped('剪贴板已改变，已取消粘贴')
            if not w.try_wm_paste():
                require_target(target, cancelled)
                if not w.inject_named_combo('ctrl+v'):
                    raise Skipped('粘贴失败，请检查目标窗口权限')
            time.sleep(0.25)  # allow applications to consume asynchronous paste
            return '已转换，剪贴板已还原'
        finally:
            if copied:
                if clip.last_write_sequence is not None:
                    expected = clip.last_write_sequence
                if not clip.restore(expected):
                    raise Skipped('剪贴板已被更新，未覆盖新内容')
