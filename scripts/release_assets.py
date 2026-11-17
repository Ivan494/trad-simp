"""Build notices, source provenance, and checksums next to the fresh executable."""
import hashlib
from importlib import metadata
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trad2simp.version import __version__

out = Path('dist')
notices = ['Trad2Simp ' + __version__, Path('LICENSE').read_text(encoding='utf-8')]
for name in ('opencc', 'Pillow', 'pystray', 'six', 'pyinstaller'):
    dist = metadata.distribution(name)
    notices.append(f'\n{name} {dist.version}\n')
    for path in dist.files or []:
        if any(part.lower().startswith(('license', 'copying', 'notice')) for part in path.parts):
            try:
                notices.append(Path(dist.locate_file(path)).read_text(encoding='utf-8'))
            except (UnicodeError, OSError):
                pass
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.exists():
    notices.append(python_license.read_text(encoding='utf-8'))
for directory in (Path(sys.base_prefix) / 'tcl').glob('*'):
    for name in ('license.terms', 'LICENSE'):
        license_path = directory / name
        if license_path.is_file():
            notices.append(license_path.read_text(encoding='utf-8'))
(out / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices), encoding='utf-8')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
(out / 'BUILD_INFO.txt').write_text(f'Trad2Simp {__version__}\nCommit: {commit}\nPlatform: Windows x64\n', encoding='utf-8')
lines = []
for name in ('Trad2Simp.exe', 'THIRD_PARTY_NOTICES.txt', 'BUILD_INFO.txt'):
    lines.append(f'{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}')
(out / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='ascii')
