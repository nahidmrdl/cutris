"""Verify crop and resize in the actual Windows WebView2 renderer.

Set CUTOUT_HOME to empty disposable storage and pass a JSON report path.
The generated transparent fixture exercises the real image pipeline without AI.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
import webview


def main():
    if not os.environ.get("CUTOUT_HOME"):
        raise RuntimeError("Set CUTOUT_HOME to empty disposable test storage.")
    from app_paths import APP_NAME, DATA_DIR
    from desktop import DesktopApi, LocalServer

    if any((DATA_DIR / "jobs").glob("*/manifest.json")):
        raise RuntimeError("Choose empty test storage for this isolated check.")
    report = {"ok": False, "checks": {}}
    destination = Path(sys.argv[1])
    service = LocalServer(desktop_mode=True)
    service.start()
    bridge = DesktopApi()
    window = webview.create_window(APP_NAME + " — crop verification", service.url,
                                   js_api=bridge, width=1440, height=960)
    bridge._window = window
    fixture = Image.new("RGBA", (320, 240), (0, 0, 0, 0))
    ImageDraw.Draw(fixture).rectangle((80, 50, 239, 189), fill=(72, 84, 177, 255))
    # Auto crop must keep even the faintest nonzero alpha at the subject edge.
    fixture.putpixel((79, 49), (72, 84, 177, 1))
    occupied = Image.new("RGBA", (64, 48), (255, 255, 255, 255))
    # A small alpha variation bypasses AI while every pixel remains occupied.
    occupied.putpixel((0, 0), (255, 255, 255, 249))
    empty = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
    encoded = []
    for name, image in (("geometry-fixture.png", fixture),
                        ("occupied-fixture.png", occupied),
                        ("transparent-fixture.png", empty)):
        payload = io.BytesIO()
        image.save(payload, "PNG")
        encoded.append({"name": name, "data": base64.b64encode(payload.getvalue()).decode("ascii")})

    def wait(expression, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if window.evaluate_js(expression):
                return
            time.sleep(.15)
        raise RuntimeError("Timed out waiting for a crop renderer check.")

    def record(name, result):
        report["checks"][name] = bool(result)
        if not result:
            raise AssertionError(name)

    def check(name, expression):
        record(name, window.evaluate_js(expression))

    def click(identifier):
        window.evaluate_js(f"$({json.dumps(identifier)}).click()")

    def field(identifier, value):
        window.evaluate_js("""(() => {
            const input = $(%s);
            input.value = %s;
            input.dispatchEvent(new Event('input', {bubbles:true}));
            input.dispatchEvent(new Event('change', {bubbles:true}));
        })()""" % (json.dumps(identifier), json.dumps(str(value))))

    def read_image(kind="result"):
        path = window.evaluate_js(f"imageURL(currentItem(), {json.dumps(kind)})")
        with urllib.request.urlopen(service.url + path, timeout=10) as response:
            image = Image.open(io.BytesIO(response.read())).convert("RGBA")
            image.load()
        return image

    def apply(revision):
        click("geometryApply")
        wait(f"!$('geometryDialog').open && !state.busy && currentItem().revision === {revision}")

    def run():
        stage = "initialization"
        try:
            wait("Boolean(state.token && window.pywebview?.api?.document_state)")
            check("layout_fits_window", "document.documentElement.scrollWidth <= innerWidth")
            stage = "transparent fixture processing"
            window.evaluate_js("""(() => {
                const transfer = new DataTransfer();
                for (const fixture of %s) {
                    const bytes = Uint8Array.from(atob(fixture.data), c => c.charCodeAt(0));
                    transfer.items.add(new File([bytes], fixture.name, {type:'image/png'}));
                }
                $('files').files = transfer.files;
                $('files').dispatchEvent(new Event('change'));
            })()""" % json.dumps(encoded))
            wait("state.files.length === 3 && Boolean(state.original)")
            window.evaluate_js("$('quality').value='fast'; $('start').click()")
            wait("state.job?.status === 'complete' && Boolean(state.automatic)")
            check("original_preview_size", "canvas.width === 320 && canvas.height === 240")

            stage = "auto crop soft alpha"
            click("geometryButton")
            wait("$('geometryDialog').open && !$('geometryAutoCrop').disabled")
            check("crop_dialog_fits_window", "$('geometryDialog').getBoundingClientRect().width <= innerWidth")
            click("geometryAutoCrop")
            wait("Number($('geometryCropX').value) === 79 && Number($('geometryCropY').value) === 49")
            check("auto_crop_detects_unused_margins", "Number($('geometryCropWidth').value) === 161 && Number($('geometryCropHeight').value) === 141")
            check("auto_crop_preview_dimensions", "$('geometryOutputDimensions').textContent === '161 × 141 px'")
            apply(1)
            auto = read_image()
            record("auto_crop_export_size", auto.size == (161, 141))
            record("auto_crop_retains_soft_alpha", auto.getpixel((0, 0))[3] == 1)
            check("auto_crop_main_preview", "canvas.width === 161 && canvas.height === 141")

            stage = "manual crop and aspect locked resize"
            click("geometryButton")
            wait("$('geometryDialog').open")
            click("geometryFullImage")
            click("geometryManualCrop")
            window.evaluate_js("""(() => {
                const wrap = $('geometryCanvasWrap').getBoundingClientRect();
                const scale = geometryState.scale;
                const send = (target, type, x, y, buttons) => target.dispatchEvent(new PointerEvent(type, {
                    bubbles:true, pointerId:71, pointerType:'mouse', button:0, buttons,
                    clientX:wrap.left+x*scale, clientY:wrap.top+y*scale
                }));
                send($('geometryCropBox'), 'pointerdown', 84, 54, 1);
                send($('geometryStage'), 'pointermove', 236, 186, 1);
                send($('geometryStage'), 'pointerup', 236, 186, 0);
            })()""")
            check("manual_drag_draws_crop", "Number($('geometryCropX').value) === 84 && Number($('geometryCropY').value) === 54 && Number($('geometryCropWidth').value) === 152 && Number($('geometryCropHeight').value) === 132")
            for identifier, value in (("geometryCropX", 84), ("geometryCropY", 54),
                                      ("geometryCropWidth", 152), ("geometryCropHeight", 132)):
                field(identifier, value)
            if not window.evaluate_js("$('geometryResizeEnabled').checked"):
                click("geometryResizeEnabled")
            if not window.evaluate_js("$('geometryAspectLock').checked"):
                click("geometryAspectLock")
            field("geometryResizeWidth", 12001)
            check("oversized_resize_blocks_apply", "$('geometryApply').disabled && !$('geometryError').hidden")
            field("geometryResizeWidth", 304)
            wait("Number($('geometryResizeHeight').value) === 264")
            check("aspect_locked_resize", "$('geometryAspectLock').checked && Number($('geometryResizeWidth').value) === 304")
            check("manual_crop_live_preview", "$('geometryOutputDimensions').textContent === '304 × 264 px' && $('geometryOutputPreview').width > 0 && $('geometryOutputPreview').height > 0")
            apply(2)
            record("manual_crop_export_size", read_image().size == (304, 264))
            check("resized_main_preview", "canvas.width === 304 && canvas.height === 264")

            stage = "reopen and cancel"
            click("geometryButton")
            wait("$('geometryDialog').open")
            check("saved_crop_reopens", "Number($('geometryCropX').value) === 84 && Number($('geometryCropY').value) === 54 && Number($('geometryCropWidth').value) === 152 && Number($('geometryCropHeight').value) === 132")
            check("saved_resize_reopens", "$('geometryResizeEnabled').checked && Number($('geometryResizeWidth').value) === 304 && Number($('geometryResizeHeight').value) === 264")
            field("geometryCropX", 10)
            # Keep a failed save reviewable instead of silently dismissing it.
            window.evaluate_js("""window.geometrySmokeApi=api; api=async (path, options) => {
                if (path.endsWith('/transform')) throw new Error('Unable to save this test crop.');
                return window.geometrySmokeApi(path, options);
            }""")
            click("geometryApply")
            wait("!state.busy && !$('geometryError').hidden")
            check("failed_save_keeps_dialog_and_settings", "$('geometryDialog').open && $('geometryError').textContent === 'Unable to save this test crop.' && Number($('geometryCropX').value) === 10 && currentItem().revision === 2")
            window.evaluate_js("api=window.geometrySmokeApi; delete window.geometrySmokeApi")
            click("geometryCancel")
            wait("!$('geometryDialog').open")
            check("cancel_preserves_revision", "currentItem().revision === 2")
            record("cancel_preserves_export", read_image().size == (304, 264))

            stage = "touch up after resize"
            click("eraseTool")
            check("touch_up_uses_source_coordinates", "canvas.width === 320 && canvas.height === 240")
            # Supply one source-coordinate gesture, then exercise Save and the server.
            window.evaluate_js("state.strokes.push({mode:'erase',size:20,points:[[160,120]]}); state.dirty=true; renderCanvas(); updateTools(); $('save').click()")
            wait("!state.busy && !state.dirty && currentItem().revision === 3")
            click("doneEditing")
            check("saved_geometry_preview_after_touch_up", "canvas.width === 304 && canvas.height === 264")
            edited = read_image()
            record("touch_up_preserves_output_size", edited.size == (304, 264))
            record("touch_up_maps_through_crop_and_resize", edited.getpixel((152, 132))[3] == 0)
            record("source_pixels_untouched", read_image("original").tobytes() == fixture.tobytes())

            stage = "ordered ZIP preserves geometry"
            job_id = window.evaluate_js("state.job.id")
            with urllib.request.urlopen(service.url + f"/api/jobs/{job_id}/download.zip", timeout=10) as response:
                with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                    record("ordered_zip_members", archive.namelist() == ["001_geometry-fixture.png", "002_occupied-fixture.png", "003_transparent-fixture.png", "batch-manifest.json"])
                    packed = Image.open(io.BytesIO(archive.read("001_geometry-fixture.png")))
                    record("ordered_zip_uses_saved_dimensions", packed.size == (304, 264))

            stage = "restore full canvas"
            click("geometryButton")
            wait("$('geometryDialog').open")
            click("geometryFullImage")
            click("geometryResetSize")
            apply(4)
            restored = read_image()
            record("full_canvas_export_restored", restored.size == (320, 240))
            record("full_canvas_keeps_touch_up", restored.getpixel((160, 120))[3] == 0)
            check("full_canvas_main_preview", "canvas.width === 320 && canvas.height === 240")

            stage = "occupied and empty auto crop"
            window.evaluate_js("document.querySelectorAll('.queue-item')[1].click()")
            wait("currentItem()?.name === 'occupied-fixture.png' && Boolean(state.automatic) && canvas.width === 64")
            click("geometryButton")
            wait("$('geometryDialog').open")
            click("geometryAutoCrop")
            check("occupied_canvas_not_removed", "Number($('geometryCropX').value) === 0 && Number($('geometryCropY').value) === 0 && Number($('geometryCropWidth').value) === 64 && Number($('geometryCropHeight').value) === 48")
            click("geometryCancel")
            window.evaluate_js("document.querySelectorAll('.queue-item')[2].click()")
            wait("currentItem()?.name === 'transparent-fixture.png' && Boolean(state.automatic) && canvas.width === 64")
            click("geometryButton")
            wait("$('geometryDialog').open")
            click("geometryAutoCrop")
            check("empty_canvas_retains_valid_dimensions", "Number($('geometryCropWidth').value) === 64 && Number($('geometryCropHeight').value) === 48 && $('geometryOutputPreview').width > 0 && $('geometryOutputPreview').height > 0")
            check("empty_canvas_explanation", "$('geometryStatus').textContent.includes('fully transparent')")
            click("geometryCancel")
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
        webview.start(run, gui="edgechromium", private_mode=True,
                      storage_path=str(DATA_DIR / "webview-geometry-smoke"))
    finally:
        service.stop()
        service.module.POOL.shutdown(wait=True, cancel_futures=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
