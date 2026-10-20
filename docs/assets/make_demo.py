r"""Build the README comparison from synthetic artwork and real model output.

Run from the repository root with the source environment and detail model ready:
    .venv\Scripts\python.exe docs/assets/make_demo.py

The layout adds labels and a checkerboard for display; it does not retouch the
cutout. No user images, filenames, local paths, or personal metadata are used.
"""
from pathlib import Path
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine import Remover, load_image  # noqa: E402


def font(size, bold=False):
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    name = 'segoeuib.ttf' if bold else 'segoeui.ttf'
    try:
        return ImageFont.truetype(str(fonts / name), size)
    except OSError:
        return ImageFont.load_default(size=size)


def main():
    source = load_image((ROOT / 'tests' / 'synthetic-character.png').read_bytes())
    cutout, _ = Remover().process(source, 'detail', 'white')

    width, height = 1600, 872
    image = Image.new('RGB', (width, height), '#f3f5f0')
    draw = ImageDraw.Draw(image)
    dark = '#182328'
    draw.text((50, 36), 'From original to transparent PNG.', font=font(46, True), fill=dark)
    draw.text((52, 105), 'BiRefNet  /  Maximum detail  /  White illustration', font=font(22), fill='#60706a')

    left = (48, 169, 780, 791)
    right = (820, 169, 1552, 791)
    draw.rounded_rectangle(left, radius=22, fill='white', outline='#dce2d8', width=2)
    draw.rounded_rectangle(right, radius=22, fill=dark)
    draw.text((80, 193), '01  /  ORIGINAL', font=font(17, True), fill='#61716a')
    draw.text((852, 193), '02  /  CUTOUT', font=font(17, True), fill='#a4ed75')

    # The input and actual AI result use the same size and placement.
    displayed = (500, 500)
    original = source.convert('RGB').resize(displayed, Image.Resampling.LANCZOS)
    result = cutout.resize(displayed, Image.Resampling.LANCZOS)
    image.paste(original, (164, 237))
    board = Image.new('RGB', displayed, dark)
    checker = ImageDraw.Draw(board)
    for row in range(0, 500, 20):
        for col in range(0, 500, 20):
            color = '#28373a' if (row // 20 + col // 20) % 2 else '#213033'
            checker.rectangle((col, row, col + 19, row + 19), fill=color)
    board.paste(result, (0, 0), result.getchannel('A'))
    image.paste(board, (936, 237))
    draw.text((80, 752), '1024 × 1024  ·  White background', font=font(17), fill='#61716a')
    draw.text((852, 752), '1024 × 1024  ·  Transparent PNG', font=font(17), fill='#b8c7c0')
    draw.text((52, 820), 'Synthetic artwork. Actual cutris output. No manual retouching.', font=font(18), fill='#60706a')
    image.save(Path(__file__).with_name('demo.png'), optimize=True)


if __name__ == '__main__':
    main()
