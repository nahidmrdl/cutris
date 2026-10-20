"""Verify that release scans find identities hidden by artifact compression."""
from io import BytesIO
import zipfile

import pytest

from scripts import privacy_audit


def zip_bytes(name, data):
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return output.getvalue()


def test_findings_redact_private_filenames(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy_audit, 'private_terms', lambda: ['private-owner'])
    source = tmp_path / 'PRIVATE-OWNER.txt'
    source.write_text('Private-Owner', encoding='utf-8')
    findings = privacy_audit.audit([source])
    assert findings
    assert all('private-owner' not in item.casefold() for item in findings)
    assert any('[private]' in item for item in findings)


def test_nested_archive_contents_are_scanned(tmp_path, monkeypatch):
    monkeypatch.setattr(privacy_audit, 'private_terms', lambda: ['private-owner'])
    archive = tmp_path / 'source.zip'
    archive.write_bytes(zip_bytes('nested.zip', zip_bytes('data.txt', b'Private-Owner')))
    findings = privacy_audit.audit([archive])
    assert len(findings) == 1
    assert 'nested.zip:data.txt' in findings[0]


@pytest.mark.parametrize('member_type', ['script', 'pyz'])
def test_portable_zip_scans_compressed_python_archives(tmp_path, monkeypatch, member_type):
    pytest.importorskip('PyInstaller')
    from PyInstaller.archive.writers import CArchiveWriter, ZlibArchiveWriter

    monkeypatch.setattr(privacy_audit, 'private_terms', lambda: ['private-owner'])
    source = tmp_path / 'application.py'
    source.write_text("IDENTITY = 'Private-Owner'\n", encoding='utf-8')
    executable = tmp_path / 'application.exe'
    if member_type == 'script':
        entries = [('application', str(source), True, 's')]
    else:
        pyz = tmp_path / 'application.pyz'
        code = compile(source.read_text(encoding='utf-8'), 'application.py', 'exec')
        ZlibArchiveWriter(str(pyz), [('application', str(source), 'PYMODULE')],
                          {'application': code})
        entries = [('PYZ.pyz', str(pyz), False, 'z')]
    CArchiveWriter(str(executable), entries, 'python312.dll')
    # A superficial scan of compressed executable bytes cannot find the name.
    assert b'private-owner' not in executable.read_bytes().lower()
    archive = tmp_path / 'portable.zip'
    archive.write_bytes(zip_bytes('cutrix/application.exe', executable.read_bytes()))
    findings = privacy_audit.audit([archive])
    assert len(findings) == 1
    assert 'application.exe:application' in findings[0]
