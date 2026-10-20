# Contributing

Small, focused improvements are welcome. Open an issue before starting a large change.

## Report a problem

Include the cutrix version, Windows version, selected AI quality and background mode, what you expected, and steps to reproduce. If an image helps, use an example you are comfortable making public. Review screenshots and error messages for private filenames or paths.

## Work on the app

1. Use 64-bit Python 3.11–3.13 on Windows and run `Setup.cmd`.
2. Install test dependencies: `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
3. Make a focused change and run `.\.venv\Scripts\python.exe -m pytest -q`.
4. For interface changes, check the desktop app with `Start.cmd` and include a safe screenshot in the pull request.

Keep model weights, saved batches, generated binaries, personal artwork, and credentials out of commits. Preserve upstream license notices. See [release tooling](docs/releasing.md) for packaging changes.
