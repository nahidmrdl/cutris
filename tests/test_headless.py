"""Headless contracts, editable handoff, authentication, and safe file output."""
import io
import json
import sys

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from cutris import cli, processing, projects, service


def transparent_image():
    image = Image.new("RGBA", (30, 24))
    image.paste((100, 130, 200, 255), (5, 6, 22, 20))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_transparent_input_crops_without_a_model_and_resizes(monkeypatch):
    monkeypatch.setattr(processing, "ensure_model", lambda *a, **k: pytest.fail("Unexpected download"))
    monkeypatch.setattr(processing, "require_model", lambda *a, **k: pytest.fail("Unexpected model lookup"))
    image, metadata = processing.Processor().remove(transparent_image(), resize={"width": 34, "height": 28})
    assert image.size == (34, 28)
    assert metadata["crop"] == {"x": 5, "y": 6, "width": 17, "height": 14}
    assert metadata["source_width"] == 30


def test_cli_never_overwrites_an_input_or_existing_output(tmp_path, capsys):
    source = tmp_path / "source.png"
    source.write_bytes(transparent_image())
    original = source.read_bytes()
    assert cli.main(["remove", str(source), "-o", str(source), "--overwrite"]) == 1
    assert source.read_bytes() == original
    output = tmp_path / "out.png"
    assert cli.main(["remove", str(source), "-o", str(output), "--offline", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert (result[0]["width"], result[0]["height"]) == (17, 14)
    before = output.read_bytes()
    assert cli.main(["remove", str(source), "-o", str(output)]) == 1
    assert output.read_bytes() == before


def test_api_requires_auth_on_reads_and_rejects_foreign_origins(monkeypatch):
    app = service.create_app("x" * 48)
    with TestClient(app) as client:
        assert client.get("/v1/health").status_code == 401
        assert client.get("/v1/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
        headers = {"Authorization": "Bearer " + "x" * 48}
        assert client.get("/v1/health", headers=headers).json()["desktop_required"] is False
        assert client.get("/v1/health", headers={**headers, "Origin": "https://hostile.invalid"}).status_code == 403
        assert client.post("/v1/remove", headers={**headers, "Content-Length": str(40*1024*1024)}).status_code == 413


def test_api_returns_png_and_preserves_full_layers_for_manual_editing(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "DATA_DIR", tmp_path)
    headers = {"Authorization": "Bearer " + "x" * 48}
    with TestClient(service.create_app("x" * 48)) as client:
        response = client.post("/v1/remove", headers=headers, files={"file": ("sample.png", transparent_image(), "image/png")}, data={"editable": "true"})
    assert response.status_code == 200
    assert Image.open(io.BytesIO(response.content)).size == (17, 14)
    project = response.headers["X-Cutris-Project"]
    manifest = json.loads((tmp_path / "jobs" / project / "manifest.json").read_text())
    item = manifest["items"][0]
    directory = tmp_path / "jobs" / project / item["id"]
    assert Image.open(directory / "original.png").size == (30, 24)
    assert Image.open(directory / "automatic.png").size == (30, 24)
    assert Image.open(directory / "result.png").size == (17, 14)
    assert item["transform"]["crop"]["x"] == 5
    assert item["status"] == "done" and item["strokes"] == []
    with TestClient(service.create_app("x" * 48)) as client:
        exported = client.get(f"/v1/projects/{project}/result", headers=headers)
        assert exported.status_code == 200
        first, latest = Image.open(io.BytesIO(response.content)), Image.open(io.BytesIO(exported.content))
        assert first.size == latest.size and first.tobytes() == latest.tobytes()
        assert exported.headers["X-Cutris-Revision"] == "0"
        assert client.get("/v1/projects/not-a-project/result", headers=headers).status_code == 404


@pytest.mark.parametrize("data", [{"quality": "invalid"}, {"mode": "invalid"}, {"width": "5"}, {"width": "50000", "height": "5"}])
def test_api_rejects_bad_settings(data):
    with TestClient(service.create_app("x" * 48)) as client:
        response = client.post("/v1/remove", headers={"Authorization": "Bearer " + "x" * 48}, files={"file": ("sample.png", transparent_image())}, data=data)
        assert response.status_code == 400


def test_headless_imports_do_not_require_gui_runtime():
    import subprocess
    result = subprocess.run([sys.executable, "-c", "import cutris.cli, cutris.service, sys; assert 'webview' not in sys.modules; assert 'desktop' not in sys.modules; assert 'server' not in sys.modules"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
