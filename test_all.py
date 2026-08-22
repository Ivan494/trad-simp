import os
import sys
import tempfile
import time
import tkinter as tk

sys.path.insert(0, '.')

def check(name, cond, detail=''):
    print(f'[{"PASS" if cond else "FAIL"}] {name}' + (f'  -> got: {detail}' if detail and not cond else ''))
    if not cond:
        raise SystemExit(1)

import trad2simp as t2s
from trad2simp.convert import flip_script
from trad2simp.win32 import VK_CONTROL, VK_ESCAPE, VK_MENU

# isolate from the real user config
t2s.config.CONFIG_DIR = tempfile.mkdtemp(prefix='trad2simp_test_')
t2s.config.CONFIG_PATH = os.path.join(t2s.config.CONFIG_DIR, 'config.json')


class FakeClipboard:
    def __init__(self):
        self.data = ''


class FakeMessagebox:
    def __init__(self):
        self.errors = []
    def showerror(self, title, msg):
        self.errors.append(msg)
    def showinfo(self, *a):
        pass


class FakeHotkeyPump:
    """Stand-in for WinHotkeyPump (RegisterHotKey)."""
    def __init__(self, on_hotkey, on_pre=None):
        self.on_hotkey = on_hotkey
        self.on_pre = on_pre
        self.registered = None
        self.fail_next = False

    def start(self):
        pass

    def register(self, mods, vk, force=False):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError('boom')
        changed = force or self.registered != (mods, vk)
        self.registered = (mods, vk)
        return changed

    def unregister(self):
        self.registered = None

    def stop(self):
        self.registered = None


clipboard = FakeClipboard()
seq = [0]
msgbox = FakeMessagebox()
inject_sent = []
keys = type('Keys', (), {'selection': '', 'paste_target': None, 'copy_works': True})()


def fake_inject(combo):
    inject_sent.append(combo)
    if combo == 'ctrl+c':
        if keys.copy_works:
            clipboard.data = keys.selection
            seq[0] += 1
    elif combo == 'ctrl+v':
        keys.paste_target = clipboard.data
    elif combo == 'ctrl+insert':
        if keys.copy_works:
            clipboard.data = keys.selection
            seq[0] += 1
    return True


t2s.hotkeys.WinHotkeyPump = FakeHotkeyPump
t2s.app.pystray.Icon.run_detached = lambda self: None
t2s.app.pystray.Icon.stop = lambda self: None
t2s.app.messagebox = msgbox
t2s.win32.wait_modifiers_up = lambda timeout=0.12: True
t2s.win32.release_modifiers = lambda: True

# ---- Part A: hotkey validation + VK mapping ----
v = t2s.validate_hotkey
check('valid: alt+`', v('alt+`') == 'alt+`')
check('valid: default is alt+`', v(t2s.DEFAULT_HOTKEY) == 'alt+`')
check('valid: ctrl+shift+a canonicalized', v('shift+ctrl+a') == 'ctrl+shift+a')
check('valid: f5', v('f5') == 'f5')
check('valid: left alt alias', v('left alt+1') == 'alt+1')
mods, vk = t2s.hotkey_to_mods_vk('alt+`')
check('alt+` maps to MOD_ALT + grave VK', mods == t2s.MOD_ALT and vk in (0xC0, 0x19), f'mods={mods} vk={vk:#x}')
mods2, vk2 = t2s.hotkey_to_mods_vk('ctrl+shift+a')
check('ctrl+shift+a mods', mods2 == (t2s.MOD_CONTROL | t2s.MOD_SHIFT) and vk2 == ord('A'),
      f'mods={mods2} vk={vk2}')
for bad, why in [
    ('', 'empty'), ('win+shift+s', 'win'), ('shift+win+s', 'win alias'),
    ('print screen', 'printscreen'), ('prtsc', 'prtsc'), ('alt+tab', 'reserved'),
    ('ctrl+alt+del', 'reserved'), ('ctrl+alt+delete', 'reserved delete'),
    ('ctrl+c', 'reserved ctrl+c'), ('ctrl+v', 'reserved ctrl+v'), ('ctrl+x', 'reserved ctrl+x'),
    ('a', 'no modifier non-fkey'), ('ctrl', 'mods only'),
]:
    try:
        v(bad)
        check(f'reject: {why}', False)
    except ValueError:
        check(f'reject: {why}', True)

