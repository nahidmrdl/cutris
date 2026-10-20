"""Generate Windows and web icons from the committed app artwork.

Run ``python scripts/make_icon.py`` to refresh all icon sizes. To replace the
artwork, pass ``--source path/to/artwork.png``; the imported master is resized
to 1024 pixels, preserves transparency, and contains no source metadata.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = Path('packaging/assets/app.png')
ICON_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256)


def clean_rgba(image: Image.Image) -> Image.Image:
    """Copy only visible RGBA pixels, removing metadata and hidden RGB values."""
    rgba = image.convert('RGBA')
    # A new image also discards EXIF, XMP, text, profiles and other source info.
    clean = Image.frombytes('RGBA', rgba.size, rgba.tobytes())
    transparent = clean.getchannel('A').point(lambda alpha: 255 if alpha == 0 else 0)
    clean.paste((0, 0, 0, 0), mask=transparent)
    return clean


def resize_icon(image: Image.Image, size: int) -> Image.Image:
    """Resample premultiplied color to keep translucent edges free of halos."""
    resized = image.convert('RGBa').resize((size, size), Image.Resampling.LANCZOS)
    return clean_rgba(resized.convert('RGBA'))


def read_artwork(source: Path) -> Image.Image:
    if not source.is_file():
        raise FileNotFoundError('App icon artwork is missing. Restore packaging/assets/app.png or import it with --source.')
    with Image.open(source) as image:
        if image.format != 'PNG':
            raise ValueError('App icon artwork must be a PNG image.')
        image = ImageOps.exif_transpose(image)
        if image.width != image.height or image.width < max(ICON_SIZES):
            raise ValueError('App icon artwork must be square and at least 256 pixels wide.')
        return clean_rgba(image)


def prepare_master(source: Path, destination: Path) -> None:
    """Import approved artwork without retaining its filename or metadata."""
    master = resize_icon(read_artwork(Path(source)), 1024)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    master.save(destination, format='PNG', optimize=True)


def make_icon(destination: Path, source: Path | None = None) -> None:
    """Build a multi-size 32-bit RGBA ICO from the selected PNG master."""
    artwork = read_artwork(Path(source) if source is not None else ROOT / MASTER_PATH)
    frames = [resize_icon(artwork, size) for size in ICON_SIZES]
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames[-1].save(destination, format='ICO', sizes=[frame.size for frame in frames],
                    append_images=frames[:-1])


def make_assets(root: Path = ROOT) -> None:
    """Refresh the Windows and web assets inside one explicit project root."""
    root = Path(root)
    source = root / MASTER_PATH
    artwork = read_artwork(source)
    windows_icon = root / 'packaging' / 'assets' / 'app.ico'
    make_icon(windows_icon, source)
    web_assets = root / 'web' / 'assets'
    web_assets.mkdir(parents=True, exist_ok=True)
    resize_icon(artwork, 256).save(web_assets / 'app.png', format='PNG', optimize=True)
    shutil.copyfile(windows_icon, web_assets / 'favicon.ico')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Import replacement square PNG artwork before generating icons.')
    args = parser.parse_args()
    if args.source is not None:
        prepare_master(args.source, ROOT / MASTER_PATH)
    make_assets(ROOT)


if __name__ == '__main__':
    main()
