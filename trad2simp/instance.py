"""Single-instance mutex, tray-show event, and optional process handoff."""

import os
import subprocess
import sys
import time

from trad2simp import config
from trad2simp.win32 import (
    WAIT_ABANDONED, WAIT_OBJECT_0, WAIT_TIMEOUT, kernel32, last_error, user32,
)

SHOW_EVENT_NAME = r'Local\Trad2SimpShowEvent'
MUTEX_NAME = 'Trad2SimpMutex'

# Filled by acquire_or_exit(); App waits on this to restore the window.
show_event = None


def restart_flag_state():
    """Consume the restart flag. Returns 'fresh' when the watchdog asked a
    process to take over recently, 'stale' when the flag predates the window
    (a crashed restart must not bypass the single-instance mutex), or None."""
    path = config.RESTART_FLAG
    if not os.path.exists(path):
        return None
    fresh = False
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read().strip()
        try:
            fresh = 0 <= time.time() - float(raw) <= config.RESTART_FLAG_MAX_AGE
        except ValueError:
            fresh = False
        os.remove(path)
    except OSError:
        pass
    return 'fresh' if fresh else 'stale'


def _mutex_is_free(mutex):
    """Wait 0 on the mutex. 0/ABANDONED -> no live owner (we may take over);
    TIMEOUT -> a live instance owns it."""
    result = kernel32.WaitForSingleObject(mutex, 0)
    if result not in (WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT):
        raise OSError('Instance check failed')
    return result != WAIT_TIMEOUT


def acquire_or_exit():
    """Own the single-instance mutex or signal the live instance and exit.

    Heavy UI imports must run only after this returns, so a second launch is
    rejected before paying the multi-second import cost.
    """
    global show_event

    # bInitialOwner=True: the first creator owns the mutex, so a later
    # instance can tell "live owner" (WAIT_TIMEOUT) from "previous owner
    # crashed" (WAIT_ABANDONED) and take over instead of bricking the app
    # behind an abandoned mutex.
    mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    already_running = last_error() == 183
    if not mutex:
        raise OSError('Cannot create instance mutex')
    restart_state = restart_flag_state()
    show_event = kernel32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
    if not show_event:
        kernel32.CloseHandle(mutex)
        raise OSError('Cannot create instance event')

    if already_running and not _mutex_is_free(mutex):
        if restart_state == 'fresh':
            # Watchdog handoff: the old instance still owns the mutex.
            # Stay dormant (no tray, no hotkey) until it exits, then take over.
            acquired = False
            for _ in range(600):
                wait_result = kernel32.WaitForSingleObject(mutex, 0)
                if wait_result in (WAIT_OBJECT_0, WAIT_ABANDONED):
                    acquired = True
                    break
                if wait_result != WAIT_TIMEOUT:
                    raise OSError('Instance wait failed')
                time.sleep(0.1)
            if not acquired:
                os._exit(1)
        else:
            if show_event:
                kernel32.SetEvent(show_event)
                kernel32.CloseHandle(show_event)
                show_event = None
            else:
                user32.MessageBoxW(None, f'{config.APP_TITLE} 已在运行中', config.APP_TITLE, 0)
            # os._exit, not sys.exit: interpreter shutdown would join
            # import-time threads and can hang a windowed build, leaving a
            # zombie that keeps the mutex alive and bricks later launches.
            os._exit(0)
    return mutex


def do_restart():
    """Spawn a replacement process and exit once it takes over."""
    for _ in range(3):
        try:
            with open(config.RESTART_FLAG, 'w', encoding='utf-8') as f:
                f.write(str(time.time()))
            if getattr(sys, 'frozen', False):
                proc = subprocess.Popen([sys.executable])
            else:
                proc = subprocess.Popen([sys.executable, '-m', 'trad2simp'])
        except Exception as ex:
            config.log('watchdog restart spawn failed')
            continue
        for _ in range(100):
            if proc.poll() is not None:
                config.log('watchdog: spawned process died early')
                break
            if not os.path.exists(config.RESTART_FLAG):
                config.log('watchdog: restart confirmed')
                os._exit(0)
            time.sleep(0.1)
    try:
        os.remove(config.RESTART_FLAG)
    except OSError:
        pass
    config.log('watchdog: restart failed, staying alive')
