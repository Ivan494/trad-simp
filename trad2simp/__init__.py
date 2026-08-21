"""Traditional ↔ Simplified Chinese selection converter."""

__version__ = '1.0.1'

# Lazy imports keep `from trad2simp.convert import flip_script` free of
# Windows-only ctypes bindings, and let a second-instance launch take the
# mutex without paying for tkinter / opencc / pystray.


def __getattr__(name):
    if name in ('app', 'config', 'convert', 'hotkeys', 'instance', 'win32'):
        import importlib
        return importlib.import_module(f'.{name}', __name__)

    _lazy = {
        'App': ('.app', 'App'),
        'CONFIG_DIR': ('.config', 'CONFIG_DIR'),
        'CONFIG_PATH': ('.config', 'CONFIG_PATH'),
        'RESTART_FLAG': ('.config', 'RESTART_FLAG'),
        'load_config': ('.config', 'load_config'),
        'log': ('.config', 'log'),
        'save_config': ('.config', 'save_config'),
        'DEFAULT_HOTKEY': ('.hotkeys', 'DEFAULT_HOTKEY'),
        'MOD_ALT': ('.hotkeys', 'MOD_ALT'),
        'MOD_CONTROL': ('.hotkeys', 'MOD_CONTROL'),
        'MOD_SHIFT': ('.hotkeys', 'MOD_SHIFT'),
        'MOD_WIN': ('.hotkeys', 'MOD_WIN'),
        'HotkeyRecorder': ('.hotkeys', 'HotkeyRecorder'),
        'WinHotkeyPump': ('.hotkeys', 'WinHotkeyPump'),
        'canonical_hotkey': ('.hotkeys', 'canonical_hotkey'),
        'combo_from_vks': ('.hotkeys', 'combo_from_vks'),
        'hotkey_to_mods_vk': ('.hotkeys', 'hotkey_to_mods_vk'),
        'key_to_vk': ('.hotkeys', 'key_to_vk'),
        'validate_hotkey': ('.hotkeys', 'validate_hotkey'),
        'do_restart': ('.instance', 'do_restart'),
        'restart_flag_state': ('.instance', 'restart_flag_state'),
        'inject_named_combo': ('.win32', 'inject_named_combo'),
        'release_modifiers': ('.win32', 'release_modifiers'),
        'suppress_hotkey_side_effects': ('.win32', 'suppress_hotkey_side_effects'),
        'wait_modifiers_up': ('.win32', 'wait_modifiers_up'),
    }
    if name in _lazy:
        import importlib
        mod_name, attr = _lazy[name]
        mod = importlib.import_module(mod_name, __name__)
        value = getattr(mod, attr)
        globals()[name] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


__all__ = [
    'App',
    'CONFIG_DIR',
    'CONFIG_PATH',
    'DEFAULT_HOTKEY',
    'HotkeyRecorder',
    'MOD_ALT',
    'MOD_CONTROL',
    'MOD_SHIFT',
    'MOD_WIN',
    'RESTART_FLAG',
    'WinHotkeyPump',
    'canonical_hotkey',
    'combo_from_vks',
    'do_restart',
    'hotkey_to_mods_vk',
    'inject_named_combo',
    'key_to_vk',
    'load_config',
    'log',
    'release_modifiers',
    'restart_flag_state',
    'save_config',
    'suppress_hotkey_side_effects',
    'validate_hotkey',
    'wait_modifiers_up',
]
