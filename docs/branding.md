# Choosing the app's name

The application is named **cutrix**, written in lowercase. Its display name, executable name, version, and publisher are centralized in `branding.json`.

```json
{
  "display_name": "cutrix",
  "version": "1.0.0",
  "publisher": "cutrix contributors",
  "executable_name": "cutrix"
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
