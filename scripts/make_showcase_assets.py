"""Compose README use cases from real cutris exports, without image retouching.

Input images are supplied separately, using the neutral names in ASSETS. They
are not copied into the repository. Processing cache stays under ignored build/.
Run with --process to generate fresh exports with the installed detail model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Remover, load_image, save_png
from image_geometry import apply_transform

ASSETS = ('crystal', 'gift', 'backpack', 'quest', 'token', 'shopping-bag', 'bomb')
DARK = '#12191d'
INK = '#182328'
PAPER = '#f3f5f0'
LIME = '#a4ed75'
MUTED = '#a8b6b3'


def font(size, bold=False):
    directory = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    try:
        return ImageFont.truetype(str(directory / ('segoeuib.ttf' if bold else 'segoeui.ttf')), size)
    except OSError:
        return ImageFont.load_default(size=size)


def text(image, position, value, size=22, color=INK, bold=False, anchor='lt'):
    ImageDraw.Draw(image).text(position, value, font=font(size, bold), fill=color, anchor=anchor)


def box(image, bounds, fill, radius=22, outline=None):
    ImageDraw.Draw(image).rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=2)


def checker(size, light=False):
    first, second = ('#e7ece5', '#f5f7f2') if light else ('#243438', '#1d2b2f')
    image = Image.new('RGB', size, first)
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], 18):
        for x in range(0, size[0], 18):
            if (x // 18 + y // 18) % 2:
                draw.rectangle((x, y, x + 17, y + 17), fill=second)
    return image


def scaled(image, size):
    return image.convert('RGBa').resize(size, Image.Resampling.LANCZOS).convert('RGBA')


def place(image, subject, bounds, trim=False):
    if trim:
        subject = subject.crop(subject.getchannel('A').getbbox())
    left, top, right, bottom = bounds
    ratio = min((right-left) / subject.width, (bottom-top) / subject.height)
    size = (max(1, round(subject.width*ratio)), max(1, round(subject.height*ratio)))
    subject = scaled(subject, size)
    position = (round((left+right-size[0])/2), round((top+bottom-size[1])/2))
    image.paste(subject, position, subject.getchannel('A'))


def save_visual(image, destination):
    # Reconstruct pixels so source metadata never propagates into public images.
    clean = Image.frombytes('RGB', image.size, image.convert('RGB').tobytes())
    clean.save(destination, optimize=True)


def comparison(sources, cutouts, output):
    image = Image.new('RGB', (1600, 880), PAPER)
    text(image, (56, 39), 'From white background to transparent PNG.', 47, bold=True)
    text(image, (59, 108), 'Keep the pale details. Export the subject.', 24, '#63736a')
    box(image, (48, 172, 775, 790), '#ffffff', outline='#dce3d8')
    box(image, (825, 172, 1552, 790), DARK)
    text(image, (79, 196), '01  /  ORIGINAL JPG', 18, '#64736b', True)
    text(image, (856, 196), '02  /  TRANSPARENT PNG', 18, LIME, True)
    image.paste(checker((520, 520)), (929, 239))
    place(image, sources['gift'], (152, 239, 672, 759))
    place(image, cutouts['gift'], (929, 239, 1449, 759))
    text(image, (59, 824), 'Actual cutris output  ·  BiRefNet Maximum detail  ·  White illustration', 20, '#63736a')
    save_visual(image, output / 'background-removal.png')


def use_cases(cutouts, output):
    image = Image.new('RGB', (1600, 970), DARK)
    text(image, (57, 42), 'YOUR PNGS, IN CONTEXT', 17, LIME, True)
    text(image, (53, 88), 'Assets for every screen.', 56, '#f4f6f0', True)
    text(image, (57, 164), 'Game inventories, reward cards and shop graphics.', 24, MUTED)
    cards = [(48, 228, 534, 873), (557, 228, 1043, 873), (1066, 228, 1552, 873)]
    for bounds in cards:
        box(image, bounds, '#1c282c', outline='#324145')
    text(image, (77, 256), 'Game inventory', 27, '#f4f6f0', True)
    inventory = [('crystal', 'Crystal'), ('backpack', 'Backpack'), ('token', 'Token'),
                 ('bomb', 'Game badge'), ('quest', 'Quest'), ('gift', 'Gift')]
    for index, (key, label) in enumerate(inventory):
        x, y = 77 + index % 2 * 215, 313 + index // 2 * 171
        box(image, (x, y, x+197, y+154), '#28383d', radius=14, outline='#3b4c50')
        place(image, cutouts[key], (x+42, y+13, x+155, y+121), trim=True)
        text(image, (x+98, y+127), label, 15, '#c8d4ce', anchor='mt')

    text(image, (586, 256), 'Reward graphics', 27, '#f4f6f0', True)
    box(image, (586, 313, 1014, 761), '#e5d9fa', radius=16)
    text(image, (800, 338), 'DAILY REWARD', 17, '#69558b', True, anchor='mt')
    place(image, cutouts['gift'], (663, 393, 937, 660), trim=True)
    box(image, (672, 692, 928, 738), LIME, radius=13)
    text(image, (800, 704), 'A little something extra', 17, INK, True, anchor='mt')
    text(image, (586, 799), 'Soft highlights stay intact.', 19, MUTED)

    text(image, (1095, 256), 'Shop & interface icons', 27, '#f4f6f0', True)
    box(image, (1095, 313, 1523, 638), '#f2f2e9', radius=16)
    place(image, cutouts['shopping-bag'], (1196, 339, 1422, 596), trim=True)
    for key, label, x in [('token', 'Currency', 1095), ('quest', 'Tasks', 1318)]:
        box(image, (x, 660, x+205, 761), '#28383d', radius=14)
        place(image, cutouts[key], (x+15, 680, x+72, 741), trim=True)
        text(image, (x+90, 699), label, 18, '#e3ebe5', True)
    text(image, (1095, 799), 'Ready for light or dark layouts.', 19, MUTED)
    text(image, (57, 912), 'Illustrative layouts assembled from real cutris PNG exports.', 20, MUTED)
    save_visual(image, output / 'use-cases.png')


def crop_and_resize(cutouts, output):
    subject = cutouts['crystal']
    bounds = subject.getchannel('A').getbbox()
    if bounds is None:
        raise ValueError('The crop example needs visible subject pixels.')
    left, top, right, bottom = bounds
    crop = {'x': left, 'y': top, 'width': right-left, 'height': bottom-top}
    cropped = apply_transform(subject, {'crop': crop})
    size = {'width': 512, 'height': max(1, round(512 * cropped.height / cropped.width))}
    resized = apply_transform(subject, {'crop': crop, 'resize': size})
    image = Image.new('RGB', (1600, 816), PAPER)
    text(image, (56, 40), 'Keep the subject. Lose the extra canvas.', 47, bold=True)
    text(image, (59, 108), 'Auto crop finds transparent margins. Resize sets your final dimensions.', 23, '#63736a')
    panels = [(48, 179, 534, 724), (557, 179, 1043, 724), (1066, 179, 1552, 724)]
    stages = [('01  /  FULL CANVAS', subject), ('02  /  AUTO CROP', cropped), ('03  /  RESIZE', resized)]
    scale = 374 / max(subject.size)
    for index, ((label, current), panel) in enumerate(zip(stages, panels)):
        box(image, panel, '#ffffff', outline='#dce3d8')
        x = panel[0]
        text(image, (x+29, 205), label, 18, '#64736b', True)
        display = (max(1, round(current.width*scale)), max(1, round(current.height*scale))) if index < 2 else (round(374*current.width/max(current.size)), round(374*current.height/max(current.size)))
        px, py = round(x+243-display[0]/2), round(455-display[1]/2)
        board = checker(display)
        picture = scaled(current, display)
        board.paste(picture, (0, 0), picture.getchannel('A'))
        image.paste(board, (px, py))
        ImageDraw.Draw(image).rectangle((px-1, py-1, px+display[0], py+display[1]), outline='#b7c3b6', width=1)
        if index == 0:
            guide = (px+round(left*scale), py+round(top*scale), px+round(right*scale), py+round(bottom*scale))
            ImageDraw.Draw(image).rectangle(guide, outline=LIME, width=3)
        text(image, (x+243, 669), f'{current.width} × {current.height} px', 24, INK, True, anchor='mt')
    text(image, (59, 764), 'Originals stay untouched. Crop and resize settings remain editable.', 21, '#63736a')
    text(image, (1541, 769), 'Previews scaled to fit.', 17, '#63736a', anchor='rt')
    save_visual(image, output / 'crop-and-resize.png')
    return {'asset': 'crystal', 'source_size': list(subject.size), 'crop': crop, 'output_size': list(resized.size)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT / 'build/readme-showcase/input')
    parser.add_argument('--cache-dir', type=Path, default=ROOT / 'build/readme-showcase/cutouts')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/assets/showcase')
    parser.add_argument('--process', action='store_true', help='Regenerate real AI cutouts before composing visuals.')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    sources = {name: load_image((args.input_dir / f'{name}.png').read_bytes()) for name in ASSETS}
    if args.process:
        remover = Remover()
        for name, source in sources.items():
            print(f'Processing {name}...', flush=True)
            result, _ = remover.process(source, 'detail', 'white')
            save_png(result, args.cache_dir / f'{name}.png')
    cutouts = {name: load_image((args.cache_dir / f'{name}.png').read_bytes()) for name in ASSETS}
    for name, result in cutouts.items():
        if result.size != sources[name].size or result.getchannel('A').getextrema() != (0, 255):
            raise ValueError(f'Expected a full-size transparent cutout for {name}.')
    comparison(sources, cutouts, args.output_dir)
    use_cases(cutouts, args.output_dir)
    geometry = crop_and_resize(cutouts, args.output_dir)
    manifest = {'quality': 'detail', 'treatment': 'white', 'manual_touchups': False,
                'presentation': 'Composed graphics, not application screenshots',
                'assets': list(ASSETS), 'geometry_example': geometry}
    (args.output_dir / 'provenance.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print('README visuals generated from real cutris exports.', flush=True)


if __name__ == '__main__':
    main()
