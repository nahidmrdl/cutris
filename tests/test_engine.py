import io

import numpy as np
import pytest
from PIL import Image

from engine import Remover, apply_strokes, load_image, refine_white, save_png


def test_decode_and_export(tmp_path):
    image = Image.new("RGB", (120, 90), "white")
    data = io.BytesIO(); image.save(data, "JPEG")
    loaded = load_image(data.getvalue())
    assert loaded.size == (120, 90) and loaded.mode == "RGBA"
    save_png(loaded, tmp_path / "out.png")
    with Image.open(tmp_path / "out.png") as result:
        assert result.size == loaded.size and result.mode == "RGBA"
        assert result.info.get("icc_profile")


def test_bad_file():
    with pytest.raises(Exception):
        load_image(b"not a photo")


def test_orientation():
    image = Image.new("RGB", (120, 90), "red")
    exif = Image.Exif(); exif[274] = 6
    data = io.BytesIO(); image.save(data, "JPEG", exif=exif)
    assert load_image(data.getvalue()).size == (90, 120)


def test_existing_alpha_is_preserved():
    image = Image.new("RGBA", (30, 30), (120, 20, 70, 120))
    result, notes = Remover().process(image, "detail", "white")
    assert np.array_equal(np.array(result), np.array(image))
    assert "preserved" in notes[0]


def test_white_foreground_and_edge_cleanup():
    rgb = np.ones((100, 100, 3), np.float32)
    rgb[20:80, 20:80] = [.1,.3,.5]
    rgb[35:45, 35:45] = 1  # White eye highlight INSIDE the subject.
    mask = np.zeros((100, 100), np.float32)
    mask[20:80, 20:80] = 1
    clean, alpha, _ = refine_white(rgb, mask)
    assert alpha[40,40] == 1 and np.all(clean[40,40] == 1)
    assert alpha[0,0] == 0 and alpha[50,50] == 1


def test_colored_background_does_not_use_white_refinement():
    rgb = np.zeros((40,40,3), np.float32); rgb[:,:,0] = 1
    mask = np.ones((40,40), np.float32)*.7
    clean, alpha, notes = refine_white(rgb, mask)
    assert np.array_equal(alpha, mask) and np.array_equal(clean, rgb)
    assert "AI-only" in notes[0]


def test_edge_color_unmix():
    rgb = np.ones((100,100,3), np.float32)
    rgb[20:80,20:80] = [0,.2,.4]
    rgb[19,20:80] = [.5,.6,.7]
    mask = np.zeros((100,100), np.float32); mask[20:80,20:80] = 1; mask[19,20:80] = .4
    clean, alpha, _ = refine_white(rgb, mask)
    assert .45 < alpha[19,50] < .55
    assert np.allclose(clean[19,50], [0,.2,.4], atol=.02)


def test_erase_restore_and_reset():
    original = Image.new("RGBA", (80,80), (20,60,120,255))
    automatic = original.copy()
    strokes = [{"mode":"erase", "size":20, "points":[[30,30],[50,30]]}]
    erased = np.array(apply_strokes(original, automatic, strokes))
    assert erased[30,40,3] == 0 and erased[60,60,3] == 255
    restored = np.array(apply_strokes(original, automatic, strokes + [{"mode":"restore", "size":10, "points":[[40,30]]}]))
    assert tuple(restored[30,40]) == (20,60,120,255)
    assert np.array_equal(np.array(apply_strokes(original,automatic,[])),np.array(automatic))


def test_off_canvas_stroke_safe():
    original = Image.new("RGBA",(10,10),"blue")
    result = apply_strokes(original, original, [{"mode":"erase","size":10,"points":[[-100,-100],[-90,-90]]}])
    assert np.array_equal(np.array(original),np.array(result))


def test_model_switch_recovers_after_failed_session_load(monkeypatch, tmp_path):
    import engine
    import onnxruntime as ort
    from pathlib import Path
    from types import SimpleNamespace
    calls = []

    class Session:
        def get_inputs(self):
            return [SimpleNamespace(name="image")]

        def run(self, outputs, inputs):
            return [np.zeros((1, 1, 4, 4), dtype=np.float32)]

    def create(path, **kwargs):
        quality = Path(path).stem
        calls.append(quality)
        if quality == "detail":
            raise RuntimeError("Not enough memory for the larger model.")
        return Session()

    monkeypatch.setattr(engine, "require_model", lambda quality: tmp_path / (quality + ".onnx"))
    monkeypatch.setattr(ort, "InferenceSession", create)
    remover = Remover()
    image = Image.new("RGB", (16, 16), "white")
    remover.predict(image, "fast")
    with pytest.raises(RuntimeError, match="memory"):
        remover.predict(image, "detail")
    assert remover.predict(image, "fast").shape == (16, 16)
    assert calls == ["fast", "detail", "fast"]
