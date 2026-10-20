# Privacy and local storage

cutrix performs image decoding, AI inference, refinement, editing, and export on the local computer. The application contains no account system, analytics, cloud image processing, or automatic upload of images.

## Network access

The app's interface communicates with its own local service on `127.0.0.1`. The desktop launcher chooses a local port. This service uses host/origin checks and a per-session token for changes. It is intended for one local user and is not an internet-facing service.

The desktop app downloads missing model weights from the rembg GitHub release. HTTPS downloads can follow redirects to GitHub's asset delivery infrastructure. Those providers receive normal connection metadata such as IP address. No source images or batch contents are sent with model downloads.

The installer also downloads Microsoft's WebView2 bootstrapper if the runtime is missing, checks its Microsoft signature, and installs the runtime. This contacts Microsoft and its delivery infrastructure. Microsoft Edge WebView2 is a separate Microsoft runtime with its own policies; cutrix does not add analytics to it.

## Local files

The installed Windows app stores models and working files under:

```text
%LOCALAPPDATA%\CutoutStudio\
```

This is a placeholder resolved for the current user; no developer's account path is embedded in it. `CutoutStudio` is a stable internal storage key retained for compatibility, while the app's visible name is cutrix. Model weights live in `models`, saved batches in `data\jobs`, and the desktop browser's local profile in `data\webview`.

Saved batches contain normalized copies of selected source images, automatically processed cutouts, saved touch-ups, thumbnails, filenames, processing settings, and job status. Input files are read without being overwritten. Exported PNGs omit original EXIF/DPI metadata, but export names and batch manifests may still include original filenames.

Files remain on disk until removed. Close cutrix before manually deleting saved job folders. Back up anything important first. Uninstalling the program does not automatically erase working images and downloaded models. To remove all app data after uninstalling, delete the application-data folder yourself.

Source runs keep their `data` and `models` in the source folder. These are private working files and are excluded from publication. `CUTOUT_HOME` can select another working root; `CUTOUT_DATA` and `CUTOUT_MODELS` can override the corresponding locations for development and testing.

## Before sharing files or reporting problems

- Export only the images you intend to share. Review filenames and the ZIP manifest if those names are sensitive.
- Logs, screenshots, or copied error messages can contain local filenames or paths. Review them before publishing an issue.
- Publish the prepared source archive or the project source files; do not upload a complete working folder containing saved batches, backups, or model caches.
- Git commit names, emails, and hosting-account details are controlled separately by Git and the hosting service. Repository contents do not hide an account's public profile or commit metadata.

Upstream copyright notices identify the upstream authors as required by their licenses. Those notices do not identify the person distributing a customized copy of cutrix.
