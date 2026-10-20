"""The approved icon artwork must survive builds without private metadata."""
import io
from pathlib import Path
import struct

from PIL import Image, ImageDraw, PngImagePlugin
import pytest

from scripts.make_icon import (
    ICON_SIZES, MASTER_PATH, ROOT, make_assets, make_icon, prepare_master, resize_icon,
)


def artwork(path: Path, *, metadata: bool = False) -> Path:
    image = Image.new('RGBA', (512, 512), (230, 210, 190, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((64, 64, 447, 447), fill=(211, 31, 48, 255))
    draw.rectangle((320, 96, 415, 191), fill=(22, 184, 86, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {}
    if metadata:
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text('Author', 'private-test-artist')
        png_info.add_itxt('XML:com.adobe.xmp', '<xmp>private-test-workstation</xmp>')
        exif = Image.Exif()
        exif[315] = 'private-test-artist'
        options = {'pnginfo': png_info, 'exif': exif}
    image.save(path, **options)
    return path


def assert_clean_transparency(image: Image.Image) -> None:
    assert image.mode == 'RGBA'
    alpha = image.getchannel('A')
    assert alpha.getextrema() == (0, 255)
    assert image.getpixel((0, 0)) == (0, 0, 0, 0)
    assert all(r == g == b == 0 for r, g, b, a in image.get_flattened_data() if a == 0)


def ico_frames(path: Path):
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from('<HHH', data)
    assert (reserved, kind) == (0, 1)
    frames = {}
    for index in range(count):
        width, height, colors, reserved, planes, bits, length, offset = struct.unpack_from(
            '<BBBBHHII', data, 6 + 16 * index)
        width, height = width or 256, height or 256
        assert width == height and planes == 0 and bits == 32
        assert colors == reserved == 0
        with Image.open(io.BytesIO(data[offset:offset + length])) as image:
            assert image.format == 'PNG' and image.info == {}
            frames[width] = image.copy()
    return frames


def test_import_strips_metadata_and_hidden_rgb_while_preserving_padding(tmp_path):
    source = artwork(tmp_path / 'source.png', metadata=True)
    original = source.read_bytes()
    master = tmp_path / 'master.png'
    prepare_master(source, master)
    assert source.read_bytes() == original
    with Image.open(master) as image:
        assert image.size == (1024, 1024)
        assert image.info == {} and not image.getexif()
        assert_clean_transparency(image)
        # Import preserves the composition and transparent canvas margins.
        assert image.getpixel((512, 512)) == (211, 31, 48, 255)
        assert image.getpixel((736, 288)) == (22, 184, 86, 255)
        assert image.getpixel((64, 512)) == (0, 0, 0, 0)
    assert b'private-test' not in master.read_bytes()


def test_ico_contains_every_windows_size_using_the_selected_artwork(tmp_path):
    source = artwork(tmp_path / 'source.png', metadata=True)
    output = tmp_path / 'icons' / 'custom.ico'
    make_icon(output, source)
    frames = ico_frames(output)
    assert set(frames) == set(ICON_SIZES)
    for size, image in frames.items():
        assert_clean_transparency(image)
        assert image.size == (size, size)
        assert image.getpixel((size // 2, size // 2)) == (211, 31, 48, 255)
    assert b'private-test' not in output.read_bytes()


def test_resampling_does_not_add_hidden_background_color_to_edges():
    image = Image.new('RGBA', (256, 256), (0, 255, 0, 0))
    ImageDraw.Draw(image).ellipse((31, 31, 224, 224), fill=(255, 0, 0, 255))
    small = resize_icon(image, 16)
    assert any(0 < alpha < 255 for _, _, _, alpha in small.get_flattened_data())
    assert all((r, g, b) == (255, 0, 0) for r, g, b, alpha in small.get_flattened_data() if alpha)
    assert_clean_transparency(small)


def test_asset_generation_stays_in_explicit_root_and_keeps_master(tmp_path):
    master = artwork(tmp_path / MASTER_PATH, metadata=True)
    before = master.read_bytes()
    make_assets(tmp_path)
    assert master.read_bytes() == before
    windows_icon = tmp_path / 'packaging' / 'assets' / 'app.ico'
    assert set(ico_frames(windows_icon)) == set(ICON_SIZES)
    assert (tmp_path / 'web' / 'assets' / 'favicon.ico').read_bytes() == windows_icon.read_bytes()
    with Image.open(tmp_path / 'web' / 'assets' / 'app.png') as web_icon:
        assert web_icon.size == (256, 256) and web_icon.info == {}
        assert_clean_transparency(web_icon)
        assert web_icon.getpixel((128, 128)) == (211, 31, 48, 255)


def test_missing_artwork_fails_without_placeholder_or_partial_outputs(tmp_path):
    with pytest.raises(FileNotFoundError, match='App icon artwork is missing'):
        make_assets(tmp_path)
    with pytest.raises(FileNotFoundError, match='App icon artwork is missing'):
        make_icon(tmp_path / 'app.ico', tmp_path / 'missing.png')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('size,format', [((512, 256), 'PNG'), ((128, 128), 'PNG'), ((512, 512), 'BMP')])
def test_unsuitable_artwork_fails_clearly(tmp_path, size, format):
    source = tmp_path / 'source.png'
    Image.new('RGBA', size, 'red').save(source, format=format)
    with pytest.raises(ValueError, match='App icon artwork must be'):
        make_icon(tmp_path / 'app.ico', source)
    assert not (tmp_path / 'app.ico').exists()


def test_committed_master_is_clean_and_all_assets_can_be_reproduced(tmp_path):
    source = ROOT / MASTER_PATH
    with Image.open(source) as image:
        assert image.size == (1024, 1024) and image.info == {} and not image.getexif()
        assert_clean_transparency(image)
    # Rebuild in an isolated root so tests cannot silently rewrite real assets.
    imported = tmp_path / MASTER_PATH
    imported.parent.mkdir(parents=True)
    imported.write_bytes(source.read_bytes())
    make_assets(tmp_path)
    for relative in ('packaging/assets/app.ico', 'web/assets/app.png', 'web/assets/favicon.ico'):
        assert (tmp_path / relative).read_bytes() == (ROOT / relative).read_bytes()
