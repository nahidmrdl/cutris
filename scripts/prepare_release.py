"""Validate manual release inputs and prepare versioned, verifiable release metadata.

Inputs are read from environment variables, never evaluated as shell commands.
The GitHub workflow publishes only after the Windows build and all checks pass.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r'(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})\.(0|[1-9][0-9]{0,4})')


def validate_version(value: str) -> str:
    if not VERSION_PATTERN.fullmatch(value) or any(int(part) > 65535 for part in value.split('.')):
        raise ValueError('Version must be three numbers from 0 to 65535, such as 1.0.0 (without v).')
    return value


def parse_notes(value: str) -> list[str]:
    if len(value) > 20000:
        raise ValueError('Release notes must be at most 20,000 characters.')
    if any(ord(character) < 32 and character not in '\t\r\n' for character in value):
        raise ValueError('Release notes contain unsupported control characters.')
    notes = [' '.join(part.split()) for part in value.split(';') if part.strip()]
    if not notes:
        raise ValueError('Enter at least one release note; separate notes with semicolons.')
    return notes


def markdown_text(value: str) -> str:
    """Keep notes as prose: HTML, mentions and Markdown cannot inject page structure."""
    value = re.sub(r'([\\`*_{}\[\]()#+.!|~-])', r'\\\1', value)
    return html.escape(value, quote=False).replace('@', '&#64;')


def artifact_names(executable: str, version: str) -> list[str]:
    validate_version(version)
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,49}', executable):
        raise ValueError('Executable name must use lowercase letters, numbers and hyphens.')
    prefix = f'{executable}-{version}'
    return [f'{prefix}-windows-x64-setup.exe', f'{prefix}-windows-x64-portable.zip',
            f'{prefix}-source.zip', f'cutris-{version}-py3-none-any.whl', 'SHA256SUMS.txt']


def format_notes(notes: list[str], version: str, executable: str, repository: str) -> str:
    names = artifact_names(executable, version)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('GITHUB_REPOSITORY must identify an owner and repository.')
    base = f'https://github.com/{repository}/releases/download/v{version}/'
    rows = [
        (names[0], '**Windows installer**', 'Recommended. Installs the app and shortcuts.'),
        (names[1], 'Portable ZIP', 'Extract and run. No app installation.'),
        (names[2], 'Source ZIP', 'Versioned project source.'),
        (names[3], 'CLI / API wheel', 'Python 3.11–3.13. Runs without the desktop app.'),
        (names[4], 'SHA-256 checksums', 'Verify your download.'),
    ]
    return ('## What\'s new\n\n' + '\n'.join('- ' + markdown_text(note) for note in notes)
            + '\n\n## Downloads\n\n| Download | Details |\n| --- | --- |\n'
            + '\n'.join(f'| [{label}]({base}{name}) | {detail} |' for name, label, detail in rows)
            + '\n\nWindows 10/11 · x64. AI models download separately during setup or first use. '
              'Image processing runs locally and works offline once models are installed.\n')


def prepare(root: Path, version: str, notes_input: str, repository: str, source_sha: str) -> dict:
    validate_version(version)
    notes = parse_notes(notes_input)
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
        raise ValueError('GITHUB_SHA must be the exact 40-character source commit.')
    branding_path = root / 'branding.json'
    branding = json.loads(branding_path.read_text(encoding='utf-8'))
    executable = branding['executable_name']
    names = artifact_names(executable, version)
    body = format_notes(notes, version, executable, repository)
    branding['version'] = version
    branding_text = json.dumps(branding, indent=2, ensure_ascii=False) + '\n'
    branding_path.write_text(branding_text, encoding='utf-8', newline='\n')
    control = root / 'build' / 'release-control'
    control.mkdir(parents=True, exist_ok=True)
    metadata = {'version': version, 'tag': f'v{version}', 'executable': executable,
                'display_name': branding['display_name'], 'source_sha': source_sha,
                'repository': repository, 'branding_text': branding_text,
                'body': body, 'assets': names}
    (control / 'release.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n',
                                          encoding='utf-8', newline='\n')
    (control / 'release-notes.md').write_text(body, encoding='utf-8', newline='\n')
    return metadata


def verify_artifacts(root: Path, metadata: dict) -> dict[str, str]:
    names = artifact_names(metadata['executable'], metadata['version'])
    if metadata['assets'] != names:
        raise ValueError('Release metadata contains unexpected assets.')
    directory = root / 'release'
    actual = {path.name for path in directory.iterdir()}
    if actual != set(names):
        raise ValueError('Release folder must contain exactly the installer, portable, source, wheel and checksums.')
    for name in names:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Release asset is empty or invalid: {name}')
    checksums = {}
    for name in names:
        with (directory / name).open('rb') as stream:
            checksums[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    expected_lines = sorted(f'{checksums[name]}  {name}' for name in names[:-1])
    actual_lines = sorted((directory / names[-1]).read_text(encoding='ascii').splitlines())
    if actual_lines != expected_lines:
        raise ValueError('SHA256SUMS.txt does not match the release assets.')
    prefix = f'{metadata["executable"]}-{metadata["version"]}/'
    with zipfile.ZipFile(directory / names[2]) as archive:
        branding_text = archive.read(prefix + 'branding.json').decode('utf-8')
        if branding_text != metadata['branding_text']:
            raise ValueError('Source archive version metadata does not match the build.')
        if any(name.lower().endswith('.onnx') for name in archive.namelist()):
            raise ValueError('AI model weights must not be included in source releases.')
    with zipfile.ZipFile(directory / names[3]) as archive:
        if archive.read('cutris/resources/branding.json').decode('utf-8') != metadata['branding_text']:
            raise ValueError('Wheel version metadata does not match the build.')
        package_metadata = archive.read(f'cutris-{metadata["version"]}.dist-info/METADATA').decode('utf-8')
        if f'\nVersion: {metadata["version"]}\n' not in package_metadata:
            raise ValueError('Wheel package version does not match the build.')
        if any(name.lower().endswith('.onnx') for name in archive.namelist()):
            raise ValueError('AI model weights must not be included in wheels.')
    return checksums


def finalize(root: Path) -> None:
    control = root / 'build' / 'release-control'
    path = control / 'release.json'
    metadata = json.loads(path.read_text(encoding='utf-8'))
    metadata['sha256'] = verify_artifacts(root, metadata)
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(f'## {metadata["display_name"]} {metadata["version"]}\n\n')
            stream.write('Windows build, release artifact verification and privacy audit passed.\n\n')
            stream.write('The publish job will upload these assets before making the release public.\n\n')
            for name in metadata['assets']:
                stream.write(f'- `{name}`\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finalize', action='store_true', help='Verify completed build artifacts and checksums.')
    args = parser.parse_args()
    if args.finalize:
        finalize(ROOT)
    else:
        metadata = prepare(ROOT, os.environ.get('RELEASE_VERSION', ''), os.environ.get('RELEASE_NOTES', ''),
                           os.environ.get('GITHUB_REPOSITORY', ''), os.environ.get('GITHUB_SHA', ''))
        output = os.environ.get('GITHUB_OUTPUT')
        if output:
            with Path(output).open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(f'version={metadata["version"]}\ntag={metadata["tag"]}\n')
        print(f'Prepared {metadata["display_name"]} {metadata["version"]}.')


if __name__ == '__main__':
    main()