check('combo_from_vks ctrl+a', t2s.combo_from_vks({VK_CONTROL, ord('A')}) == 'ctrl+a')
check('combo_from_vks alt+` name', 'alt' in (t2s.combo_from_vks({VK_MENU, 0xC0}) or ''))
check('combo_from_vks esc', t2s.combo_from_vks({VK_ESCAPE}) == 'esc')
check('combo_from_vks bare modifier', t2s.combo_from_vks({VK_CONTROL}) is None)

# ---- Part A3: bidirectional convert ----
check('t2s', flip_script('今天是臺灣，我們喝咖啡。') == '今天是台湾，我们喝咖啡。')
check('s2t', flip_script('今天是台湾，我们喝咖啡。') == '今天是臺灣，我們喝咖啡。')
check('roundtrip trad', flip_script(flip_script('繁體測試文字')) == '繁體測試文字')
check('ascii unchanged', flip_script('hello 123') == 'hello 123')
check('empty unchanged', flip_script('') == '')

# ---- Part A2: restart flag staleness ----
flag_dir = tempfile.mkdtemp(prefix='trad2simp_flag_')
real_restart_flag = t2s.config.RESTART_FLAG
t2s.config.RESTART_FLAG = os.path.join(flag_dir, 'restart.flag')
check('no flag -> None', t2s.restart_flag_state() is None, str(t2s.restart_flag_state()))
with open(t2s.config.RESTART_FLAG, 'w', encoding='utf-8') as f:
    f.write(str(time.time()))
check('fresh flag -> fresh', t2s.restart_flag_state() == 'fresh', str(t2s.restart_flag_state()))
check('fresh flag consumed', not os.path.exists(os.path.join(flag_dir, 'restart.flag')))
with open(t2s.config.RESTART_FLAG, 'w', encoding='utf-8') as f:
    f.write(str(time.time() - 1000))
check('stale flag -> stale', t2s.restart_flag_state() == 'stale', str(t2s.restart_flag_state()))
with open(t2s.config.RESTART_FLAG, 'w', encoding='utf-8') as f:
    f.write('1')
check('legacy garbage flag -> stale', t2s.restart_flag_state() == 'stale', str(t2s.restart_flag_state()))
t2s.config.RESTART_FLAG = real_restart_flag

# ---- Part B: App with faked OS clipboard ----
root = tk.Tk()
root.withdraw()
app = t2s.App(root)
check('no mode radios', not hasattr(app, 'mode_var'))
check('no listen button', not hasattr(app, 'toggle_btn'))
app._clipboard_sequence = lambda: seq[0]
app._clipboard_has_text = lambda: bool(clipboard.data)
app._read_clipboard = lambda: clipboard.data
app._write_clipboard = lambda text: setattr(clipboard, 'data', text)
app._try_wm_copy = lambda: False
app._try_wm_paste = lambda: False
app._inject = fake_inject

check('auto-start registers hotkey',
      app.hotkey_handle == t2s.DEFAULT_HOTKEY and app._hotkey_pump.registered is not None,
      str(app.hotkey_handle))
check('listening flag', app.listening is True)
app.start_listen()
check('start_listen still registers hotkey', app.hotkey_handle == t2s.DEFAULT_HOTKEY, str(app.hotkey_handle))
check('re-register same combo is no-op', app.apply_hotkey() is False)


def wait_convert(timeout=2.0):
    deadline = time.time() + timeout
    while app._convert_busy and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.02)


def fire(selection, old):
    clipboard.data = old
    keys.selection = selection
    keys.paste_target = None
    inject_sent.clear()
    app.last_convert = 0.0
    app.on_hotkey()
    wait_convert()


# 1. empty old clipboard + selection
fire('繁體測試文字', '')
check('empty clipboard: converted', keys.paste_target == '繁体测试文字', keys.paste_target)
check('empty clipboard: converted kept (nothing to restore)', clipboard.data == '繁体测试文字', clipboard.data)

