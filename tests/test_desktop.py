"""Desktop lifecycle and privacy checks; no desktop windows or downloads open."""
import json
import subprocess
import sys
from types import SimpleNamespace
import urllib.request

import pytest

import app_paths
import desktop
import model_manager


def test_instance_lock_releases_and_can_be_reacquired(tmp_path):
    path = tmp_path / "private-data" / "desktop.lock"
    first, second = desktop.InstanceLock(path), desktop.InstanceLock(path)
    try:
        assert first.acquire()
        assert not second.acquire()
        first.release()
        first.release()  # Shutdown cleanup is idempotent.
        assert second.acquire()
        second.release()
        assert first.acquire()
    finally:
        first.release()
        second.release()


def test_local_server_ready_and_shutdown_use_isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "DATA_DIR", tmp_path)
    monkeypatch.setenv("CUTOUT_DATA", str(tmp_path))
    import server
    jobs = tmp_path / "jobs"
    jobs.mkdir(exist_ok=True)
    monkeypatch.setattr(server, "DATA", jobs)
    monkeypatch.setattr(server, "JOBS", {})
    monkeypatch.setattr(server, "model_status", lambda: {"detail": False, "fast": False})
    service = desktop.LocalServer()
    try:
        assert service.socket.getsockname()[0] == "127.0.0.1"
        service.start(timeout=5)
        with urllib.request.urlopen(service.url + "/api/config", timeout=2) as response:
            config = json.load(response)
        assert config["appId"] == app_paths.APP_ID
        assert config["token"] == server.TOKEN
        assert service.thread.is_alive()
        assert config["models"] == {"detail": False, "fast": False}
        assert server.DATA == jobs
        assert not list(jobs.iterdir())
    finally:
        service.stop()
    assert not service.thread.is_alive()
    assert service.socket.fileno() == -1


@pytest.mark.parametrize("frozen", [False, True])
def test_model_setup_subprocess_preserves_command_arguments(tmp_path, monkeypatch, frozen):
    calls = []
    executable = str(tmp_path / "runtime with spaces" / "python.exe")
    resources = tmp_path / "application folder"
    module_path = tmp_path / "installed package" / "desktop.py"
    monkeypatch.setattr(sys, "executable", executable)
    monkeypatch.setattr(app_paths, "FROZEN", frozen)
    monkeypatch.setattr(desktop, "RESOURCE_DIR", resources)
    monkeypatch.setattr(desktop, "__file__", str(module_path))
    monkeypatch.setattr(model_manager, "model_status", lambda: {"detail": True, "fast": False})

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", run)
    api = desktop.DesktopApi()
    assert api.setup_models() == {"ok": True, "models": {"detail": True, "fast": False}}
    expected = [executable] + ([] if frozen else [str(module_path.resolve())]) + ["--setup-models"]
    assert calls[0][0] == expected
    options = calls[0][1]
    assert not options.get("shell", False)
    assert options["stdin"] == subprocess.DEVNULL
    assert options["stdout"] == subprocess.DEVNULL
    assert options["stderr"] == subprocess.DEVNULL
    if sys.platform == "win32":
        assert options["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert not api._model_lock.locked()


def test_duplicate_model_setup_does_not_launch_second_process(monkeypatch):
    api = desktop.DesktopApi()
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("A second setup opened"))
    api._model_lock.acquire()
    try:
        result = api.setup_models()
        assert result["ok"] is False
        assert "already open" in result["message"]
    finally:
        api._model_lock.release()


def test_model_setup_failure_hides_private_diagnostics_and_releases_lock(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("Could not execute C:/Users/private-user/secret-folder/python.exe")

    monkeypatch.setattr(subprocess, "run", fail)
    api = desktop.DesktopApi()
    result = api.setup_models()
    assert result["ok"] is False
    assert "private-user" not in result["message"]
    assert "secret-folder" not in result["message"]
    assert not api._model_lock.locked()


def test_document_state_controls_close_confirmation():
    api = desktop.DesktopApi()
    api._window = SimpleNamespace(confirm_close=False)
    api.document_state(True, False)
    assert api._window.confirm_close is True
    api.document_state(False, True)
    assert api._window.confirm_close is True
    api.document_state(False, False)
    assert api._window.confirm_close is False


@pytest.mark.parametrize("message", [
    r"Cannot load C:\Users\private-user\model.onnx",
    "Cannot load C:/Users/private-user/model.onnx",
    r"Cannot load \\private-host\private-share\model.onnx",
    "Cannot load /Users/private-user/model.onnx",
    "Cannot load /home/private-user/model.onnx",
    "Traceback: private diagnostic details",
    "Library failed in site-packages/private-module",
    "Native runtime crashed at 0x1234",
])
def test_public_error_scrubs_machine_paths_and_library_diagnostics(message):
    assert app_paths.public_error(RuntimeError(message), "Safe failure message.") == "Safe failure message."


def test_public_error_retains_useful_user_action_and_hides_os_details():
    message = "Use a PNG, JPG, WebP, BMP, or TIFF image."
    assert app_paths.public_error(ValueError(message)) == message
    assert app_paths.public_error(PermissionError("private account details"), "Cannot save this file.") == "Cannot save this file."
