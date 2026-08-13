"""Config file and rotating log under %APPDATA%\\Trad2Simp."""

import json
import os
import time

APP_TITLE = '繁简转换'

CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Trad2Simp')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
RESTART_FLAG = os.path.join(CONFIG_DIR, 'restart.flag')
RESTART_FLAG_MAX_AGE = 120.0
LOG_MAX_BYTES = 256 * 1024


def load_config():
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        log('config save failed')


def log(msg):
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
