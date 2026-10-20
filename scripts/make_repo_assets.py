"""Compose the README hero from the project's approved, metadata-free icon.

Run from the repository root:
    .venv/Scripts/python.exe scripts/make_repo_assets.py

The application artwork is resized and composited without retouching. The PNG
contains no source metadata, local paths, or personal information.
"""
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def font(size: int, bold: bool = False):
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    name = 'segoeuib.ttf' if bold else 'segoeui.ttf'
    try:
        return ImageFont.truetype(str(fonts / name), size)
    except OSError:
        return ImageFont.load_default(size=size)


def tracked_text(draw, xy, value, face, fill, tracking):
    x, y = xy
    for character in value:
        draw.text((x, y), character, font=face, fill=fill, anchor='lt')
        x += draw.textlength(character, font=face) + tracking


def main():
    width, height = 1600, 430
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    dark, lime = '#12191d', '#a4ed75'
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=24, fill=dark)
    draw.rectangle((0, 406, width - 1, height - 1), fill=lime)

    tracked_text(draw, (88, 74), 'LOCAL AI. PRECISE CUTOUTS.', font(17, True), lime, 3.3)
    draw.text((77, 122), 'cutrix', font=font(224, True), fill='#f4f6f0', anchor='lt')
    draw.text((90, 336), 'Your images stay on your computer.', font=font(22), fill='#a8b1b2', anchor='lt')
    draw.line((883, 73, 883, 355), fill='#303c40', width=2)

    with Image.open(ROOT / 'packaging' / 'assets' / 'app.png') as artwork:
        icon = artwork.convert('RGBA').resize((420, 420), Image.Resampling.LANCZOS)
    image.alpha_composite(icon, (1017, -7))
    draw.line(((1022, 96), (1022, 73), (1045, 73)), fill=lime, width=3)
    draw.line(((1409, 326), (1432, 326), (1432, 303)), fill=lime, width=3)

    destination = ROOT / 'docs' / 'assets' / 'hero.png'
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


if __name__ == '__main__':
    main()
