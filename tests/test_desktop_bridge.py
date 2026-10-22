"""Exercise the shipped JavaScript against delayed native bridge injection."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_desktop_bridge_startup_and_return():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed for the desktop JavaScript regression checks.")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("desktop_bridge.test.cjs"))],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
