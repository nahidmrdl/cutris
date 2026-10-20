"""Set up a source checkout; end users should use the Windows installer."""
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main():
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        raise SystemExit("Source setup needs Python 3.11, 3.12, or 3.13. The Windows installer includes Python.")
    environment = ROOT / ".venv"
    executable = environment / "Scripts" / "python.exe"
    if not executable.exists():
        venv.create(environment, with_pip=True)
    subprocess.run([str(executable), "-m", "pip", "install", "-r", str(ROOT / "requirements-desktop.txt")], check=True)
    subprocess.run([str(executable), str(ROOT / "desktop.py"), "--setup-models"], check=True)
    print("Ready. Double-click Start.cmd to open cutrix.")


if __name__ == "__main__":
    main()
