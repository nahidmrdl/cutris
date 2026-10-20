import io
import json
import os
import time
import zipfile

import pytest
from PIL import Image


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTOUT_DATA", str(tmp_path))
    import server
    monkeypatch.setattr(server, "DATA", tmp_path)
    monkeypatch.setattr(server, "JOBS", {})
    class FakeRemover:
        def process(self, image, quality, mode, progress):
            progress("Testing")
            return image, ["Synthetic test"]
    monkeypatch.setattr(server, "REMOVER", FakeRemover())
    from fastapi.testclient import TestClient
    with TestClient(server.app) as client:
        client.headers.update({"X-Cutout-Token": server.TOKEN})
        yield client
    # Let the background test job finish before monkeypatch restores its storage.
    server.POOL.submit(lambda: None).result(timeout=10)


def picture():
    data = io.BytesIO(); Image.new("RGB", (50,40), "blue").save(data,"PNG"); return data.getvalue()


def wait(api, job_id):
    for _ in range(100):
        job = api.get("/api/jobs/" + job_id).json()
        if job["status"] == "complete":
            return job
        time.sleep(.03)
    raise AssertionError("Worker did not finish")


def test_order_duplicates_zip_and_edits(api):
    files = [("files", (name, picture(), "image/png")) for name in ["page10.png", "page2.png", "page2.png"]]
    response = api.post("/api/jobs", files=files)
    assert response.status_code == 200
    job = wait(api, response.json()["id"])
    assert [i["output"] for i in job["items"]] == ["001_page10.png", "002_page2.png", "003_page2.png"]
    item = job["items"][0]
    edits_path = f'/api/jobs/{job["id"]}/items/{item["id"]}/edits'
    edit = {"revision":0,"strokes":[{"mode":"erase","size":10,"points":[[20,20]]}]}
    assert api.put(edits_path,json=edit).status_code == 200
    assert api.put(edits_path,json=edit).status_code == 409
    result = Image.open(io.BytesIO(api.get(f'/api/jobs/{job["id"]}/items/{item["id"]}/result').content))
    assert result.getpixel((20,20))[3] == 0 and result.size == (50,40)
    original = Image.open(io.BytesIO(api.get(f'/api/jobs/{job["id"]}/items/{item["id"]}/original').content))
    assert original.getpixel((20,20))[3] == 255
    bundle = api.get(f'/api/jobs/{job["id"]}/download.zip')
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert archive.namelist() == ["001_page10.png", "002_page2.png", "003_page2.png", "batch-manifest.json"]
    assert api.put(edits_path,json={"revision":1,"strokes":[]}).status_code == 200


def test_reject_51_files(api):
    response = api.post("/api/jobs",files=[("files",("a.png",picture(),"image/png"))]*51)
    assert response.status_code == 400


def test_accept_50_files(api):
    response = api.post("/api/jobs",files=[("files",("a.png",picture(),"image/png"))]*50)
    assert response.status_code == 200
    assert len(wait(api,response.json()["id"])["items"]) == 50


def test_corrupt_image_does_not_stop_batch(api):
    response = api.post("/api/jobs", files=[("files",("bad.png",b"bad","image/png")),("files",("good.png",picture(),"image/png"))])
    job = wait(api,response.json()["id"])
    assert [i["status"] for i in job["items"]] == ["error","done"]


def test_security(api):
    assert api.post("/api/jobs",headers={"X-Cutout-Token":"bad"}).status_code == 403
    assert api.post("/api/jobs",headers={"Origin":"https://evil.example"}).status_code == 403
    assert api.get("/api/config",headers={"Host":"evil.example"}).status_code == 400
    assert api.get("/api/jobs/not-a-job").status_code == 404


def test_stroke_validation(api):
    job = wait(api,api.post("/api/jobs",files=[("files",("a.png",picture(),"image/png"))]).json()["id"])
    path = f'/api/jobs/{job["id"]}/items/{job["items"][0]["id"]}/edits'
    assert api.put(path,json={"revision":0,"strokes":[{"mode":"erase","size":1000,"points":[[1,1]]}]}).status_code == 422
    assert api.put(path,json={"revision":0,"strokes":[{"mode":"erase","size":20,"points":[[99999,1]]}]}).status_code == 400


def test_pause_resume_and_only_one_active_batch(api, monkeypatch):
    import server
    import threading
    entered, release = threading.Event(), threading.Event()
    class SlowRemover:
        def process(self, image, quality, mode, progress):
            entered.set()
            release.wait(timeout=5)
            return image, []
    monkeypatch.setattr(server, "REMOVER", SlowRemover())
    files = [("files",("a.png",picture(),"image/png"))]*2
    job_id = api.post("/api/jobs",files=files).json()["id"]
    assert entered.wait(timeout=3)
    assert api.post("/api/jobs",files=files).status_code == 409
    assert api.post(f"/api/jobs/{job_id}/pause").status_code == 200
    release.set()
    server.POOL.submit(lambda: None).result(timeout=5)
    job = api.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "paused"
    assert [i["status"] for i in job["items"]] == ["done","waiting"]
    assert api.post(f"/api/jobs/{job_id}/resume").status_code == 200
    assert all(i["status"] == "done" for i in wait(api,job_id)["items"])


def test_thumbnails_are_small_and_do_not_change_output(api):
    job = wait(api,api.post("/api/jobs",files=[("files",("a.png",picture(),"image/png"))]).json()["id"])
    path = f'/api/jobs/{job["id"]}/items/{job["items"][0]["id"]}/'
    thumb = api.get(path+"thumbnail")
    assert thumb.status_code == 200 and "private" in thumb.headers["cache-control"]
    assert max(Image.open(io.BytesIO(thumb.content)).size) <= 128
    assert Image.open(io.BytesIO(api.get(path+"result").content)).size == (50,40)
