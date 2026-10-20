# Windows setup and troubleshooting

## Install and prepare models

Run the cutris setup executable and launch the app from its shortcut. The installer provides an option to download the AI models during setup. You can defer that download; model setup is also available from the desktop app when a needed model is missing.

Model weights are kept outside the application install folder. This keeps installers smaller and allows installed models to survive an app update. Both BiRefNet models together take approximately 1.2 GB. Allow additional free space for temporary downloads and image batches.

**Maximum detail** uses the general model. **Faster** uses the lite model. The full model is more demanding; choose Faster when memory or processing time is limited. Both use the CPU.

Model setup lets you select either or both models and shows download/verification progress. It checks expected size and a pinned SHA-256 checksum before activating each file. If a download fails, check the internet connection and available disk space, then retry; interrupted downloads can resume. Downloading a replacement does not modify image batches. Close the app before moving or replacing files manually.

To reopen model setup explicitly, run `cutris.exe --setup-models` from the app's installed directory. For a source checkout, use `.\.venv\Scripts\python.exe desktop.py --setup-models`.

Once the required models are installed, background removal and editing work offline. There is no subscription or API-key step.

## System requirements

- 64-bit Windows 10 or 11.
- Microsoft Edge WebView2 Runtime for the desktop window.
- Enough RAM for inference and the source images; 16 GB or more is recommended for Maximum detail and large images.
- Enough disk space for the app, models, normalized originals, cutouts, touch-ups, and exports.

If WebView2 is missing, the installer downloads Microsoft's bootstrapper, checks its signature, and installs the runtime for the current user. This needs an internet connection. For a portable build or a source checkout, use the official [Microsoft WebView2 download](https://developer.microsoft.com/microsoft-edge/webview2/) if needed. The Windows app bundles its Python runtime, so end users do not need a Python installation.

## Saved work and upgrades

Saved jobs and models normally live under `%LOCALAPPDATA%\CutoutStudio`. This stable internal folder name preserves compatibility; the visible app name is cutris. Program updates and uninstalling the executable do not deliberately delete that folder. Back it up before moving computers or changing it manually.

Previous batches reopens saved results. If the app closes while processing, the unfinished batch is paused on restart and can be resumed. A source file that could not be decoded or exceeded the limits needs to be corrected and added again.

## Common issues

| Symptom | Action |
| --- | --- |
| The app asks for a model download | Finish model setup for the selected quality. Existing completed cutouts do not need the model for inspection or editing. |
| A model download fails | Check network access to GitHub, free disk space, and retry. Never rename an incomplete download into an `.onnx` file. |
| The desktop window cannot start | Check that WebView2 is installed. Include the displayed error and app version when reporting a problem. |
| Processing uses a lot of memory | Use Faster, work with smaller batches, or reduce input dimensions. Only one image is processed at a time. |
| A pale detail, glass, or hair is missing | Inspect on a contrasting preview background and use Restore or another pass with Maximum detail. |
| White mode gives an unexpected result | Try Any background / AI only; white-edge refinement is designed for consistently white borders. |
| PNG looks different in another app | Check that the other viewer supports transparency and sRGB. Preview background colors are not exported. |

Unsigned community builds can trigger Windows reputation warnings. Release filenames alone do not establish authenticity; obtain builds from the project's own release page and compare any published checksums.
