"""Tk UI, tray icon, and convert-on-hotkey orchestration."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import pystray
from PIL import Image, ImageDraw

from trad2simp import config, hotkeys, instance, win32
from trad2simp import startup as startup_settings
from trad2simp.version import __version__
from trad2simp.selection import capture_target, convert_selection, Skipped
from trad2simp.config import APP_TITLE, log
from trad2simp.hotkeys import DEFAULT_HOTKEY, validate_hotkey
from trad2simp.win32 import clear_stale_tcl_env

clear_stale_tcl_env()

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
    def __init__(self, root, startup=False):
        self.root = root
        self._closing = threading.Event()
        self._worker = None
        self._watchdog_id = None
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

        root.title(f'{APP_TITLE} {__version__}')
        if startup:
            root.withdraw()
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=16)
        frame.pack()

        ttk.Label(frame, text='快捷键').grid(row=0, column=0, sticky='w')
        self.hotkey_var = tk.StringVar(value=hotkey)
        ttk.Entry(frame, textvariable=self.hotkey_var, width=16, state='readonly').grid(row=0, column=1, padx=8)
        self.record_btn = ttk.Button(frame, text='记录', width=6, command=self.toggle_record)
        self.record_btn.grid(row=0, column=2)

        self.mode = self.cfg.get('mode', 'auto')
        self.mode_labels = {'自动': 'auto', '转为简体': 't2s', '转为繁体': 's2t'}
        self.mode_var = tk.StringVar(value=next(k for k, v in self.mode_labels.items() if v == self.mode))
        ttk.Label(frame, text='转换方向').grid(row=1, column=0, sticky='w', pady=(10, 0))
        modes = ttk.Combobox(frame, textvariable=self.mode_var, values=list(self.mode_labels),
                             state='readonly', width=14)
        modes.grid(row=1, column=1, columnspan=2, sticky='w', padx=8, pady=(10, 0))
        modes.bind('<<ComboboxSelected>>', self.change_mode)
        try:
            registered = bool(startup_settings.registered_command())
            startup_error = False
        except OSError:
            registered, startup_error = False, True
        self.startup_var = tk.BooleanVar(value=registered)
        startup_btn = ttk.Checkbutton(frame, text='开机启动（登录后进入托盘）',
                                     variable=self.startup_var, command=self.change_startup)
        startup_btn.grid(row=2, column=0, columnspan=3, sticky='w', pady=(10, 0))
        if startup_error:
            startup_btn.state(['disabled'])
        self.status = ttk.Label(frame, text='选中文字后按快捷键，繁简互转', foreground='gray')
        self.status.grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))

        self.tray = pystray.Icon('trad2simp', make_icon(), f'{APP_TITLE} {__version__}', menu=pystray.Menu(
            pystray.MenuItem('显示', lambda *a: self.events.put(('show', None))),
            pystray.MenuItem('退出', lambda *a: self.events.put(('quit', None))),
        ))
        self.tray.run_detached()

        if instance.show_event:
            threading.Thread(target=self._wait_show_signal, daemon=True).start()

        root.protocol('WM_DELETE_WINDOW', self.hide)
        root.after(EVENT_POLL_MS, self.poll_events)
        self._watchdog_id = root.after(300000, self._watchdog_loop)
        self.start_listen()

    def _show_error(self, title, text):
        self.root.deiconify()
        self.root.lift()
        messagebox.showerror(title, text, parent=self.root)

    def change_mode(self, event=None):
        previous = self.mode
        self.mode = self.mode_labels[self.mode_var.get()]
        self.cfg['mode'] = self.mode
        if not config.save_config(self.cfg):
            self.mode = previous
            self.cfg['mode'] = previous
            self.mode_var.set(next(k for k, v in self.mode_labels.items() if v == previous))
            self._show_error(APP_TITLE, '设置保存失败，请检查配置目录权限')

    def change_startup(self):
        desired = self.startup_var.get()
        try:
            startup_settings.set_enabled(desired)
        except OSError:
            self.startup_var.set(not desired)
            self._show_error(APP_TITLE, '开机启动设置失败，请检查系统权限')

    def _watchdog_loop(self):
        if self._closing.is_set():
            return
        if not self.recording:
            try:
                self.apply_hotkey(force=True)
                self.listening = True
                self.refresh_status()
            except Exception:
                self.listening = False
                self.refresh_status()
                log('hotkey recovery failed')
        self._watchdog_id = self.root.after(300000, self._watchdog_loop)

    def _do_restart(self):
        instance.do_restart()

    def _wait_show_signal(self):
        handle = instance.show_event
        if not handle:
            return
        while not self._closing.is_set():
            result = win32.kernel32.WaitForSingleObject(handle, 250)
            if result == win32.WAIT_OBJECT_0:
                self.events.put(('show', None))
            elif result != win32.WAIT_TIMEOUT:
                log('show event wait failed')
                return

    def poll_events(self):
        if self._closing.is_set():
            return
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
                elif kind == 'status':
                    self.status.config(text=payload, foreground='gray')
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
        if self._convert_busy:
            self.status.config(text='转换进行中，请稍后记录快捷键')
            return
        self.record_token += 1
        token = self.record_token
        self.recording = True
        self.record_btn.config(text='取消')
        self.status.config(text='请按组合键 (Esc 取消)…')

        def on_combo(combo):
            if token != self.record_token or not self.recording:
                return
            self.events.put(('recorded', (combo, token)))

        def on_cancel():
            if token != self.record_token:
                return
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
            self._show_error('无效快捷键', '快捷键无效或被占用，请选择其他组合键')
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
                self._show_error('无效快捷键', '快捷键无效或被占用，请选择其他组合键')
                try:
                    self.apply_hotkey()
                except Exception as ex2:
                    log(f'restore previous hotkey failed: {ex2}')
                    self.stop_listen()
                return
        if not self.listening:
            self.start_listen()
        if not config.save_config(self.cfg):
            self._show_error(APP_TITLE, '快捷键已生效，但设置保存失败')
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
            self._show_error('无效快捷键', '快捷键无效或被占用，请选择其他组合键')
            return
        self.hotkey_var.set(hotkey)
        try:
            self.apply_hotkey()
        except Exception as ex:
            self._show_error('无效快捷键', '快捷键无效或被占用，请选择其他组合键')
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

    def apply_hotkey(self, force=False):
        combo = self.hotkey_var.get().strip()
        mods, vk = hotkeys.hotkey_to_mods_vk(combo)
        changed = self._hotkey_pump.register(mods, vk, force=force)
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

    def on_hotkey(self):
        """The message pump never reads Tk objects or performs conversion."""
        with self._convert_lock:
            now = time.monotonic()
            if self.recording or not self.listening or self._closing.is_set():
                return
            if self._convert_busy or now - self.last_convert < CONVERT_DEBOUNCE:
                return
            self.last_convert = now
            self._convert_busy = True
            mode = self.mode
        target = capture_target()
        self._worker = threading.Thread(target=self._convert_job, args=(mode, target), daemon=True)
        self._worker.start()

    def _convert_job(self, mode, target):
        started = time.monotonic()
        try:
            status = convert_selection(mode, self._closing.is_set, target)
            log(f'conversion completed elapsed_ms={round((time.monotonic() - started) * 1000)}')
        except Skipped as ex:
            status = str(ex)
            log(f'conversion skipped {status} elapsed_ms={round((time.monotonic() - started) * 1000)}')
        except Exception:
            status = '转换未完成，请稍后重试'
            log('conversion failed')
        finally:
            with self._convert_lock:
                self._convert_busy = False
        self.events.put(('status', status))

    def hide(self):
        if self.recording:
            self.cancel_record()
        self.root.withdraw()

    def quit_all(self):
        if self._closing.is_set():
            return
        self._closing.set()
        if self.recording:
            self.cancel_record()
        if self._watchdog_id:
            self.root.after_cancel(self._watchdog_id)
        self.stop_listen()
        try:
            self._hotkey_pump.stop()
        except Exception:
            log('hotkey shutdown failed')
        # Keep the event loop alive until the worker has restored its clipboard.
        self._finish_quit()

    def _finish_quit(self):
        if self._worker and self._worker.is_alive():
            self.root.after(50, self._finish_quit)
            return
        self.tray.stop()
        self.root.destroy()


def run(startup=False):
    root = tk.Tk()
    App(root, startup=startup)
    root.mainloop()
