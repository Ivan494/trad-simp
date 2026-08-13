"""Traditional ↔ Simplified Chinese selection converter."""

__version__ = '1.0.0'

from trad2simp.config import CONFIG_DIR, CONFIG_PATH, RESTART_FLAG, load_config, log, save_config
from trad2simp.hotkeys import (
    DEFAULT_HOTKEY, MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN,
    HotkeyRecorder, WinHotkeyPump, canonical_hotkey, combo_from_vks,
    hotkey_to_mods_vk, key_to_vk, validate_hotkey,
)
from trad2simp.instance import do_restart, restart_flag_state
from trad2simp.win32 import (
    inject_named_combo, release_modifiers, suppress_hotkey_side_effects,
    wait_modifiers_up,
)


def __getattr__(name):
    # Lazy: App / app pull in tkinter / opencc / pystray. A second-instance
    # launch must import this package and take the mutex without that cost.
    # Defining __getattr__ also disables implicit submodule lookup, so
    # expose the known submodules here.
    if name in ('app', 'config', 'convert', 'hotkeys', 'instance', 'win32'):
        import importlib
        return importlib.import_module(f'.{name}', __name__)
    if name == 'App':
        from trad2simp.app import App
        return App
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
