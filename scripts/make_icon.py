"""Create the project's original geometric icon, without external artwork."""
from pathlib import Path
from PIL import Image, ImageDraw


def make_icon(destination: Path) -> None:
    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 248, 248), radius=54, fill='#12191d')
    # A sheet of transparency with a clean green cutout in front.
    for row in range(4):
        for col in range(4):
            x, y = 48 + col * 40, 48 + row * 40
            draw.rectangle((x, y, x + 39, y + 39), fill='#3c484d' if (row + col) % 2 else '#253138')
    draw.rounded_rectangle((75, 68, 181, 193), radius=22, fill='#a4ed75')
    draw.polygon(((145, 68), (181, 104), (145, 104)), fill='#d6f9bf')
    draw.polygon(((145, 68), (181, 68), (181, 104)), fill='#12191d')
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == '__main__':
    make_icon(Path(__file__).resolve().parents[1] / 'packaging' / 'assets' / 'app.ico')
