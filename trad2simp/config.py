"""Config file and rotating log under %APPDATA%\\Trad2Simp."""

import json
import os
import time
import tempfile
import threading

APP_TITLE = '繁简转换'

CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Trad2Simp')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
RESTART_FLAG = os.path.join(CONFIG_DIR, 'restart.flag')
RESTART_FLAG_MAX_AGE = 120.0
LOG_MAX_BYTES = 256 * 1024
_LOG_LOCK = threading.Lock()


def load_config():
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            value = json.load(f)
            if not isinstance(value, dict):
                return {}
            result = {}
            if isinstance(value.get('hotkey'), str):
                result['hotkey'] = value['hotkey']
            if value.get('mode') in ('auto', 't2s', 's2t'):
                result['mode'] = value['mode']
            if isinstance(value.get('tray_hint'), bool):
                result['tray_hint'] = value['tray_hint']
            return result
    except (OSError, ValueError, UnicodeError):
        return {}


def save_config(cfg):
    temp_path = None
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=CONFIG_DIR,
                                         prefix='.config-', delete=False) as f:
            temp_path = f.name
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, CONFIG_PATH)
        return True
    except (OSError, ValueError, TypeError):
        log('config save failed')
        return False
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def log(msg):
    with _LOG_LOCK:
        _write_log(str(msg).split(':', 1)[0].replace('\n', ' ')[:100])


def _write_log(msg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        path = os.path.join(CONFIG_DIR, 'log.txt')
        try:
            if os.path.getsize(path) > LOG_MAX_BYTES:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    tail = f.readlines()[-200:]
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(tail)
        except OSError:
            pass
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'{time.strftime("%m-%d %H:%M:%S")} {msg}\n')
    except OSError:
        pass
