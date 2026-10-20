# Choosing the app's name

The application is named **cutris**, written in lowercase. Its display name, executable name, version, and publisher are centralized in `branding.json`.

```json
{
  "display_name": "cutris",
  "version": "1.0.0",
  "publisher": "cutris contributors",
  "executable_name": "cutris"
}
```

The publisher uses a generic contributor attribution, with no personal name or email. Use a numeric three-part version such as `1.0.0`. The executable name determines the executable and release filenames; keep it a simple filename without an extension.

Edit the config, restart a source run, and rebuild the app and installer before distributing the change:

```powershell
.\.venv\Scripts\python.exe scripts\build.py --installer
```

The desktop window, editor header/footer, browser title, About dialog, model setup, and release metadata read the configured branding. A source edit does not change a previously built executable.

Internal identifiers intentionally remain stable: `%LOCALAPPDATA%\CutoutStudio`, the `cutout-studio` application ID, installer upgrade ID, and saved-job keys continue to identify the same application. That storage-folder name is an internal compatibility path, not the visible app name. Existing models and batches therefore remain available when branding changes. Keep these internal identifiers stable; changing the storage layout requires explicit migration handling.

Documentation and the project's own copyright attribution are normal text files; review them if the brand changes again. Keep all third-party license texts and upstream author attribution intact.

## Icon artwork

The icon artwork was supplied and approved by the project maintainer. The committed PNG master is re-encoded without the source file's Adobe XMP, EXIF, or other metadata. Fully transparent pixels have no hidden color data.

| File | Purpose |
| --- | --- |
| `packaging/assets/app.png` | 1024 × 1024 transparent PNG master |
| `packaging/assets/app.ico` | Windows EXE, taskbar, window, shortcuts, installer, and model setup icon |
| `web/assets/app.png` | 256 × 256 interface artwork |
| `web/assets/favicon.ico` | Browser tab icon |
| `docs/assets/hero.png` | Repository banner |

To change the icon, import square PNG artwork through the generator. It strips source metadata and creates the master and derived files:

```powershell
.\.venv\Scripts\python.exe scripts/make_icon.py --source path/to/icon.png
.\.venv\Scripts\python.exe scripts/make_repo_assets.py
```

Commit the master and generated files together. Windows builds regenerate the app icons from this master, keeping the chosen artwork across releases. The ICO contains multiple sizes from 16 to 256 pixels for different Windows display scales.
