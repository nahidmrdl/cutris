# Build through scripts/build.py so release notices and the icon exist first.
from pathlib import Path
import json
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPECPATH).parent
executable_name = json.loads((root / 'branding.json').read_text(encoding='utf-8'))['executable_name']
stage = root / 'build' / 'release-input'
datas = [(str(root / 'web'), 'web'), (str(stage / 'licenses'), 'licenses'),
         (str(root / 'packaging' / 'assets' / 'app.ico'), 'packaging/assets')]
if (root / 'docs').is_dir():
    datas.append((str(root / 'docs'), 'docs'))
for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md', 'branding.json'):
    datas.append((str(root / name), '.'))
datas += collect_data_files('webview')
datas += collect_data_files('onnxruntime', includes=['LICENSE', 'ThirdPartyNotices.txt'])
binaries = collect_dynamic_libs('onnxruntime')

a = Analysis(
    [str(root / 'desktop.py')], pathex=[str(root)],
    binaries=binaries, datas=datas,
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                   'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets.auto',
                   'uvicorn.lifespan.on', 'webview.platforms.winforms', 'clr', 'pythonnet'],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'cefpython3', 'pytest',
              'IPython', 'matplotlib', 'pandas', 'notebook'],
    noarchive=False, optimize=0,
)
# This app uses only OpenCV image processing. Video/FFmpeg is never used.
# Do not redistribute the unused LGPL video plugin in this still-image app.
def keep(entry):
    return not Path(entry[0]).name.lower().startswith('opencv_videoio_ffmpeg')
a.binaries = [entry for entry in a.binaries if keep(entry)]
a.datas = [entry for entry in a.datas if keep(entry)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name=executable_name,
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=True,
    icon=str(root / 'packaging' / 'assets' / 'app.ico'),
    version=str(root / 'packaging' / 'windows-version.txt'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=executable_name)
