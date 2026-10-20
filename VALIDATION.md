# Validation

The Windows desktop release is checked with synthetic images and isolated working folders. Private artwork and existing saved batches are not part of the release test inputs.

## Automated regression

The regression suite covers image decoding and metadata, existing transparency, white-edge refinement, general-background fallback, erase/restore and wand replay, reversible crop/resize, alpha-safe resampling, original preservation, upload limits, batch ordering, pause/resume/retry, PNG and ZIP output, local request protection, model integrity, resumable downloads, cancellation, and desktop lifecycle.

Run from the source environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests need working Windows loopback sockets. A restricted test runner that blocks asyncio socket initialization must allow local loopback for the server tests.

## Native renderer check

`tests/native_smoke.py` exercises the actual WebView2 renderer with a generated fixture: local native bridge, custom icon and favicon, general-background default, desktop layout, real AI processing, saved touch-up, exported alpha, ordered ZIP, About/licenses, and saved-batch history.

Use disposable storage and an explicit local report path:

```powershell
$env:CUTOUT_HOME = Join-Path $PWD 'build\native-smoke-home'
.\.venv\Scripts\python.exe tests\native_smoke.py build\native-smoke.json
```

For a second run, use another empty test home so the history check remains isolated. The test reuses verified source-checkout models without bundling them.

`tests/native_geometry_smoke.py` checks Auto crop, manual crop, resizing, preview and export dimensions, cancel/reset behavior, and continued touch-ups in the actual renderer. It uses generated transparent artwork and a separate disposable `CUTOUT_HOME`.

`tests/native_layout_smoke.py` checks editing, wand and export controls without page scrolling across eight desktop window sizes, including 900 × 660, 1920 × 1080, and the initial 1232 × 656 window for a 1280 × 720 display, plus two narrow layouts. It also verifies visible crop dialog actions, Auto crop on opening, automatic transitions to Manual mode, and accessible icon close buttons. Window dimensions include the native frame; the report records the actual content viewport.

```powershell
$env:CUTOUT_HOME = Join-Path $PWD 'build\native-layout-home'
.\.venv\Scripts\python.exe tests\native_layout_smoke.py build\native-layout.json
```

## Packaged runtime

The release build runs the frozen executable's self-test for static assets, the shipped Windows and interface icons, the local server, image decoding, numerical/native runtime availability, edits, crop/resize, and PNG/ZIP handling. `--check-inference` adds real AI processing when a model is installed. The runtime report does not contain workstation paths or private image names.

```powershell
.\dist\cutris\cutris.exe --self-test --check-inference --report build\frozen-inference.json
```

Build tooling scans the source archive and packaged runtime for the build account identity, configured Git name/email, and workstation home path. The scan includes decompressed embedded Python code. It excludes saved work, model weights, backups, logs, and private example images from the source payload.

On GitHub-hosted Windows runners, the generic `runneradmin` account and its standard home path are excluded from automatic identity detection because upstream wheels contain the same public build metadata. Local and self-hosted builds keep the account checks. Configured Git identities and explicit `CUTOUT_PRIVATE_TERMS` are always checked.

## Scope and limits

The model downloader is checked with deterministic simulated servers for interruption, HTTP Range behavior, corrupt data, size mismatches, retries, cancellation, and concurrent setup. Real-host download and installer smoke results are recorded locally under ignored build output.

A successful build and these checks do not substitute for trying installation on another clean Windows machine. No automatic remover guarantees perfect masks for every image. Review glass, hair, fur, pale edges, shadows, and detached details before export. Inference predicts a 1024-pixel mask and refines it at the original image dimensions; it is not full-resolution neural inference. Saved brush rasterization may differ slightly from Canvas preview at subpixel stroke edges.

The release is unsigned. Publisher signing can be added separately without putting a personal name, certificate, or private key into the source tree.
