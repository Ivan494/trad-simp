import ctypes
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import MagicMock, patch

if sys.platform != 'win32':
    raise unittest.SkipTest('Windows integration tests')

from trad2simp import app, config, hotkeys, instance, startup, win32 as w
from trad2simp import clipboard as cb
from trad2simp import selection as s


class NativeClipboardTests(unittest.TestCase):
    def test_isolated_station(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('clipboard_station.py'))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


class HotkeyTests(unittest.TestCase):
    def test_validation(self):
        for combo in ('ctrl+c', 'control+c', 'ctrl+ins', 'ctrl+insert', 'shift+insert',
                      'shift+del', 'alt+tab', 'alt+f4', 'win+shift+s', 'ctrl', '', 'a'):
            with self.subTest(combo=combo), self.assertRaises(ValueError):
                hotkeys.validate_hotkey(combo)
        self.assertEqual(hotkeys.validate_hotkey('shift+control+k'), 'ctrl+shift+k')
        self.assertEqual(hotkeys.validate_hotkey('alt+`'), 'alt+`')
        self.assertEqual(hotkeys.validate_hotkey('f5'), 'f5')

    def test_mods_and_recording(self):
        self.assertEqual(hotkeys.hotkey_to_mods_vk('ctrl+shift+a'), (6, 65))
        self.assertEqual(hotkeys.combo_from_vks({w.VK_CONTROL, 65}), 'ctrl+a')
        self.assertEqual(hotkeys.combo_from_vks({w.VK_ESCAPE}), 'esc')
        self.assertIsNone(hotkeys.combo_from_vks({w.VK_CONTROL}))


