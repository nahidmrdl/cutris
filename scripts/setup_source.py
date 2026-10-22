"""Set up a source checkout; end users can use the Windows installer or wheel."""
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        raise SystemExit("Source setup needs Python 3.11, 3.12, or 3.13.")
    executable = ROOT / ".venv" / "Scripts" / "python.exe"
    if not executable.exists():
        venv.create(ROOT / ".venv", with_pip=True)
    subprocess.run([str(executable), "-m", "pip", "install", "-r", str(ROOT / "requirements-desktop.txt")], check=True)
    subprocess.run([str(executable), str(ROOT / "desktop.py"), "--setup-models"], check=True)
    print("Ready. Double-click Start.cmd to open cutris.")


if __name__ == "__main__":
    main()
