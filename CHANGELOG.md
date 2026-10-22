# Changelog

## Unreleased

- Stop remaining queue items without losing finished cutouts; clear the current queue while keeping saved files and batch history.
- Show installed AI models immediately, with separate download and repair actions.
- Simplify the app header and refresh workspace, settings, and batch tools screenshots.
- Wait for native bridge methods before syncing editor state, so startup cannot interrupt editing or saving.
- Settings for export folders, automatic cropping, processing defaults, and preview controls.
- Optional desktop-hosted API with direct editor handoff from connected local apps.
- Save PNGs and ZIPs to a preferred folder without overwriting existing files.
- Full editor embedding, saved-revision metadata, and Save & return support for local workspaces.
- Standalone CLI and authenticated local API, with optional desktop dependencies.
- Default auto crop and optional resizing for automated PNG output.
- Editable API projects retain originals and full cutout masks for manual touch-ups.
- Release workflow builds and publishes the CLI/API wheel alongside the desktop downloads.
- Apply the same automatic crop rules to PNG and ZIP downloads.
- Auto crop batches and resize selected images.
- Create square icons with optional transparent padding.
- Preview batch changes and preserve editable originals and touch-ups.
- Update the README with current editor and batch tools screenshots.
- Retry temporary Windows file locks when saving batch progress.