class StartupTests(unittest.TestCase):
    def test_quoted_frozen_command(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', r'C:\Apps With Spaces\Trad2Simp.exe'):
            self.assertEqual(startup.command(), '"C:\\Apps With Spaces\\Trad2Simp.exe" --startup')

    def test_source_command_independent_of_cwd(self):
        with patch.object(sys, 'frozen', False, create=True):
            result = startup.command()
        self.assertIn(str(Path(__file__).resolve().parents[1] / 'run.py'), result)
        self.assertTrue(result.endswith('--startup'))

    def test_registry_only_current_user(self):
        with patch.object(startup, 'winreg') as reg:
            startup.set_enabled(True)
            self.assertEqual(reg.CreateKeyEx.call_args.args[0], reg.HKEY_CURRENT_USER)
            self.assertIn('--startup', reg.SetValueEx.call_args.args[-1])
            startup.set_enabled(False)
            reg.DeleteValue.assert_called_once()
            reg.OpenKey.side_effect = FileNotFoundError
            self.assertEqual(startup.registered_command(), '')

    def test_registry_errors_not_swallowed(self):
        with patch.object(startup.winreg, 'CreateKeyEx', side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                startup.set_enabled(True)


class InstanceTests(unittest.TestCase):
    def test_duplicate_startup_never_shows_window(self):
        for silent in (False, True):
            with patch.object(instance, 'kernel32') as kernel, patch.object(instance, 'last_error', return_value=183), \
                    patch.object(instance, 'restart_flag_state', return_value=None), \
                    patch.object(instance.os, '_exit', side_effect=SystemExit):
                kernel.WaitForSingleObject.return_value = w.WAIT_TIMEOUT
                with self.assertRaises(SystemExit):
                    instance.acquire_or_exit(startup=silent)
                self.assertEqual(kernel.SetEvent.call_count, int(not silent))
        instance.show_event = None

    def test_failed_mutex_or_wait(self):
        with patch.object(instance, 'kernel32') as kernel:
            kernel.CreateMutexW.return_value = 0
            with self.assertRaises(OSError):
                instance.acquire_or_exit()
            kernel.WaitForSingleObject.return_value = 0xffffffff
            with self.assertRaises(OSError):
                instance._mutex_is_free(123)


class DirectTests(unittest.TestCase):
    def test_custom_text_widgets_use_keyboard_paste(self):
        with patch.object(w, 'focused_hwnd', return_value=123), \
                patch.object(w, 'window_class_name', return_value='TkText'), \
                patch.object(w, 'send_message_timeout') as send:
            self.assertFalse(w.try_wm_paste())
            send.assert_not_called()

    def test_browser_skips_unsupported_wm_copy(self):
        with patch.object(w, 'focused_hwnd', return_value=123), \
                patch.object(w, 'window_class_name', return_value='Chrome_RenderWidgetHostHWND'), \
                patch.object(w, 'send_message_timeout') as send:
            self.assertFalse(w.try_wm_copy())
            send.assert_not_called()

    def test_readonly_password_and_multiline_controls(self):
        for style in (0x20, 0x800):
            with patch.object(w, 'window_class_name', return_value='EDIT'), \
                    patch.object(w.user32, 'GetWindowLongW', return_value=style):
                with self.assertRaises(s.Skipped):
                    s.direct_selection((1, 2))
        with patch.object(w, 'window_class_name', return_value='EDIT'), \
                patch.object(w.user32, 'GetWindowLongW', return_value=4), \
                patch.object(w.user32, 'IsWindowUnicode', return_value=True):
            self.assertIsNone(s.direct_selection((1, 2)))

    def test_direct_never_uses_clipboard(self):
        with patch.object(s, 'capture_target', return_value=(1, 2)), \
                patch.object(w, 'wait_modifiers_up'), \
                patch.object(s, 'direct_selection', return_value=(0, 2, '繁體')), \
                patch.object(s, 'message') as msg, patch.object(s, 'clipboard_convert') as fallback:
            self.assertIn('未使用剪贴板', s.convert_selection('t2s'))
            self.assertEqual(msg.call_args.args[1:3], (0xC2, 1))
            fallback.assert_not_called()

    def test_ambiguous_replacement_never_falls_back(self):
        with patch.object(s, 'capture_target', return_value=(1, 2)), patch.object(w, 'wait_modifiers_up'), \
                patch.object(s, 'direct_selection', return_value=(0, 2, '繁體')), \
                patch.object(s, 'message', side_effect=s.Skipped('timeout')), \
                patch.object(s, 'clipboard_convert') as fallback:
            with self.assertRaises(s.Skipped):
                s.convert_selection('t2s')
            fallback.assert_not_called()

    def test_focus_and_selection_changes_abort(self):
        with patch.object(s, 'capture_target', return_value=(3, 4)):
            with self.assertRaises(s.Skipped):
                s.require_target((1, 2), lambda: False)
        with patch.object(s, 'capture_target', return_value=(1, 2)), patch.object(w, 'wait_modifiers_up'), \
                patch.object(s, 'direct_selection', side_effect=[(0, 2, '繁體'), (2, 4, '繁體')]), \
                patch.object(s, 'message') as msg:
            with self.assertRaises(s.Skipped):
                s.convert_selection('t2s')
            msg.assert_not_called()

    def test_native_edit_unicode_and_undo(self):
        hwnd = w.user32.CreateWindowExW(0, 'EDIT', '😀繁體測試', 0,
                                       0, 0, 200, 100, None, None, None, None)
        self.assertTrue(hwnd)
        try:
            s.message(hwnd, 0xB1, 2, 4)
            self.assertEqual(s.direct_selection((hwnd, hwnd)), (2, 4, '繁體'))
            with patch.object(s, 'capture_target', return_value=(hwnd, hwnd)), patch.object(w, 'wait_modifiers_up'):
                s.convert_selection('t2s')
            buf = ctypes.create_unicode_buffer(100)
            s.message(hwnd, 0xD, 100, ctypes.addressof(buf))
            self.assertEqual(buf.value, '😀繁体測試')
            s.message(hwnd, 0xC7)
            s.message(hwnd, 0xD, 100, ctypes.addressof(buf))
            self.assertEqual(buf.value, '😀繁體測試')
        finally:
            w.user32.DestroyWindow(hwnd)


class ClipboardFlowTests(unittest.TestCase):
    def setUp(self):
        self.clip = MagicMock()
        self.clip.__enter__.return_value = self.clip
        self.clip.sequence = 1
        self.clip.last_write_sequence = None
        self.clip.owner_matches.return_value = True
        self.clip.read_text.return_value = '繁體'
        self.clip.write_text.return_value = 3
        self.clip.restore.return_value = True
        patches = [patch.object(cb, 'Clipboard', return_value=self.clip),
                   patch.object(s, 'require_target'), patch.object(w, 'try_wm_copy', return_value=True),
                   patch.object(w, 'try_wm_paste', return_value=True),
                   patch.object(w, 'clipboard_sequence', side_effect=[1, 2, 3]),
                   patch.object(s.time, 'sleep')]
        self.mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)

    def test_success_and_restore(self):
        s.clipboard_convert((1, 2), 't2s', lambda: False)
        self.clip.write_text.assert_called_once_with('繁体', 2)
        self.clip.restore.assert_called_once_with(3)

    def test_snapshot_failure_never_copies(self):
        self.clip.snapshot.side_effect = s.Skipped('unsupported')
        with self.assertRaises(s.Skipped):
            s.clipboard_convert((1, 2), 'auto', lambda: False)
        w.try_wm_copy.assert_not_called()

    def test_foreign_copy_not_overwritten(self):
        self.clip.owner_matches.return_value = False
        with self.assertRaises(s.Skipped):
            s.clipboard_convert((1, 2), 'auto', lambda: False)
        self.clip.restore.assert_not_called()
        self.clip.write_text.assert_not_called()

    def test_read_failure_restores_snapshot(self):
        self.clip.read_text.side_effect = OSError
        with self.assertRaises(OSError):
            s.clipboard_convert((1, 2), 'auto', lambda: False)
        self.clip.restore.assert_called_once_with(2)

    def test_partial_write_restores_snapshot(self):
        self.clip.write_text.side_effect = OSError
        self.clip.last_write_sequence = 4
        with self.assertRaises(OSError):
            s.clipboard_convert((1, 2), 'auto', lambda: False)
        self.clip.restore.assert_called_once_with(4)

    def test_new_copy_before_paste_cancels(self):
        self.mocks[4].side_effect = [1, 2, 99]
        self.clip.restore.return_value = False
        with self.assertRaises(s.Skipped):
            s.clipboard_convert((1, 2), 'auto', lambda: False)
        w.try_wm_paste.assert_not_called()


class AppTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [patch.object(config, 'CONFIG_DIR', self.tmp.name),
                   patch.object(config, 'CONFIG_PATH', os.path.join(self.tmp.name, 'config.json')),
                   patch.object(startup, 'registered_command', return_value=''),
                   patch.object(startup, 'set_enabled'), patch.object(app, 'messagebox'),
                   patch.object(app.pystray.Icon, 'run_detached'), patch.object(app.pystray.Icon, 'stop'),
                   patch.object(hotkeys, 'WinHotkeyPump'), patch.object(instance, 'show_event', None)]
        self.mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.a = app.App(self.root, startup=True)
        self.addCleanup(self.a.quit_all)

    def test_defaults_mode_and_startup_rollback(self):
        self.assertEqual(self.root.state(), 'withdrawn')
        self.assertEqual(self.a.mode, 'auto')
        self.assertFalse(self.a.startup_var.get())
        self.a.mode_var.set('转为简体')
        self.a.change_mode()
        self.assertEqual(config.load_config()['mode'], 't2s')
        self.mocks[3].side_effect = PermissionError
        self.a.startup_var.set(True)
        self.a.change_startup()
        self.assertFalse(self.a.startup_var.get())

    def test_recording_and_shutdown_suppress_conversion(self):
        with patch.object(app, 'convert_selection') as convert:
            self.a.recording = True
            self.a.on_hotkey()
            convert.assert_not_called()
            self.a.recording = False
            self.a.quit_all()
            self.a.on_hotkey()
            convert.assert_not_called()

    def test_close_always_hides_without_popup(self):
        for _ in range(2):
            self.root.deiconify()
            self.a.hide()
            self.assertEqual(self.root.state(), 'withdrawn')
        self.mocks[4].showinfo.assert_not_called()
        self.assertNotIn('tray_hint', config.load_config())

    def test_hotkey_failure_restores_old_combo(self):
        self.a._hotkey_pump.register.side_effect = [RuntimeError(), True]
        previous = self.a.hotkey_var.get()
        self.a.finish_record('ctrl+alt+k')
        self.assertEqual(self.a.hotkey_var.get(), previous)
        self.assertTrue(self.a.listening)
