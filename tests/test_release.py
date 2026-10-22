"""Release inputs must remain data and published artifacts must match their manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_release import (artifact_names, finalize, format_notes, markdown_text,
                             parse_notes, prepare, validate_version, verify_artifacts)


@pytest.mark.parametrize('value', ['1.0.0', '0.0.0', '12.34.56', '65535.65535.65535'])
def test_valid_release_versions(value):
    assert validate_version(value) == value


@pytest.mark.parametrize('value', ['', 'v1.0.0', '1.0', '1.0.0-beta', '01.0.0', '65536.0.0',
                                  '1.0.0\n', '1.0.0;Write-Host no', '../1.0.0', '1.0.$(whoami)',
                                  '１.0.0', '1.0.0+meta'])
def test_reject_versions_that_are_not_safe_windows_release_numbers(value):
    with pytest.raises(ValueError):
        validate_version(value)


def test_notes_split_semicolons_trim_blanks_and_flatten_lines():
    assert parse_notes('First change;  Second\n change ; ;Third\tchange;') == [
        'First change', 'Second change', 'Third change']


@pytest.mark.parametrize('value', ['', ' ; ;\n', 'x' * 20001, 'a\x00b', 'a\x1bb'])
def test_empty_or_invalid_notes_fail(value):
    with pytest.raises(ValueError):
        parse_notes(value)


def test_notes_escape_html_mentions_and_markdown_without_executing_shell_text():
    notes = parse_notes('Fix <script>alert(1)</script>;Hello @all;[link](javascript:bad);$(Get-Item secret)')
    rendered = format_notes(notes, '1.0.0', 'cutris', 'sample/project')
    assert '<script>' not in rendered
    assert '&lt;script&gt;' in rendered
    assert '@all' not in rendered
    assert '&#64;all' in rendered
    assert '\\[link\\]\\(javascript:bad\\)' in rendered
    assert '$\\(Get\\-Item secret\\)' in rendered
    assert rendered.count('\n- ') == 4
    assert 'https://github.com/sample/project/releases/download/v1.0.0/cutris-1.0.0-windows-x64-setup.exe' in rendered


@pytest.mark.parametrize('executable', ['../cutris', 'Cutris', 'cutris;run', 'cutris/path'])
def test_artifact_names_reject_path_and_shell_characters(executable):
    with pytest.raises(ValueError):
        artifact_names(executable, '1.0.0')


def test_prepare_stamps_only_version_and_writes_release_control(tmp_path):
    branding = {'display_name': 'cutris', 'version': '1.0.0', 'publisher': 'cutris contributors',
                'executable_name': 'cutris'}
    (tmp_path / 'branding.json').write_text(json.dumps(branding), encoding='utf-8')
    metadata = prepare(tmp_path, '1.2.3', 'One; Two', 'sample/project', 'a' * 40)
    stamped = json.loads((tmp_path / 'branding.json').read_text(encoding='utf-8'))
    assert stamped == dict(branding, version='1.2.3')
    assert metadata['tag'] == 'v1.2.3'
    assert metadata['source_sha'] == 'a' * 40
    assert metadata['branding_text'] == (tmp_path / 'branding.json').read_text(encoding='utf-8')
    assert (tmp_path / 'build/release-control/release.json').is_file()
    assert (tmp_path / 'build/release-control/release-notes.md').is_file()


def fixture_release(root):
    branding = {'display_name': 'cutris', 'version': '1.0.0', 'publisher': 'cutris contributors',
                'executable_name': 'cutris'}
    (root / 'branding.json').write_text(json.dumps(branding), encoding='utf-8')
    metadata = prepare(root, '1.2.3', 'One;Two', 'sample/project', 'a' * 40)
    directory = root / 'release'
    directory.mkdir()
    names = metadata['assets']
    (directory / names[0]).write_bytes(b'installer')
    (directory / names[1]).write_bytes(b'portable')
    with zipfile.ZipFile(directory / names[2], 'w') as archive:
        archive.writestr('cutris-1.2.3/branding.json', metadata['branding_text'])
    with zipfile.ZipFile(directory / names[3], 'w') as archive:
        archive.writestr('cutris/resources/branding.json', metadata['branding_text'])
        archive.writestr('cutris-1.2.3.dist-info/METADATA', 'Name: cutris\nVersion: 1.2.3\n')
    write_checksums(directory, names)
    return metadata


def write_checksums(directory, names):
    lines = [f'{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}' for name in names[:-1]]
    (directory / names[-1]).write_text('\n'.join(sorted(lines)) + '\n', encoding='ascii')


def test_finalize_records_hashes_for_every_asset(tmp_path, monkeypatch):
    metadata = fixture_release(tmp_path)
    summary = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    finalize(tmp_path)
    result = json.loads((tmp_path / 'build/release-control/release.json').read_text(encoding='utf-8'))
    assert set(result['sha256']) == set(metadata['assets'])
    assert 'Windows build' in summary.read_text(encoding='utf-8')


def test_release_rejects_modified_asset_after_checksums_written(tmp_path):
    metadata = fixture_release(tmp_path)
    (tmp_path / 'release' / metadata['assets'][0]).write_bytes(b'changed installer')
    with pytest.raises(ValueError, match='SHA256SUMS'):
        verify_artifacts(tmp_path, metadata)


def test_release_rejects_unexpected_files(tmp_path):
    metadata = fixture_release(tmp_path)
    (tmp_path / 'release' / 'private.txt').write_text('private', encoding='utf-8')
    with pytest.raises(ValueError, match='exactly'):
        verify_artifacts(tmp_path, metadata)


def test_release_rejects_wrong_wheel_version(tmp_path):
    metadata = fixture_release(tmp_path)
    names = metadata['assets']
    with zipfile.ZipFile(tmp_path / 'release' / names[3], 'w') as archive:
        archive.writestr('cutris/resources/branding.json', '{}')
    write_checksums(tmp_path / 'release', names)
    with pytest.raises(ValueError, match='Wheel version'):
        verify_artifacts(tmp_path, metadata)


@pytest.mark.parametrize('add_model', [False, True])
def test_release_rejects_wrong_source_version_or_embedded_model(tmp_path, add_model):
    metadata = fixture_release(tmp_path)
    names = metadata['assets']
    with zipfile.ZipFile(tmp_path / 'release' / names[2], 'w') as archive:
        archive.writestr('cutris-1.2.3/branding.json', metadata['branding_text'] if add_model else '{}')
        if add_model:
            archive.writestr('cutris-1.2.3/models/weights.onnx', b'weights')
    write_checksums(tmp_path / 'release', names)
    with pytest.raises(ValueError, match='model weights|version metadata'):
        verify_artifacts(tmp_path, metadata)
