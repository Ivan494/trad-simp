"""Entry: `python -m trad2simp` or the frozen Trad2Simp.exe."""

import os
import sys


def _ensure_pkg_on_path():
    if __package__:
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)


def _run_selftest():
    from trad2simp.convert import flip_script
    trad = '今天是臺灣，我們喝咖啡。'
    simp = '今天是台湾，我们喝咖啡。'
    ok = flip_script(trad) == simp and flip_script(simp) == trad
    result = f'{flip_script(trad)}\n{flip_script(simp)}'
    selftest_path = os.path.join(os.environ.get('TEMP', '.'), 'Trad2Simp_selftest.txt')
    try:
        os.makedirs(os.path.dirname(selftest_path) or '.', exist_ok=True)
        with open(selftest_path, 'w', encoding='utf-8') as f:
            f.write(result + '\n')
    except OSError:
        pass
    if hasattr(sys.stdout, 'buffer'):
        try:
            sys.stdout.buffer.write((result + '\n').encode('utf-8'))
            sys.stdout.buffer.flush()
        except (OSError, UnicodeEncodeError):
            pass
    sys.exit(0 if ok else 2)


def main():
    _ensure_pkg_on_path()
    from trad2simp.win32 import clear_stale_tcl_env
    clear_stale_tcl_env()
    if '--selftest' in sys.argv:
        _run_selftest()
    from trad2simp.instance import acquire_or_exit
    acquire_or_exit()
    from trad2simp.app import run
    run()


if __name__ == '__main__':
    main()
