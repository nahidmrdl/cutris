"""Collect actual runtime wheel licenses and native notices into a release folder."""
from __future__ import annotations

from importlib import metadata
from pathlib import Path
import json
import shutil
import sys

from packaging.requirements import Requirement

ROOT_PACKAGES = ('fastapi', 'uvicorn', 'python-multipart', 'Pillow', 'numpy', 'scipy',
                 'onnxruntime', 'opencv-python-headless', 'pywebview',
                 # cffi's optional compiler imports are collected by PyInstaller.
                 'setuptools')


def runtime_distributions():
    pending = list(ROOT_PACKAGES)
    seen = set()
    while pending:
        distribution = metadata.distribution(pending.pop())
        name = distribution.metadata['Name']
        key = name.lower().replace('_', '-')
        if key in seen:
            continue
        seen.add(key)
        yield distribution
        for text in distribution.requires or ():
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                pending.append(requirement.name)


def collect(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    packages = []
    for distribution in sorted(runtime_distributions(), key=lambda d: d.metadata['Name'].lower()):
        name, version = distribution.metadata['Name'], distribution.version
        package_dir = destination / f'{name}-{version}'
        notices = []
        for entry in distribution.files or ():
            path = Path(str(entry))
            if '..' in path.parts:
                continue
            lower = path.name.lower()
            if ('licenses' not in [p.lower() for p in path.parts]
                    and not any(word in lower for word in ('license', 'licence', 'copying', 'notice', 'copyright'))):
                continue
            source = Path(distribution.locate_file(entry))
            if not source.is_file() or source.suffix.lower() in ('.py', '.pyc', '.pyd', '.dll'):
                continue
            target = package_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            notices.append(target.relative_to(destination).as_posix())
        if not notices:
            fallback = Path(__file__).resolve().parents[1] / 'packaging' / 'licenses' / f'{name}-LICENSE.txt'
            if fallback.is_file():
                package_dir.mkdir(parents=True, exist_ok=True)
                target = package_dir / 'LICENSE.txt'
                shutil.copyfile(fallback, target)
                notices.append(target.relative_to(destination).as_posix())
        if not notices:
            # Legacy wheels occasionally contain only their license in METADATA.
            license_text = distribution.metadata.get('License', '').strip()
            if len(license_text) > 400:
                package_dir.mkdir(parents=True, exist_ok=True)
                target = package_dir / 'LICENSE.txt'
                target.write_text(license_text + '\n', encoding='utf-8')
                notices.append(target.relative_to(destination).as_posix())
            else:
                raise RuntimeError(f'No full license text found for {name}; resolve before release.')
        packages.append({'name': name, 'version': version, 'notices': notices})
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Python LICENSE.txt was not found.')
    shutil.copyfile(python_license, destination / 'Python-LICENSE.txt')
    tcl_license = Path(__file__).resolve().parents[1] / 'packaging' / 'licenses' / 'Tcl-LICENSE.txt'
    shutil.copyfile(tcl_license, destination / 'Tcl-LICENSE.txt')
    for license_file in (Path(sys.base_prefix) / 'tcl').glob('tk*/license.terms'):
        shutil.copyfile(license_file, destination / 'Tk-LICENSE.txt')
    for license_file in (Path(__file__).resolve().parents[1] / 'packaging' / 'licenses').glob('*.txt'):
        shutil.copyfile(license_file, destination / license_file.name)
    # Preserve the PyInstaller bootloader exception for its distributed executable.
    import PyInstaller
    pyinstaller_license = Path(PyInstaller.__file__).parent / 'COPYING.txt'
    if pyinstaller_license.is_file():
        shutil.copyfile(pyinstaller_license, destination / 'PyInstaller-COPYING.txt')
    (destination / 'runtime-packages.json').write_text(json.dumps(packages, indent=2) + '\n', encoding='utf-8')
    (destination / 'README.txt').write_text(
        'These are unmodified license texts and third-party notices from the runtime wheels.\n'
        'Third-party copyright holders retain their names and rights.\n'
        'The unused OpenCV FFmpeg video DLL is excluded from this still-image application.\n'
        'OpenCV bundled third-party notices are retained in full for attribution.\n', encoding='utf-8')
    return packages


if __name__ == '__main__':
    collect(Path(__file__).resolve().parents[1] / 'build' / 'release-input' / 'licenses')
