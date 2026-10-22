"""Build auditable Windows releases. Run with the project's build environment.

Examples: python scripts/build.py --installer
          python scripts/build.py --source-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from collect_licenses import collect
from make_icon import make_assets
from privacy_audit import audit

ROOT = Path(__file__).resolve().parents[1]
BRANDING = json.loads((ROOT / 'branding.json').read_text(encoding='utf-8'))
VERSION = BRANDING['version']
EXECUTABLE = BRANDING['executable_name']
RELEASE = ROOT / 'release'
SOURCE_FILES = (
    '.gitattributes', '.gitignore', 'LICENSE', 'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'THIRD_PARTY_NOTICES.md', 'VALIDATION.md', 'branding.json',
    'requirements.txt', 'requirements-dev.txt', 'requirements-desktop.txt', 'requirements-build.txt', 'requirements-release.txt',
    'engine.py', 'image_geometry.py', 'server.py', 'launch.py', 'desktop.py', 'app_paths.py', 'model_manager.py', 'model_setup_ui.py',
    'setup.py', 'pyproject.toml', 'MANIFEST.in', 'Setup.cmd', 'Start.cmd', 'Start-browser.cmd',
)
SOURCE_DIRECTORIES = ('cutris', 'web', 'docs', 'tests', 'packaging', 'scripts', '.github')
DISALLOWED_PARTS = {'__pycache__', '.pytest_cache', '.venv', '.git', 'data', 'models', 'backups',
                    'example-results', 'node_modules'}
DISALLOWED_SUFFIXES = {'.pyc', '.pyo', '.log', '.onnx', '.download', '.bak', '.psd', '.psb'}


def run(command, *, log=None, **kwargs):
    command = [str(part) for part in command]
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w', encoding='utf-8') as output:
            subprocess.run(command, cwd=ROOT, check=True, stdout=output, stderr=subprocess.STDOUT, **kwargs)
    else:
        subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def check_privacy(paths):
    findings = audit(paths)
    if findings:
        raise RuntimeError('Release privacy audit failed:\n' + '\n'.join(findings))


def source_files():
    files = {ROOT / name for name in SOURCE_FILES if (ROOT / name).is_file()}
    for name in SOURCE_DIRECTORIES:
        directory = ROOT / name
        if not directory.is_dir():
            continue
        for path in directory.rglob('*'):
            relative = path.relative_to(ROOT)
            if (path.is_file() and not path.is_symlink()
                    and not any(part in DISALLOWED_PARTS for part in relative.parts)
                    and relative.as_posix() != 'packaging/windows-version.txt'
                    and path.suffix.lower() not in DISALLOWED_SUFFIXES):
                files.add(path)
    return sorted(files)


def archive_sources():
    files = source_files()
    check_privacy(files)
    output = RELEASE / f'{EXECUTABLE}-{VERSION}-source.zip'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            name = f'{EXECUTABLE}-{VERSION}/' + path.relative_to(ROOT).as_posix()
            archive.write(path, name)
    check_privacy([output])
    return output


def compiler_path(explicit):
    paths = [explicit, os.environ.get('ISCC'), shutil.which('ISCC'),
             ROOT / 'build' / 'tools' / 'inno' / 'ISCC.exe']
    for parent in (os.environ.get('ProgramFiles(x86)', ''), os.environ.get('ProgramFiles', ''),
                   os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')):
        paths.extend(Path(parent) / f'Inno Setup {version}' / 'ISCC.exe' for version in ('7', '6'))
    for value in paths:
        if value and Path(value).is_file():
            return Path(value)
    raise RuntimeError('Inno Setup compiler not found. Install Inno Setup or pass --iscc PATH.')


def build_binary(installer, compiler, verify_runtime=False):
    if sys.platform != 'win32' or sys.maxsize <= 2**32:
        raise RuntimeError('Build this Windows x64 release with 64-bit Python on Windows.')
    collect(ROOT / 'build' / 'release-input' / 'licenses')
    make_assets(ROOT)
    from make_version_info import make_version_info
    make_version_info(ROOT / 'branding.json', ROOT / 'packaging' / 'windows-version.txt')
    print('Freezing the Windows application (details in build/pyinstaller-build.log)...', flush=True)
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
         '--workpath', ROOT / 'build' / 'pyinstaller', '--distpath', ROOT / 'dist',
         ROOT / 'packaging' / 'cutout-studio.spec'], log=ROOT / 'build' / 'pyinstaller-build.log')
    bundle = ROOT / 'dist' / EXECUTABLE
    if any(bundle.rglob('*.onnx')) or any(bundle.rglob('opencv_videoio_ffmpeg*.dll')):
        raise RuntimeError('The binary must not embed AI models or unused FFmpeg DLLs.')
    check_privacy([bundle])
    # Frozen execution verifies image codecs, numerical libraries, native ONNX and web assets.
    report = ROOT / 'build' / 'frozen-self-test.json'
    test_home = ROOT / 'build' / 'self-test-home'
    test_env = dict(os.environ, CUTOUT_HOME=str(test_home))
    # Do not inherit a developer's alternate model/data locations in a clean-runtime check.
    test_env.pop('CUTOUT_DATA', None)
    test_env.pop('CUTOUT_MODELS', None)
    if verify_runtime:
        print('Verifying the bundled application...', flush=True)
        run([bundle / f'{EXECUTABLE}.exe', '--self-test', '--report', report], env=test_env, timeout=120)
        if not report.is_file():
            raise RuntimeError('The frozen executable did not produce a self-test report.')
        result = json.loads(report.read_text(encoding='utf-8'))
        if not result.get('ok'):
            raise RuntimeError('The frozen application self-test failed; inspect the local build report.')
    portable = RELEASE / f'{EXECUTABLE}-{VERSION}-windows-x64-portable.zip'
    with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                archive.write(path, EXECUTABLE + '/' + path.relative_to(bundle).as_posix())
    artifacts = [portable]
    if installer:
        print('Compiling Windows Setup (details in build/installer-build.log)...', flush=True)
        run([compiler_path(compiler), f'/DAppVersion={VERSION}',
             f'/DAppName={BRANDING["display_name"]}', f'/DAppPublisher={BRANDING["publisher"]}',
             f'/DAppExeName={EXECUTABLE}',
             f'/DProjectRoot={ROOT}',
             ROOT / 'packaging' / 'windows-installer.iss'], log=ROOT / 'build' / 'installer-build.log')
        setup = RELEASE / f'{EXECUTABLE}-{VERSION}-windows-x64-setup.exe'
        check_privacy([setup])
        artifacts.append(setup)
    return artifacts


def checksums(artifacts):
    output = RELEASE / 'SHA256SUMS.txt'
    lines = []
    for path in sorted(artifacts):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        lines.append(f'{digest}  {path.name}')
    output.write_text('\n'.join(lines) + '\n', encoding='ascii')


def build_wheel():
    output = RELEASE / f'cutris-{VERSION}-py3-none-any.whl'
    run([sys.executable, '-m', 'pip', 'wheel', '.', '--no-deps', '--no-build-isolation',
         '--disable-pip-version-check', '--wheel-dir', RELEASE], log=ROOT / 'build' / 'wheel-build.log')
    if not output.is_file():
        raise RuntimeError('The standalone CLI/API wheel was not built.')
    check_privacy([output])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', action='store_true', help='Also compile the Windows Setup EXE.')
    parser.add_argument('--source-only', action='store_true', help='Only package clean publishable source.')
    parser.add_argument('--verify-runtime', action='store_true', help='Opt in to the bundled runtime smoke check.')
    parser.add_argument('--iscc', help='Optional path to Inno Setup ISCC.exe.')
    args = parser.parse_args()
    RELEASE.mkdir(exist_ok=True)
    artifacts = []
    if not args.source_only:
        artifacts += build_binary(args.installer, args.iscc, args.verify_runtime)
        artifacts.append(build_wheel())
    artifacts.append(archive_sources())
    checksums(artifacts)
    print('Release artifacts:')
    for path in artifacts:
        print('  ' + path.name)
    print('All release privacy checks passed. SHA256SUMS.txt written.')


if __name__ == '__main__':
    main()
