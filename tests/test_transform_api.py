import io
import json
import zipfile

import pytest
from PIL import Image

from test_server import api, picture, wait


def create(api, data=None):
    response = api.post("/api/jobs", files=[("files", ("cutout.png", data or picture(), "image/png"))])
    assert response.status_code == 200
    job = wait(api, response.json()["id"])
    item = job["items"][0]
    return job, item, f'/api/jobs/{job["id"]}/items/{item["id"]}/'


def png(response):
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as image:
        return image.convert("RGBA")


def test_transform_export_zip_persistence_and_subsequent_touchups(api, monkeypatch):
    import server
    data = io.BytesIO()
    source = Image.new("RGBA", (80, 60), (0, 0, 0, 0))
    source.paste((40, 100, 200, 255), (20, 15, 60, 45))
    source.save(data, "PNG")
    job, item, path = create(api, data.getvalue())
    original_bytes = api.get(path + "original").content
    automatic_bytes = api.get(path + "automatic").content
    settings = {"crop": {"x": 20, "y": 15, "width": 40, "height": 30},
                "resize": {"width": 20, "height": 15}}
    response = api.put(path + "transform", json={"revision": 0, **settings})
    assert response.status_code == 200
    assert response.json() == {"revision": 1, "transform": settings, "output_width": 20, "output_height": 15}
    assert png(api.get(path + "result")).size == (20, 15)
    assert png(api.get(path + "thumbnail")).size == (20, 15)
    assert api.get(path + "original").content == original_bytes
    assert api.get(path + "automatic").content == automatic_bytes
    assert api.put(path + "transform", json={"revision": 0, **settings}).status_code == 409

    # Re-open saved data as a new process would, then edit in source coordinates.
    manifest = server.DATA / job["id"] / "manifest.json"
    saved_job = json.loads(manifest.read_text(encoding="utf-8"))
    monkeypatch.setattr(server, "JOBS", {job["id"]: saved_job})
    saved_item = api.get(f'/api/jobs/{job["id"]}').json()["items"][0]
    assert saved_item["width"] == 80 and saved_item["height"] == 60
    assert saved_item["transform"] == settings and saved_item["output_width"] == 20
    assert api.get("/api/jobs").json()[0]["id"] == job["id"]
    edited = api.put(path + "edits", json={"revision": 1, "strokes": [
        {"mode": "erase", "size": 14, "points": [[40, 30]]},
    ]})
    assert edited.status_code == 200
    assert edited.json()["transform"] == settings and edited.json()["revision"] == 2
    result = png(api.get(path + "result"))
    assert result.size == (20, 15) and result.getpixel((10, 7))[3] == 0
    assert result.getpixel((0, 0)) == (40, 100, 200, 255)
    assert api.get(path + "original").content == original_bytes
    assert api.get(path + "automatic").content == automatic_bytes

    with zipfile.ZipFile(io.BytesIO(api.get(f'/api/jobs/{job["id"]}/download.zip').content)) as archive:
        with Image.open(io.BytesIO(archive.read(item["output"]))) as exported:
            assert exported.size == (20, 15) and exported.getpixel((10, 7))[3] == 0
        metadata = json.loads(archive.read("batch-manifest.json"))["items"][0]
        assert metadata["transform"] == settings and metadata["output_height"] == 15

    reset = api.put(path + "transform", json={"revision": 2, "crop": None, "resize": None})
    assert reset.json()["output_width"] == 80 and reset.json()["output_height"] == 60
    result = png(api.get(path + "result"))
    assert result.size == (80, 60) and result.getpixel((40, 30))[3] == 0
    assert api.get(f'/api/jobs/{job["id"]}').json()["items"][0]["strokes"]


def test_legacy_saved_items_default_to_original_canvas(api):
    import server
    job, item, path = create(api)
    legacy_item = server.JOBS[job["id"]]["items"][0]
    for field in ("transform", "output_width", "output_height"):
        legacy_item.pop(field, None)
    loaded = api.get(f'/api/jobs/{job["id"]}').json()["items"][0]
    assert loaded["transform"] == {"crop": None, "resize": None}
    assert (loaded["output_width"], loaded["output_height"]) == (50, 40)
    response = api.put(path + "edits", json={"revision": 0, "strokes": []})
    assert response.status_code == 200 and response.json()["output_width"] == 50
    assert png(api.get(path + "result")).size == (50, 40)


def test_crop_only_and_resize_only_can_be_replaced_without_reprocessing(api):
    job, item, path = create(api)
    cropped = api.put(path + "transform", json={"revision": 0,
        "crop": {"x": 10, "y": 10, "width": 20, "height": 15}, "resize": None})
    assert cropped.status_code == 200 and png(api.get(path + "result")).size == (20, 15)
    resized = api.put(path + "transform", json={"revision": 1, "crop": None,
        "resize": {"width": 10, "height": 8}})
    assert resized.status_code == 200 and png(api.get(path + "result")).size == (10, 8)
    assert resized.json()["transform"]["crop"] is None
    assert png(api.get(path + "original")).size == (50, 40)
    assert png(api.get(path + "automatic")).size == (50, 40)


@pytest.mark.parametrize("changes,status", [
    ({"crop": {"x": 49, "y": 0, "width": 2, "height": 1}}, 400),
    ({"crop": {"x": 0, "y": 39, "width": 1, "height": 2}}, 400),
    ({"crop": {"x": -1, "y": 0, "width": 1, "height": 1}}, 422),
    ({"crop": {"x": 0, "y": 0, "width": 0, "height": 1}}, 422),
    ({"crop": {"x": .5, "y": 0, "width": 1, "height": 1}}, 422),
    ({"crop": {"x": True, "y": 0, "width": 1, "height": 1}}, 422),
    ({"crop": {"x": 0, "y": 0, "width": 1, "height": 1, "extra": 1}}, 422),
    ({"resize": {"width": 12001, "height": 1}}, 422),
    ({"resize": {"width": 6000, "height": 4001}}, 400),
    ({"resize": {"width": 0, "height": 1}}, 422),
    ({"resize": {"width": 1.0, "height": 1}}, 422),
    ({"resize": {"width": "1", "height": 1}}, 422),
    ({"resize": {"width": 1, "height": False}}, 422),
    ({"resize": {"width": 1, "height": 1, "extra": 1}}, 422),
    ({"revision": True}, 422),
    ({"revision": .5}, 422),
    ({"revision": -1}, 422),
    ({"unknown": 1}, 422),
])
def test_invalid_transform_does_not_modify_saved_output(api, changes, status):
    job, item, path = create(api)
    before = api.get(path + "result").content
    response = api.put(path + "transform", json={"revision": 0, "crop": None, "resize": None, **changes})
    assert response.status_code == status
    assert api.get(path + "result").content == before
    assert api.get(f'/api/jobs/{job["id"]}').json()["items"][0]["revision"] == 0


def test_transform_requires_completed_image(api):
    import server
    job, item, path = create(api)
    server.JOBS[job["id"]]["items"][0]["status"] = "waiting"
    response = api.put(path + "transform", json={"revision": 0, "crop": None, "resize": {"width": 10, "height": 10}})
    assert response.status_code == 409
