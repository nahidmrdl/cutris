"""Verify that release scans find identities hidden by artifact compression."""
from io import BytesIO
from types import SimpleNamespace
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


@pytest.fixture
def identity_environment(monkeypatch):
    """Resolve test identities without consulting this machine's account or Git."""
    def configure(*, home=r'C:\Users\runneradmin', username='runneradmin',
                  environment=None, git=None, explicit=''):
        settings = {
            'GITHUB_ACTIONS': 'true',
            'RUNNER_ENVIRONMENT': 'github-hosted',
            'RUNNER_OS': 'Windows',
            'USERNAME': username,
            'CUTOUT_PRIVATE_TERMS': explicit,
            'CI': None,
        }
        settings.update(environment or {})
        for key, value in settings.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        # Return the literal Windows spelling so these checks also run on Unix.
        monkeypatch.setattr(privacy_audit.Path, 'home', classmethod(lambda cls: home))
        identities = git or {}

        def git_config(command, **kwargs):
            assert command[:2] == ['git', 'config']
            key = ('global' if '--global' in command else 'effective', command[-1])
            value = identities.get(key)
            return SimpleNamespace(returncode=0 if value is not None else 1,
                                   stdout=(value + '\n') if value is not None else '')

        monkeypatch.setattr(privacy_audit.subprocess, 'run', git_config)
    return configure


@pytest.mark.parametrize(('home', 'username'), [
    (r'C:\Users\runneradmin', 'runneradmin'),
    ('C:/Users/RUNNERADMIN/', 'RUNNERADMIN'),
    ('c:\\USERS\\RunnerAdmin\\', 'RunnerAdmin'),
])
def test_hosted_runner_upstream_metadata_is_not_a_personal_identity(
        tmp_path, identity_environment, home, username):
    identity_environment(home=home, username=username)
    # Wheel provenance and compiler paths may legitimately contain this public
    # build account in plain text, native binaries, or embedded Python modules.
    artifact = tmp_path / 'portable.zip'
    artifact.write_bytes(zip_bytes('numpy.dist-info/DELVEWHEEL',
        b'Build environment: C:\\Users\\runneradmin\\AppData\\Local\\Temp\\wheel\n'
        + 'C:/Users/runneradmin/build/scipy'.encode('utf-16le')))
    assert privacy_audit.private_terms() == []
    assert privacy_audit.audit([artifact]) == []


@pytest.mark.parametrize(('environment', 'home', 'username'), [
    ({'GITHUB_ACTIONS': None, 'RUNNER_ENVIRONMENT': None, 'RUNNER_OS': None},
     r'C:\Users\runneradmin', 'runneradmin'),
    ({'GITHUB_ACTIONS': None, 'RUNNER_ENVIRONMENT': None, 'RUNNER_OS': None, 'CI': 'true'},
     r'C:\Users\runneradmin', 'runneradmin'),
    ({'GITHUB_ACTIONS': 'false'}, r'C:\Users\runneradmin', 'runneradmin'),
    ({'RUNNER_ENVIRONMENT': None}, r'C:\Users\runneradmin', 'runneradmin'),
    ({'RUNNER_ENVIRONMENT': 'self-hosted'}, r'C:\Users\runneradmin', 'runneradmin'),
    ({'RUNNER_OS': 'Linux'}, r'C:\Users\runneradmin', 'runneradmin'),
    ({}, r'D:\Users\runneradmin', 'runneradmin'),
    ({}, r'C:\Users\private-developer', 'private-developer'),
    ({}, r'C:\Users\runneradmin', 'private-developer'),
])
def test_other_build_environments_keep_account_and_home_protection(
        tmp_path, identity_environment, environment, home, username):
    identity_environment(home=home, username=username, environment=environment)
    terms = privacy_audit.private_terms()
    assert username.casefold() in terms
    assert home.casefold() in terms
    assert home.replace('\\', '/').casefold() in terms
    source = tmp_path / 'build-metadata.txt'
    source.write_text(home + '\n' + username, encoding='utf-8')
    assert privacy_audit.audit([source])


@pytest.mark.parametrize(('scope', 'key', 'identity'), [
    ('effective', 'user.name', 'Private Developer'),
    ('global', 'user.name', 'Private Developer'),
    ('effective', 'user.email', 'private-developer@example.invalid'),
    ('global', 'user.email', 'private-developer@example.invalid'),
    ('effective', 'user.name', 'runneradmin'),
    ('global', 'user.name', 'runneradmin'),
])
def test_hosted_runner_keeps_explicit_git_identities_private(
        tmp_path, identity_environment, scope, key, identity):
    identity_environment(git={(scope, key): identity})
    assert identity.casefold() in privacy_audit.private_terms()
    artifact = tmp_path / 'metadata.zip'
    artifact.write_bytes(zip_bytes('build/config.txt', identity.encode('utf-16le')))
    findings = privacy_audit.audit([artifact])
    assert len(findings) == 1
    assert identity.casefold() not in findings[0].casefold()


@pytest.mark.parametrize('identity', ['runneradmin', 'Private Developer',
                                      r'C:\Users\private-developer'])
def test_hosted_runner_keeps_explicit_private_terms(
        tmp_path, identity_environment, identity):
    identity_environment(explicit=identity)
    assert identity.casefold() in privacy_audit.private_terms()
    source = tmp_path / 'metadata.txt'
    source.write_text(identity, encoding='utf-8')
    assert privacy_audit.audit([source])