# 2. non-empty old clipboard restored
fire('繁體第二輪', 'OLD-CLIP')
check('replace: converted', keys.paste_target == '繁体第二轮', keys.paste_target)
check('replace: old restored', clipboard.data == 'OLD-CLIP')

# 3. simplified selection flips back to traditional
fire('简体第二轮', 'OLD-CLIP')
check('s2t replace: converted', keys.paste_target == '簡體第二輪', keys.paste_target)
check('s2t replace: old restored', clipboard.data == 'OLD-CLIP')

# 5. no selection copied (clipboard never changes)
keys.copy_works = False
clipboard.data = 'SEED'
keys.selection = '繁體X'
keys.paste_target = None
inject_sent.clear()
app.last_convert = 0.0
app.on_hotkey()
wait_convert()
check('no selection: skipped', keys.paste_target is None, keys.paste_target)
check('no selection: clipboard untouched', clipboard.data == 'SEED')
check('no selection: retried inject', inject_sent.count('ctrl+c') == 2 and 'ctrl+insert' in inject_sent, str(inject_sent))
keys.copy_works = True

# 5b. selection read fails -> old clipboard restored
real_read = app._read_clipboard
paste_calls = [0]


def flaky_read():
    paste_calls[0] += 1
    if paste_calls[0] > 1:
        raise RuntimeError('clipboard locked')
    return clipboard.data


app._read_clipboard = flaky_read
clipboard.data = 'OLD-CLIP'
keys.selection = '繁體X'
inject_sent.clear()
app.last_convert = 0.0
app.on_hotkey()
wait_convert()
check('read failure: old clipboard restored', clipboard.data == 'OLD-CLIP', clipboard.data)
check('read failure: no paste', keys.paste_target is None, keys.paste_target)
app._read_clipboard = real_read
paste_calls[0] = 0

# 5c. first Ctrl+C eaten, second succeeds — no extra hotkey press
copy_n = [0]


def flaky_inject(combo):
    inject_sent.append(combo)
    if combo == 'ctrl+c':
        copy_n[0] += 1
        if copy_n[0] >= 2:
            clipboard.data = keys.selection
            seq[0] += 1
    elif combo == 'ctrl+v':
        keys.paste_target = clipboard.data
    return True


app._inject = flaky_inject
fire('繁體重試一次', 'OLD-CLIP')
check('retry copy: converted', keys.paste_target == '繁体重试一次', keys.paste_target)
check('retry copy: two ctrl+c', inject_sent.count('ctrl+c') == 2, str(inject_sent))
check('retry copy: old restored', clipboard.data == 'OLD-CLIP')
app._inject = fake_inject

# 6. reentry guard: rapid double fire -> single ctrl+v
clipboard.data = ''
keys.selection = '繁體連發'
inject_sent.clear()
app.last_convert = 0.0
app.on_hotkey()
app.on_hotkey()
wait_convert()
check('reentry guard: one ctrl+v', inject_sent.count('ctrl+v') == 1, str(inject_sent))

# 7. recorder rejects system-reserved combos
prev = app.hotkey_var.get()
app.finish_record('shift+win+s')
check('reject win combo', app.hotkey_var.get() == prev)
app.finish_record('alt+tab')
check('reject reserved combo', app.hotkey_var.get() == prev)
check('rejection showed messagebox', len(msgbox.errors) == 2, str(msgbox.errors))
check('still listening after rejection', app.listening and app.hotkey_handle == t2s.DEFAULT_HOTKEY)

# 8. valid re-record re-registers while listening
app.finish_record('ctrl+alt+k')
check('new combo set', app.hotkey_var.get() == 'ctrl+alt+k')
check('new hotkey registered', app.hotkey_handle == 'ctrl+alt+k', str(app.hotkey_handle))
mods_k, vk_k = t2s.hotkey_to_mods_vk('ctrl+alt+k')
check('pump has new combo', app._hotkey_pump.registered == (mods_k, vk_k), str(app._hotkey_pump.registered))

