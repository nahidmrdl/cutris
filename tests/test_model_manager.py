"""Downloads are simulated: these tests never contact an external service."""
import hashlib
import io
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import model_manager as manager


class Response(io.BytesIO):
    def __init__(self, payload, status=200, headers=None):
        super().__init__(payload)
        self.status = status
        self.headers = headers or {}


@pytest.fixture
def model(tmp_path, monkeypatch):
    payload = b"verified test model data"
    spec = manager.ModelSpec("detail", "test.onnx", "Best detail", len(payload),
                             hashlib.sha256(payload).hexdigest(), hashlib.md5(payload).hexdigest(),
                             "https://example.invalid/test.onnx")
    monkeypatch.setattr(manager, "MODEL_DIR", tmp_path / "cache")
    monkeypatch.setattr(manager, "RESOURCE_DIR", tmp_path / "resources")
    monkeypatch.setattr(manager, "MODELS", {"detail": spec})
    monkeypatch.setattr(manager.time, "sleep", lambda _: None)
    manager._verified.clear()
    return spec, payload


def test_valid_resource_model_reused_without_network(model, monkeypatch):
    spec, payload = model
    resource = manager.RESOURCE_DIR / "models" / spec.filename
    resource.parent.mkdir(parents=True)
    resource.write_bytes(payload)
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected download"))
    assert manager.ensure_model("detail") == resource
    assert manager.require_model("general") == resource
    assert manager.model_status() == {"detail": True}
    assert not manager.MODEL_DIR.exists()


def test_download_verified_and_activated_atomically(model, monkeypatch):
    spec, payload = model
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: Response(payload))
    updates = []
    path = manager.ensure_model("detail", updates.append)
    assert path.read_bytes() == payload
    assert not path.with_suffix(".onnx.part").exists()
    assert manager.require_model("detail") == path
    assert updates[-1].phase == "ready"
    assert updates[-1].downloaded == len(payload)


def test_resume_requests_exact_remaining_bytes(model, monkeypatch):
    spec, payload = model
    manager.MODEL_DIR.mkdir()
    (manager.MODEL_DIR / (spec.filename + ".part")).write_bytes(payload[:8])

    def open_response(request, **kwargs):
        assert request.get_header("Range") == "bytes=8-"
        return Response(payload[8:], 206, {"Content-Range": f"bytes 8-{len(payload) - 1}/{len(payload)}"})

    monkeypatch.setattr(manager.urllib.request, "urlopen", open_response)
    assert manager.ensure_model("detail").read_bytes() == payload


def test_server_ignoring_range_restarts_cleanly(model, monkeypatch):
    spec, payload = model
    manager.MODEL_DIR.mkdir()
    (manager.MODEL_DIR / (spec.filename + ".part")).write_bytes(payload[:8])
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: Response(payload, 200))
    assert manager.ensure_model("detail").read_bytes() == payload


def test_interruption_retries_and_resumes(model, monkeypatch):
    spec, payload = model
    calls = []

    def open_response(request, **kwargs):
        calls.append(request)
        if len(calls) == 1:
            return Response(payload[:8])
        assert request.get_header("Range") == "bytes=8-"
        return Response(payload[8:], 206, {"Content-Range": f"bytes 8-{len(payload) - 1}/{len(payload)}"})

    monkeypatch.setattr(manager.urllib.request, "urlopen", open_response)
    assert manager.ensure_model("detail").read_bytes() == payload
    assert len(calls) == 2


def test_corrupt_payload_never_activated(model, monkeypatch):
    spec, payload = model
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: Response(b"x" * len(payload)))
    with pytest.raises(manager.ModelDownloadError, match="integrity check"):
        manager.ensure_model("detail", attempts=1)
    assert not (manager.MODEL_DIR / spec.filename).exists()
    assert not (manager.MODEL_DIR / (spec.filename + ".part")).exists()
    assert manager.model_status() == {"detail": False}


def test_cancellation_keeps_partial_for_next_setup(model, monkeypatch):
    spec, payload = model
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: Response(payload))
    cancel = threading.Event()

    def progress(update):
        if update.phase == "downloading" and update.downloaded:
            cancel.set()

    with pytest.raises(manager.ModelDownloadCancelled):
        manager.ensure_model("detail", progress, cancel.is_set)
    assert not (manager.MODEL_DIR / spec.filename).exists()
    assert (manager.MODEL_DIR / (spec.filename + ".part")).read_bytes() == payload
    # A complete partial file is verified and adopted without another request.
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected download"))
    assert manager.ensure_model("detail").read_bytes() == payload


def test_bad_content_range_discards_partial(model, monkeypatch):
    spec, payload = model
    manager.MODEL_DIR.mkdir()
    partial = manager.MODEL_DIR / (spec.filename + ".part")
    partial.write_bytes(payload[:8])
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: Response(
        payload, 206, {"Content-Range": f"bytes 0-{len(payload) - 1}/{len(payload)}"}))
    with pytest.raises(manager.ModelDownloadError, match="invalid download segment"):
        manager.ensure_model("detail", attempts=1)
    assert not partial.exists()


def test_oversize_download_rejected(model, monkeypatch):
    spec, payload = model
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: Response(payload + b"extra"))
    with pytest.raises(manager.ModelDownloadError, match="unexpected size"):
        manager.ensure_model("detail", attempts=1)
    assert not (manager.MODEL_DIR / spec.filename).exists()


def test_disk_error_does_not_disclose_private_paths(model, monkeypatch):
    def fail(*a, **kw):
        raise PermissionError("private account name and path")

    monkeypatch.setattr(manager.Path, "mkdir", fail)
    with pytest.raises(manager.ModelDownloadError) as result:
        manager.ensure_model("detail")
    assert "private account" not in str(result.value)
    assert "disk space" in str(result.value)


def test_inference_rejects_corrupt_existing_weights_without_network(model, monkeypatch):
    spec, payload = model
    manager.MODEL_DIR.mkdir()
    (manager.MODEL_DIR / spec.filename).write_bytes(b"x" * len(payload))
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected download"))
    with pytest.raises(manager.ModelDownloadError, match="needs repair"):
        manager.require_model("detail")
    assert manager.model_status() == {"detail": False}


def test_two_workers_share_one_download(model, monkeypatch):
    spec, payload = model
    calls = []

    def open_response(*a, **kw):
        calls.append(True)
        return Response(payload)

    monkeypatch.setattr(manager.urllib.request, "urlopen", open_response)
    with ThreadPoolExecutor(max_workers=2) as executor:
        paths = list(executor.map(lambda _: manager.ensure_model("detail"), range(2)))
    assert paths[0] == paths[1]
    assert paths[0].read_bytes() == payload
    assert len(calls) == 1


def test_cancellation_before_work_does_not_create_files(model, monkeypatch):
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected download"))
    with pytest.raises(manager.ModelDownloadCancelled):
        manager.ensure_model("detail", cancelled=lambda: True)
    assert not manager.MODEL_DIR.exists()
