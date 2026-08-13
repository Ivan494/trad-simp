"""Tk UI, tray icon, and convert-on-hotkey orchestration."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import pystray
from PIL import Image, ImageDraw

from trad2simp import config, hotkeys, instance, win32
from trad2simp.config import APP_TITLE, log
from trad2simp.convert import flip_script
from trad2simp.hotkeys import DEFAULT_HOTKEY, validate_hotkey
from trad2simp.win32 import clear_stale_tcl_env

clear_stale_tcl_env()

CLIPBOARD_RETRIES = 6
CLIPBOARD_RETRY_DELAY = 0.05
# Per-attempt wait after each copy method. Total worst-case is still under
# the old single 1.0s sit-and-hope, but a late first copy is retried.
COPY_ATTEMPTS = (
    ('wm_copy', None, 0.08),
    ('ctrl+c', 'ctrl+c', 0.12),
    ('ctrl+c', 'ctrl+c', 0.12),
    ('ctrl+insert', 'ctrl+insert', 0.12),
)
PASTE_SETTLE = 0.14
CONVERT_DEBOUNCE = 0.2
EVENT_POLL_MS = 50


def make_icon():
    img = Image.new('RGB', (64, 64), '#1a73e8')
    d = ImageDraw.Draw(img)
    d.rectangle([4, 14, 26, 50], fill='white')
    d.rectangle([38, 14, 60, 50], fill='#ff5252')
    d.polygon([(28, 24), (36, 20), (36, 28)], fill='white')
    d.polygon([(36, 40), (28, 36), (28, 44)], fill='white')
    return img


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = config.load_config()
        hotkey = self.cfg.get('hotkey', DEFAULT_HOTKEY)
        if not isinstance(hotkey, str) or not hotkey.strip():
            hotkey = DEFAULT_HOTKEY
        try:
            hotkey = validate_hotkey(hotkey)
        except ValueError:
            hotkey = DEFAULT_HOTKEY
        self.listening = False
        self.recording = False
        self.record_token = 0
        self.hotkey_handle = None
        self._recorder = None
        self.last_convert = 0.0
        self.events = queue.Queue()
        self._convert_busy = False
        self._convert_lock = threading.Lock()
        # Call on_hotkey directly from the pump — do not wait for the Tk poll.
        self._hotkey_pump = hotkeys.WinHotkeyPump(self.on_hotkey)

        root.title(APP_TITLE)
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=16)
        frame.pack()

        ttk.Label(frame, text='快捷键').grid(row=0, column=0, sticky='w')
        self.hotkey_var = tk.StringVar(value=hotkey)
        ttk.Entry(frame, textvariable=self.hotkey_var, width=16, state='readonly').grid(row=0, column=1, padx=8)
        self.record_btn = ttk.Button(frame, text='记录', width=6, command=self.toggle_record)
        self.record_btn.grid(row=0, column=2)

        self.status = ttk.Label(frame, text='选中文字后按快捷键，繁简互转', foreground='gray')
        self.status.grid(row=1, column=0, columnspan=3, sticky='w', pady=(10, 0))

        self.tray = pystray.Icon('trad2simp', make_icon(), APP_TITLE, menu=pystray.Menu(
            pystray.MenuItem('显示', lambda *a: self.events.put(('show', None))),
            pystray.MenuItem('退出', lambda *a: self.events.put(('quit', None))),
        ))
        self.tray.run_detached()

        if instance.show_event:
            threading.Thread(target=self._wait_show_signal, daemon=True).start()

        root.protocol('WM_DELETE_WINDOW', self.hide)
        root.after(EVENT_POLL_MS, self.poll_events)
        threading.Thread(target=self._watchdog_loop, daemon=True).start()
        self.start_listen()

    def _watchdog_loop(self):
        while True:
            time.sleep(300)
            if not self.listening:
                continue
            try:
                if self.apply_hotkey():
                    log('watchdog: hotkey re-registered')
            except Exception as ex:
                log(f'watchdog: re-register failed: {ex}')

    def _do_restart(self):
        instance.do_restart()

    def _wait_show_signal(self):
        if not instance.show_event:
            return
        win32.kernel32.WaitForSingleObject(instance.show_event, 0xFFFFFFFF)
        self.events.put(('show', None))

    def poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == 'recorded':
                    self.finish_record(payload[0], payload[1])
                elif kind == 'record_cancel':
                    self.cancel_record()
                elif kind == 'hotkey':
                    self.on_hotkey()
                elif kind == 'show':
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                elif kind == 'quit':
                    self.quit_all()
                    return
        except queue.Empty:
            pass
        self.root.after(EVENT_POLL_MS, self.poll_events)

    def _stop_recorder(self):
        rec = self._recorder
        self._recorder = None
        if rec:
            rec.stop()

    def toggle_record(self):
        if self.recording:
            self.cancel_record()
            return
        self.record_token += 1
        token = self.record_token
        self.recording = True
        self.record_btn.config(text='取消')
        self.status.config(text='请按组合键 (Esc 取消)…')

        def on_combo(combo):
            if token != self.record_token or not self.recording:
                return
            self.recording = False
            self.events.put(('recorded', (combo, token)))

        def on_cancel():
            if token != self.record_token:
                return
            self.recording = False
            self.events.put(('record_cancel', None))

        self._recorder = hotkeys.HotkeyRecorder(on_combo, on_cancel)
        self._recorder.start()

    def finish_record(self, combo, token=None):
        if token is not None and token != self.record_token:
            return
        self._stop_recorder()
        self.recording = False
        self.record_btn.config(text='记录')
        try:
            combo = validate_hotkey(combo)
        except ValueError as ex:
            self.status.config(text=str(ex), foreground='red')
            messagebox.showerror('无效快捷键', str(ex))
            return
        previous = self.hotkey_var.get()
        self.hotkey_var.set(combo)
        self.cfg['hotkey'] = combo
        if self.listening:
            try:
                self.apply_hotkey()
            except Exception as ex:
                self.hotkey_var.set(previous)
                self.cfg['hotkey'] = previous
                messagebox.showerror('无效快捷键', str(ex))
                self.stop_listen()
                return
        config.save_config(self.cfg)
        self.refresh_status()

    def cancel_record(self):
        self.record_token += 1
        self._stop_recorder()
        self.recording = False
        self.record_btn.config(text='记录')
        self.refresh_status()

    def start_listen(self):
        hotkey = self.hotkey_var.get().strip()
        try:
            hotkey = validate_hotkey(hotkey)
        except ValueError as ex:
            messagebox.showerror('无效快捷键', str(ex))
            return
        self.hotkey_var.set(hotkey)
        try:
            self.apply_hotkey()
        except Exception as ex:
            messagebox.showerror('无效快捷键', str(ex))
            try:
                self._hotkey_pump.unregister()
            except Exception:
                pass
            self.hotkey_handle = None
            self.listening = False
            self.refresh_status()
            return
        self.listening = True
        self.cfg['hotkey'] = hotkey
        config.save_config(self.cfg)
        log(f'listening: {hotkey}')
        self.refresh_status()

    def apply_hotkey(self):
        combo = self.hotkey_var.get().strip()
        mods, vk = hotkeys.hotkey_to_mods_vk(combo)
        changed = self._hotkey_pump.register(mods, vk)
        self.hotkey_handle = combo
        return changed

    def stop_listen(self):
        try:
            self._hotkey_pump.unregister()
        except Exception as ex:
            log(f'unregister hotkey failed: {ex}')
        self.hotkey_handle = None
        self.listening = False
        self.refresh_status()

    def refresh_status(self):
        if self.recording:
            self.status.config(text='请按组合键 (Esc 取消)…')
        elif self.listening:
            self.status.config(text=f'选中后按 {self.hotkey_var.get()} 繁简互转')
        else:
            self.status.config(text='快捷键未就绪')
        self.status.config(foreground='gray')

    def _clipboard_sequence(self):
        return win32.clipboard_sequence()

    def _clipboard_has_text(self):
        return win32.clipboard_has_text()

    def _read_clipboard(self):
        last_error = None
        for _ in range(CLIPBOARD_RETRIES):
            try:
                return win32.read_clipboard()
            except Exception as ex:
                last_error = ex
                time.sleep(CLIPBOARD_RETRY_DELAY)
        raise last_error

    def _write_clipboard(self, text):
        last_error = None
        for _ in range(CLIPBOARD_RETRIES):
            try:
                win32.write_clipboard(text)
                return
            except Exception as ex:
                last_error = ex
                time.sleep(CLIPBOARD_RETRY_DELAY)
        raise last_error

    def _selection_copied(self, before_sequence, timeout):
        if before_sequence is None:
            time.sleep(min(timeout, 0.08))
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._clipboard_sequence() != before_sequence:
                return True
            time.sleep(0.01)
        return False

    def _try_wm_copy(self):
        return win32.try_wm_copy()

    def _try_wm_paste(self):
        return win32.try_wm_paste()

    def _inject(self, combo):
        return win32.inject_named_combo(combo)

    def _copy_selection(self, before_sequence):
        """Copy the current selection. Retries internally so the user does not
        have to press the hotkey a second time when the first Ctrl+C is eaten
        by an Alt-menu or IME."""
        for name, combo, wait in COPY_ATTEMPTS:
            try:
                if combo is None:
                    if not self._try_wm_copy():
                        continue
                else:
                    self._inject(combo)
            except Exception as ex:
                log(f'copy via {name} failed: {ex}')
                continue
            if self._selection_copied(before_sequence, wait):
                log(f'copied via {name}')
                return True
        return False

    def _restore_old_text(self, old, old_has_text):
        if not old_has_text:
            return
        try:
            self._write_clipboard(old)
        except Exception as ex:
            log(f'restore clipboard failed: {ex}')

    def on_hotkey(self):
        """Debounce and kick conversion off the UI / message-pump threads."""
        with self._convert_lock:
            now = time.time()
            if now - self.last_convert < CONVERT_DEBOUNCE:
                return
            if self._convert_busy:
                return
            self.last_convert = now
            self._convert_busy = True
        log('trigger')
        threading.Thread(target=self._convert_job, daemon=True).start()

    def _convert_job(self):
        try:
            self._do_convert()
        except Exception as ex:
            log(f'convert job failed: {ex}')
        finally:
            self._convert_busy = False

    def _do_convert(self):
        # Hotkey fires on key-down while Alt/Ctrl may still be held. Wait a
        # short beat (then force key-ups) so Ctrl+C is plain copy.
        try:
            win32.wait_modifiers_up()
        except Exception as ex:
            log(f'wait modifiers failed: {ex}')
            try:
                win32.release_modifiers()
            except Exception:
                pass
            time.sleep(0.03)
        try:
            old = self._read_clipboard()
        except Exception as ex:
            log(f'read clipboard failed: {ex}')
            return
        old_has_text = self._clipboard_has_text()
        before = self._clipboard_sequence()
        if not self._copy_selection(before):
            log('skip: no selection copied')
            return
        try:
            sel = self._read_clipboard()
        except Exception as ex:
            log(f'read selection failed: {ex}')
            self._restore_old_text(old, old_has_text)
            return
        if not sel or not self._clipboard_has_text():
            log('skip: selection has no text')
            self._restore_old_text(old, old_has_text)
            return
        try:
            converted = flip_script(sel)
        except Exception as ex:
            log(f'convert failed: {ex}')
            self._restore_old_text(old, old_has_text)
            return
        if converted == sel:
            log('skip: nothing to convert')
            self._restore_old_text(old, old_has_text)
            return
        try:
            self._write_clipboard(converted)
            time.sleep(0.05)
            pasted = False
            try:
                pasted = self._try_wm_paste()
            except Exception as ex:
                log(f'wm_paste failed: {ex}')
            if not pasted:
                try:
                    win32.release_modifiers()
                except Exception:
                    pass
                self._inject('ctrl+v')
            time.sleep(PASTE_SETTLE)
            log(f'converted {len(sel)} -> {len(converted)} chars')
        except Exception as ex:
            log(f'paste failed: {ex}')
        finally:
            self._restore_old_text(old, old_has_text)

    def hide(self):
        if self.recording:
            self.cancel_record()
        self.root.withdraw()
        if not self.cfg.get('tray_hint'):
            self.cfg['tray_hint'] = True
            config.save_config(self.cfg)
            messagebox.showinfo(APP_TITLE, '已最小化到系统托盘，右键托盘图标可退出。')

    def quit_all(self):
        if self.recording:
            self.cancel_record()
        self.stop_listen()
        try:
            self._hotkey_pump.stop()
        except Exception:
            pass
        self.tray.stop()
        self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
