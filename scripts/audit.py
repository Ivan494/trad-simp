"""Conservative release privacy checks. Findings never print matched values."""
import argparse
import marshal
from pathlib import Path
import re
import subprocess
import types

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'credential': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)'),
    'personal path': re.compile(rb'(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]+Users[\\/]+|/Users/|/home/)([^\\/\s\x00"\']+)', re.I),
    'email': re.compile(rb'[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
}
PUBLIC_EMAILS = (b'@users.noreply.github.com', b'noreply@github.com', b'cursoragent@cursor.com')
PUBLIC_USERS = {b'Private', b'Synthetic', b'runneradmin', b'runner', b'RUNNER~1', b'Public'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def inspect(data, label, emails=True):
    issues = []
    for kind, pattern in PATTERNS.items():
        if kind == 'email' and not emails:
            continue
        for match in pattern.finditer(data):
            if kind == 'email' and any(match.group().endswith(suffix) for suffix in PUBLIC_EMAILS):
                continue
            if kind == 'personal path' and match.group(1) in PUBLIC_USERS:
                continue
            issues.append(f'{label}: {kind}')
            break
    return issues


def source_audit():
    issues = []
    paths = git('ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
    for name in filter(None, paths):
        path = ROOT / name
        if not path.is_file():
            continue
        if name.startswith('vendor/') or name == 'scripts/audit.py':
            continue  # upstream attribution retained; audit rules contain samples
        if path.suffix in ('.png', '.jpg') or path.name in ('config.json', 'log.txt', '.env'):
            issues.append(f'{name}: local capture/config must not be distributed')
        issues += inspect(path.read_bytes(), name)
    # All reachable blobs, including old branches/tags; no history rewriting.
    for line in git('rev-list', '--objects', '--all').decode().splitlines():
        sha, _, name = line.partition(' ')
        if not name or name.startswith('vendor/') or name == 'scripts/audit.py':
            continue
        if git('cat-file', '-t', sha).strip() == b'blob':
            issues += inspect(git('cat-file', 'blob', sha), f'history {sha[:8]}')
    issues += inspect(git('log', '--all', '--format=%ae%n%ce%n%B'), 'commit metadata')
    return issues


def artifact_audit(path):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(path))
    issues = []
    def code_check(code, label):
        if not isinstance(code, types.CodeType):
            return
        issues.extend(inspect(code.co_filename.encode(), label, emails=False))
        for item in code.co_consts:
            if isinstance(item, types.CodeType):
                code_check(item, label)
            elif isinstance(item, str):
                issues.extend(inspect(item.encode(), label, emails=False))
    for name, entry in archive.toc.items():
        if name.endswith(('.png', '.json', '.txt')) and ('config' in name or 'log.txt' in name):
            issues.append(f'archive {name}: unexpected runtime data')
        if entry[-1] == 's':
            code_check(marshal.loads(archive.extract(name)), f'archive {name}')
        elif entry[-1] == 'z':
            pyz = archive.open_embedded_archive(name)
            for module in pyz.toc:
                code_check(pyz.extract(module), f'module {module}')
    return issues


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path)
    args = parser.parse_args()
    findings = artifact_audit(args.artifact) if args.artifact else source_audit()
    for finding in sorted(set(findings)):
        print(finding)
    print(f'Privacy audit: {len(set(findings))} findings')
    raise SystemExit(bool(findings))
