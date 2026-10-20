# Building and publishing a release

## Publish with GitHub Actions

The first release and later updates use the same workflow. No release is published just by pushing source.

1. Push the source changes to the repository's default branch.
2. Open **Actions → Release cutrix → Run workflow** on that branch.
3. Enter the **version**, such as `1.0.0`, without a `v` prefix.
4. Enter **release notes** as sentences separated by semicolons, then run the workflow.

For example:

```text
First public release;Batch background removal with BiRefNet;Manual Erase, Restore, and Magic wand tools
```

The release page formats those notes as:

- First public release
- Batch background removal with BiRefNet
- Manual Erase, Restore, and Magic wand tools

The workflow tests, builds, verifies the frozen executable, collects licenses, and audits the publication payload. It then uploads these assets to a GitHub release:

| Asset | Use |
| --- | --- |
| `cutrix-1.0.0-windows-x64-setup.exe` | Windows installer; models download separately. |
| `cutrix-1.0.0-windows-x64-portable.zip` | App bundle without an installer. |
| `cutrix-1.0.0-source.zip` | Clean source for this version. |
| `SHA256SUMS.txt` | SHA-256 checksums for all three files. |

The selected version is stamped into a release snapshot and tagged `v1.0.0`; the default branch is not changed. Enter the next version in the workflow for each update. Published versions and existing tags are never overwritten.

A release stays a draft until every asset uploads successfully. If publishing fails, inspect the workflow logs and any unpublished draft. Delete that failed draft before rerunning the same version. Successful build artifacts are also available from the workflow run. Clean-machine checks below remain manual.

## Build locally

Build Windows executables on 64-bit Windows. Start from a clean source copy and keep private images, saved jobs, models, local logs, credentials, and backups outside the publication payload.

The release tooling packages a standalone app with its Python runtime and builds a Windows installer. Model weights are downloaded separately after installation or during the optional setup task. They are never copied into the executable payload.

## Build commands

After the source environment has been created by `Setup.cmd`, run these commands from PowerShell in the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-build.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build.py --installer
```

The installer build requires the Inno Setup compiler. The script finds an installed Inno Setup 7 or 6, the `ISCC` environment setting, or a local build-tools compiler. To select a compiler explicitly:

```powershell
.\.venv\Scripts\python.exe scripts\build.py --installer --iscc "C:\Path\To\ISCC.exe"
```

Without `--installer`, the build produces the app bundle, portable ZIP, source ZIP, and checksums. To prepare only the clean source archive:

```powershell
.\.venv\Scripts\python.exe scripts\build.py --source-only
```

Output for version 1.0.0:

| File | Purpose |
| --- | --- |
| `dist\cutrix\cutrix.exe` | Standalone desktop app; keep its neighboring files with it. |
| `release\cutrix-1.0.0-windows-x64-setup.exe` | Per-user installer; optional model setup runs after program files are copied. |
| `release\cutrix-1.0.0-windows-x64-portable.zip` | Entire app bundle without an installer. It still uses the user's application-data directory. |
| `release\cutrix-1.0.0-source.zip` | Allowlisted source only, excluding private local working files. |
| `release\SHA256SUMS.txt` | SHA-256 checksums for generated release assets. |

The build audits the payload for the current workstation account, configured Git identity, and home path. Optional `CUTOUT_PRIVATE_TERMS`, with one term per line, adds names or emails to check. It examines source ZIP contents and embedded Python archives as well as ordinary binary files. To rerun the audit:

```powershell
.\.venv\Scripts\python.exe scripts\privacy_audit.py dist\cutrix release
```

The audit reports file labels instead of printing the private values. Review release contents yourself as well, especially any new screenshots or fixtures.

## Release checks

1. Install the pinned source and build dependencies and run the automated tests.
2. Build the desktop application, collect bundled dependency license texts, and compile the installer.
3. Check the generated source archive and app bundle for personal paths, credentials, private images, and unintended files. Use the prepared source archive rather than zipping the whole working directory.
4. Test on a clean Windows account or machine without Python installed. Verify first launch, model download, cancelled/failed download recovery, offline inference, manual edits, PNG/ZIP export, reopen, upgrade, and uninstall behavior.
5. Retain the application license, third-party notices, and generated dependency license directory in every binary release.

Build artifacts and archives are excluded by `.gitignore`. The clean-machine checks above are manual release checks; a successful build alone does not establish that they have been performed.

## Publishing source

The project license uses the generic attribution **cutrix contributors**. No personal author name or email is required in source headers. Required upstream author names and copyright notices must remain.

Before the first commit, configure the author identity you intend to make public. A hosting service's no-reply address can be used instead of a personal email. The repository's `.gitignore` controls untracked files; it does not remove a file already committed or rewrite old history. Check both the staged file list and any existing history before publishing.

Keep large model weights out of normal Git history. The source repository contains the model source URLs, fixed checksums, downloader, and upstream legal notices. Add installer binaries and checksums as release assets rather than committing them to the source tree.

## Signing and versioning

Use the project's version consistently in the executable and installer. Unsigned builds remain functional but may show Windows reputation warnings. Code signing requires a publisher identity and a certificate; choose those separately when preparing a public signed release. Do not embed a personal certificate or private signing key in the repository.

## Bundled components

`THIRD_PARTY_NOTICES.md` records BiRefNet/rembg attribution and explains binary dependencies. `scripts\collect_licenses.py` copies the installed dependency notices into the bundle's `_internal\licenses` directory, including `runtime-packages.json`, Python's license, and the PyInstaller bootloader exception. The inventory and license copies must match the exact environment used for the build. Native components bundled inside wheels retain their licenses as well as the Python package licenses.

The build excludes OpenCV's unused FFmpeg video DLL from this still-image app while retaining the complete OpenCV wheel notices. If that exclusion changes or another LGPL component is bundled, review the exact redistribution and corresponding-source obligations before publishing. Changing package versions can change bundled components.

Downloading models separately does not remove their license obligations. Preserve BiRefNet attribution alongside the app and model setup.
