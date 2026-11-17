"""Generate Windows version metadata from the canonical Python version."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trad2simp.version import __version__


def write_version_info(destination):
    version = tuple(map(int, __version__.split('.'))) + (0,)
    text = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={version!r}, prodvers={version!r},
    mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Traditional / Simplified Chinese Converter'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('ProductName', 'Trad2Simp'),
    StringStruct('ProductVersion', '{__version__}'),
    StringStruct('OriginalFilename', 'Trad2Simp.exe'),
    StringStruct('LegalCopyright', 'Copyright (c) 2026 Ivan494; MIT')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
'''
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(text, encoding='utf-8')


if __name__ == '__main__':
    write_version_info('build/version_info.txt')
