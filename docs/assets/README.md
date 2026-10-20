# Repository visuals

- `hero.png` uses the approved app icon supplied by the project maintainer. Its source metadata was removed before inclusion. Run `scripts/make_repo_assets.py` from the repository root to reproduce the layout with `packaging/assets/app.png`.
- `demo.png` compares `tests/synthetic-character.png` with the real result from BiRefNet **Maximum detail**, **White illustration**. Its checkerboard and labels are presentation only; the cutout is not manually retouched. It is a comparison graphic, not an app screenshot.
- `make_demo.py` reproduces the comparison with the installed detail model. Run it from the repository root using the source environment.
- `showcase/background-removal.png`, `showcase/use-cases.png`, and `showcase/crop-and-resize.png` use artwork supplied by the project maintainer for these demonstrations. All cutouts are real **Maximum detail / White illustration** outputs, with no manual retouching. Checkerboards, labels, and example interface layouts are presentation only. They are not application screenshots.
- `showcase/provenance.json` records the processing mode and actual crop/resize dimensions. Original filenames and source metadata are omitted. The full source images and transparent exports stay in ignored working folders.
- `scripts/make_showcase_assets.py` reproduces the showcase from separate input images named `crystal.png`, `gift.png`, `backpack.png`, `quest.png`, `token.png`, `shopping-bag.png`, and `bomb.png`. Use `--input-dir path/to/inputs --process` with the detail model installed. The default cache is under ignored `build/readme-showcase/`.

These assets contain no personal metadata. The project's MIT license applies to the original repository layouts and synthetic fixture. App artwork provenance is recorded in the branding documentation.
