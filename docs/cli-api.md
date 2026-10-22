# CLI and API

Cutris can process images without its desktop app, browser, or WebView2. The CLI, API, and editor use the same BiRefNet inference and output geometry.

## Install

Use 64-bit Python 3.11–3.13. Download the wheel from a release, then install it:

```powershell
python -m pip install .\cutris-VERSION-py3-none-any.whl
cutris --version
```

From a source checkout, use `python -m pip install .` or run `python -m cutris` with the source environment. The desktop dependency is optional: `python -m pip install ".[desktop]"` enables `cutris desktop` when installing from source.

## Remove backgrounds

```powershell
cutris remove input.jpg -o output.png
cutris remove .\images -o .\cutouts --quality fast --mode white
cutris remove input.jpg -o output.png --resize 512x512 --offline --json
```

Outputs are PNGs. Transparent margins are trimmed by default; use `--no-auto-crop` to keep the full canvas. Resize runs after cropping. A directory input includes supported images directly inside that directory. Original images are preserved, duplicate output names are rejected, and existing outputs require `--overwrite`.

The CLI downloads only the selected missing model and verifies its checksum. Use `--offline` to prohibit downloads. Existing transparent images do not require inference or a model.

```powershell
cutris models list
cutris models download --quality detail
cutris models download --quality all
```

Installed CLI/API and desktop releases share the existing model cache. Source checkouts keep using their local `models` folder. `CUTOUT_MODELS` selects another model folder; `CUTOUT_HOME` selects private application storage.

## HTTP API

```powershell
cutris serve --port 4320
```

The service binds only to `127.0.0.1`. Every endpoint requires `Authorization: Bearer <key>`; no keys are exposed through an unauthenticated endpoint. By default the API uses installed models. Add `--download-models` to allow verified downloads on demand.

On Windows, the key and service descriptor are under `%LOCALAPPDATA%\Cutris\api`. `service.json` contains the origin and key-file location. Treat these as private local state. Use `--key-file` and `--descriptor` to select explicit files, or `CUTRIS_API_STATE` to change the default API state folder. `--port 0` chooses a free port and records it in the descriptor.

| Endpoint | Response |
| --- | --- |
| `GET /v1/health` | API and app versions, model-download policy. |
| `GET /v1/models` | Availability of detail and fast models. |
| `POST /v1/remove` | Transparent PNG; multipart upload. |
| `GET /v1/projects/{id}/result` | Latest saved PNG from an editable project. |
| `GET /v1/projects/{id}` | Saved revision and output dimensions without downloading the PNG. |
| `POST /v1/editor/open` | Ask an open desktop editor to review a saved project. |

Removal fields: `file`, `quality` (`detail` or `fast`), `mode` (`ai` or `white`), `auto_crop` (default `true`), optional `width` and `height`, and `editable` (default `false`). Dimensions must be supplied together. Limits: 30 MB, 24 megapixels, 12,000 pixels per side. Concurrent processing requests receive HTTP 409; process batches sequentially.

Example from PowerShell using the service's saved key:

```powershell
$service = Get-Content "$env:LOCALAPPDATA\Cutris\api\service.json" -Raw | ConvertFrom-Json
$key = (Get-Content $service.key_file -Raw).Trim()
curl.exe --fail-with-body -H "Authorization: Bearer $key" `
  -F "file=@input.jpg" -F "auto_crop=true" -F "editable=true" `
  -D response-headers.txt -o output.png "$($service.origin)/v1/remove"
```

Response headers include `X-Cutris-Width`, `X-Cutris-Height`, and `X-Cutris-Crop`. With `editable=true`, `X-Cutris-Project` identifies a saved editor project containing the original image, full cutout mask, and output geometry. Open it later with `cutris desktop --project <id>`. This requires the desktop extra and a supported desktop environment; API processing itself does not.

The API accepts uploaded bytes rather than arbitrary server file paths. It does not enable cross-origin browser access. Use a local application backend to call it. Missing models return HTTP 503, invalid images/settings return 400, and malformed form fields return 422.

## Desktop settings and integrations

Open **Settings → Exports** to choose a folder for PNG and ZIP exports and set automatic cropping. Existing files receive a new filename. **Processing & preview** remembers the starting quality, background treatment, preview background, and wheel zoom preference.

Enable **Settings → Integrations → Allow local integrations** to host the API while Cutris is open. It shares the editor's model session and processing lock. Connected tools discover the private descriptor in the standard API state folder; source checkouts also publish `data/integration/service.json`. Advanced connection details let you copy the address and API key.

`GET /v1/health` reports `editor_available`. When available, send `{"project_id":"<saved-project-id>"}` to `POST /v1/editor/open` with the API bearer key. Cutris opens the saved original and full mask, asking before discarding unsaved edits. A headless service returns HTTP 409 for this action; processing and exporting remain available.

Desktop preferences do not override explicit CLI arguments or API processing fields. The independent CLI/API remains available when an editor is not needed.

gflowris embeds the complete Cutris workspace and manages its own local engine. It uses this same package; the separate Cutris desktop application is not required. Saved project revisions sync back to its image queue automatically. **Save & return** saves pending touch-ups, exports an updated PNG, and returns to the queue while preserving earlier exports.
