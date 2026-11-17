"""Opt-in, current-user startup. No administrator privileges required."""

import os
from pathlib import Path
import subprocess
import sys
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'Trad2Simp'


def command():
    executable = os.path.abspath(sys.executable)
    if getattr(sys, 'frozen', False):
        args = [executable, '--startup']
    else:
        pythonw = Path(executable).with_name('pythonw.exe')
        args = [str(pythonw) if pythonw.exists() else executable,
                str(Path(__file__).resolve().parent.parent / 'run.py'), '--startup']
    return subprocess.list2cmdline(args)


def registered_command():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, kind = winreg.QueryValueEx(key, VALUE_NAME)
            return value if kind == winreg.REG_SZ and isinstance(value, str) else ''
    except FileNotFoundError:
        return ''


def set_enabled(enabled):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
