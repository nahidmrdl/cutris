"""Audit source/releases for this workstation's identity without printing its value.

The audit keeps third-party attribution intact. It checks the current account,
home paths, configured Git identity, and optional CUTOUT_PRIVATE_TERMS (one per line).
It also opens ZIPs and decompresses PyInstaller embedded Python archives.
The canonical GitHub-hosted Windows account is not a personal identity; its
upstream wheel metadata is allowed unless explicitly listed as a private term.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import marshal
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import zipfile


def private_terms() -> list[str]:
    home = str(Path.home())
    username = os.environ.get('USERNAME', '')
    hosted_windows_account = (
        os.environ.get('GITHUB_ACTIONS') == 'true'
        and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
        and os.environ.get('RUNNER_OS') == 'Windows'
        and username.casefold() == 'runneradmin'
        and home.replace('\\', '/').rstrip('/').casefold() == 'c:/users/runneradmin'
    )
    # Third-party Windows wheels contain this same public build account. Never
    # suppress a developer's account, a self-hosted runner, or explicit terms.
    values = set() if hosted_windows_account else {home, home.replace('\\', '/'), username}
    for key in ('user.name', 'user.email'):
        for scope in ((), ('--global',)):
            try:
                result = subprocess.run(['git', 'config', *scope, '--get', key], capture_output=True,
                                        text=True, check=False)
            except FileNotFoundError:
                continue
            if result.returncode == 0:
                values.add(result.stdout.strip())
    values.update(os.environ.get('CUTOUT_PRIVATE_TERMS', '').splitlines())
    return sorted({value.casefold() for value in values if len(value.strip()) >= 4})


def patterns(terms):
    return [term.encode(encoding) for term in terms for encoding in ('utf-8', 'utf-16le')]


def audit(paths: list[Path]) -> list[str]:
    terms = private_terms()
    needles = patterns(terms)
    failures = []

    def report(label: str, reason: str):
        # A finding must not repeat the identity that was discovered in a filename.
        for term in sorted(terms, key=len, reverse=True):
            label = re.sub(re.escape(term), '[private]', label, flags=re.IGNORECASE)
        failures.append(label + ': ' + reason)

    def examine_executable(path: Path, label: str):
        from PyInstaller.archive.readers import CArchiveReader
        from PyInstaller.loader.pyimod01_archive import ArchiveReadError
        try:
            archive = CArchiveReader(str(path))
        except ArchiveReadError:
            # Ordinary installer/prerequisite executables have no Python archive.
            return
        for name, info in archive.toc.items():
            examine(name.encode(), label + ': embedded member name')
            if info[-1] == 'z':
                pyz = archive.open_embedded_archive(name)
                for module in pyz.toc:
                    code = pyz.extract(module)
                    if code is not None:
                        examine(marshal.dumps(code), label + ':' + module)
            elif info[-1] in ('s', 'm', 'M'):
                examine(archive.extract(name), label + ':' + name)

    def examine(data: bytes, label: str, depth=0, *, executable=False):
        lower = data.lower()
        # Public repository links are deliberate references, not workstation
        # identity leaks. Keep account/path checks everywhere outside those URLs.
        lower = re.sub(rb'https://github\.com/[a-z0-9_-]+/[a-z0-9_.-]+',
                       b'https://github.com/[public-repository]', lower)
        if any(needle in lower for needle in needles):
            report(label, 'private identity or workstation path detected')
        if executable:
            # PyInstaller's reader requires a real path. Inspect the decompressed
            # EXE in a private temporary directory, including its compressed PYZ.
            with TemporaryDirectory(prefix='cutris-audit-') as directory:
                path = Path(directory) / 'application.exe'
                path.write_bytes(data)
                examine_executable(path, label)
        if depth < 3 and data.startswith(b'PK\x03\x04'):
            try:
                with zipfile.ZipFile(BytesIO(data)) as archive:
                    for entry in archive.infolist():
                        examine(entry.filename.encode(), label + ': archive member name', depth + 1)
                        if not entry.is_dir():
                            examine(archive.read(entry), label + ':' + entry.filename, depth + 1,
                                    executable=Path(entry.filename).suffix.lower() == '.exe')
            except zipfile.BadZipFile:
                report(label, 'unreadable ZIP archive')

    for base in paths:
        candidates = base.rglob('*') if base.is_dir() else [base]
        for path in candidates:
            if not path.is_file():
                continue
            label = path.relative_to(base).as_posix() if base.is_dir() else path.name
            examine(label.encode(), label + ': filename')
            examine(path.read_bytes(), label)
            if path.suffix.lower() == '.exe':
                examine_executable(path, label)
    return failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args()
    problems = audit(args.paths)
    for problem in problems:
        print(problem)
    print(f'Privacy audit: {len(problems)} finding(s). Identity values are never printed.')
    raise SystemExit(bool(problems))
