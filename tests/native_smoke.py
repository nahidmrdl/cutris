"""Run an isolated smoke check in the actual Windows WebView2 renderer.

Use CUTOUT_HOME to choose disposable test storage. No user artwork is opened.
This is a developer command, not part of the installed application.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_paths import APP_NAME, DATA_DIR
from desktop import DesktopApi, LocalServer
from PIL import Image, ImageDraw
import webview


def main():
    report = {"ok": False, "checks": {}}
    destination = Path(sys.argv[1])
    service = LocalServer(desktop_mode=True)
    service.start()
    bridge = DesktopApi()
    window = webview.create_window(APP_NAME + " — isolated verification", service.url,
                                   js_api=bridge, width=1440, height=960)
    bridge._window = window
    image = Image.new("RGB", (320, 320), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 38, 250, 285), radius=50, fill="#4854b1")
    draw.ellipse((105, 100, 130, 132), fill="white")
    draw.ellipse((190, 100, 215, 132), fill="white")
    data = io.BytesIO()
    image.save(data, "PNG")
    encoded = base64.b64encode(data.getvalue()).decode("ascii")

    def wait(expression, timeout=40):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if window.evaluate_js(expression):
                return
            time.sleep(.15)
        raise RuntimeError("Timed out waiting for a renderer check.")

    def check(name, expression):
        result = window.evaluate_js(expression)
        report["checks"][name] = bool(result)
        if not result:
            raise AssertionError(name)

    def run():
        stage = "initialization"
        try:
            wait("Boolean(state.token && window.pywebview?.api?.document_state)")
            check("desktop_bridge", "!$('modelsButton').hidden && !$('savedWorkButton').hidden")
            check("general_background_default", "$('mode').value === 'ai'")
            check("desktop_layout", "document.documentElement.scrollWidth <= innerWidth")
            stage = "batch processing"
            window.evaluate_js("""(() => {
                const bytes = Uint8Array.from(atob(%s), c => c.charCodeAt(0));
                const transfer = new DataTransfer();
                transfer.items.add(new File([bytes], 'synthetic-test.png', {type:'image/png'}));
                $('files').files = transfer.files;
                $('files').dispatchEvent(new Event('change'));
            })()""" % json.dumps(encoded))
            wait("state.files.length === 1 && Boolean(state.original)")
            window.evaluate_js("$('quality').value = 'fast'; $('start').click()")
            wait("state.job?.items[0]?.status === 'done' && Boolean(state.automatic)", 90)
            check("native_batch_inference", "currentItem().width === 320 && !$('download').disabled")
            stage = "saved touch-up"
            # Supply one brush gesture, then exercise the real Save button and server.
            window.evaluate_js("state.strokes.push({mode:'erase',size:20,points:[[160,160]]}); state.dirty=true; renderCanvas(); updateTools(); $('save').click()")
            wait("!state.busy && !state.dirty && currentItem().revision === 1")
            check("touch_up_saved", "$('dirtyLabel').textContent.includes('Saved')")
            path = window.evaluate_js("imageURL(currentItem())")
            with urllib.request.urlopen(service.url + path) as response:
                exported = Image.open(io.BytesIO(response.read()))
                report["checks"]["export_alpha"] = exported.getpixel((160, 160))[3] == 0
            job_id = window.evaluate_js("state.job.id")
            with urllib.request.urlopen(service.url + f"/api/jobs/{job_id}/download.zip") as response:
                with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                    report["checks"]["ordered_zip"] = archive.namelist() == ["001_synthetic-test.png", "batch-manifest.json"]
            stage = "dialogs and history"
            window.evaluate_js("$('aboutButton').click()")
            wait("$('aboutDialog').open && $('licenseNotices').textContent.includes('MIT')")
            check("about_and_licenses", "$('appVersion').textContent.length > 0")
            window.evaluate_js("$('closeAbout').click(); $('historyButton').click()")
            wait("$('historyDialog').open && $('historyList').querySelectorAll('button').length === 1")
            check("saved_batch_history", "$('historyList').textContent.includes('1 images')")
            window.evaluate_js("$('closeHistory').click(); state.dirty=false; updateTools()")
            report["ok"] = all(report["checks"].values())
        except Exception as error:
            report["error"] = type(error).__name__
            report["stage"] = stage
        finally:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            window.confirm_close = False
            window.destroy()

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.start(run, gui="edgechromium", private_mode=True,
                      storage_path=str(DATA_DIR / "webview-smoke"))
    finally:
        service.stop()
        service.module.POOL.shutdown(wait=True, cancel_futures=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