# 8b. failed re-record restores previous hotkey instead of stopping listen
prev_combo = app.hotkey_var.get()
prev_reg = app._hotkey_pump.registered
app._hotkey_pump.fail_next = True
app.finish_record('ctrl+alt+m')
check('failed re-record keeps previous combo', app.hotkey_var.get() == prev_combo, app.hotkey_var.get())
check('failed re-record still listening', app.listening is True)
check('failed re-record restored pump', app._hotkey_pump.registered == prev_reg, str(app._hotkey_pump.registered))

# 8c. force re-register reports changed even for the same combo
check('force re-register returns True', app.apply_hotkey(force=True) is True)

# 9. recording start / esc cancel (no WH_KEYBOARD_LL hook)
app.toggle_record()
check('recording starts', app.recording is True and app._recorder is not None)
app.cancel_record()
check('cancel recording', app.recording is False and app._recorder is None)

# 10. _do_restart: verified handoff, no suicide
exits = []
real_exit = t2s.instance.os._exit


def fake_exit(code):
    exits.append(code)
    raise SystemExit(code)


t2s.instance.os._exit = fake_exit
flag2 = os.path.join(flag_dir, 'restart2.flag')
real_restart_flag2 = t2s.config.RESTART_FLAG
t2s.config.RESTART_FLAG = flag2
real_popen = t2s.instance.subprocess.Popen
spawns = []


class FakeProc:
    def __init__(self, consume):
        self.consume = consume
    def poll(self):
        if self.consume and os.path.exists(t2s.config.RESTART_FLAG):
            os.remove(t2s.config.RESTART_FLAG)
        return None


def fake_popen(consume):
    def _popen(*a, **k):
        spawns.append(a)
        return FakeProc(consume)
    return _popen


t2s.instance.subprocess.Popen = fake_popen(True)
try:
    app._do_restart()
except SystemExit:
    pass
check('restart: exits after child confirmed', exits == [0], str(exits))
check('restart: single spawn on success', len(spawns) == 1, str(spawns))
check('restart: flag consumed by child', not os.path.exists(flag2))

exits.clear()
spawns.clear()
real_sleep = t2s.instance.time.sleep
t2s.instance.time.sleep = lambda s: None
t2s.instance.subprocess.Popen = fake_popen(False)
app._do_restart()
check('restart: stays alive on failure', exits == [], str(exits))
check('restart: retried 3 spawns', len(spawns) == 3, str(spawns))
check('restart: leftover flag cleaned', not os.path.exists(flag2))
t2s.instance.time.sleep = real_sleep

t2s.instance.subprocess.Popen = lambda *a, **k: (_ for _ in ()).throw(OSError('boom'))
exits.clear()
app._do_restart()
check('restart: spawn exception stays alive', exits == [] and not os.path.exists(flag2), str(exits))
t2s.instance.subprocess.Popen = real_popen
t2s.config.RESTART_FLAG = real_restart_flag2
t2s.instance.os._exit = real_exit

# 11. stop_listen
app.stop_listen()
check('stop_listen unregisters', app._hotkey_pump.registered is None and app.listening is False)

# 12. invalid start_listen does not enable
app._hotkey_pump.fail_next = True
app.start_listen()
check('failed register stays stopped', app.listening is False)

# 13. failed re-registration while previously listening
app.start_listen()
check('re-listened', app.listening is True and app.hotkey_handle is not None, str(app.hotkey_handle))
app._hotkey_pump.fail_next = True
app.start_listen()
check('failed re-add: not listening', app.listening is False)
app.stop_listen()
check('stop after failed re-add: no crash', True)

# 14. hotkey event from pump reaches convert path via poll_events
app.start_listen()
clipboard.data = ''
keys.selection = '繁體事件'
keys.paste_target = None
inject_sent.clear()
app.last_convert = 0.0
app.events.put(('hotkey', None))
app.poll_events()
wait_convert()
check('queue hotkey converts', keys.paste_target == '繁体事件', keys.paste_target)

app.quit_all()

# Do not touch the real user config under %APPDATA%.
print('ALL TESTS PASSED')
