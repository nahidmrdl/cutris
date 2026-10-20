import pytest
import numpy as np
from PIL import Image

from image_geometry import apply_transform, normalize_transform, output_size


def test_crop_then_resize_keeps_source_and_geometry():
    image = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    image.paste((30, 100, 220, 255), (3, 2, 9, 6))
    settings = {"crop": {"x": 3, "y": 2, "width": 6, "height": 4},
                "resize": {"width": 3, "height": 2}}
    result = apply_transform(image, settings)
    assert result.mode == "RGBA" and result.size == (3, 2)
    assert result.getpixel((1, 1)) == (30, 100, 220, 255)
    assert image.size == (12, 8) and image.getpixel((0, 0)) == (0, 0, 0, 0)
    assert output_size(image.size, settings) == result.size


@pytest.mark.parametrize("size", [(5, 5), (80, 80)])
def test_resizing_does_not_bleed_hidden_background_colors(size):
    image = Image.new("RGBA", (20, 20), (0, 255, 0, 0))
    image.paste((255, 0, 0, 255), (5, 5, 15, 15))
    result = apply_transform(image, {"resize": {"width": size[0], "height": size[1]}})
    pixels = [tuple(pixel) for pixel in np.asarray(result).reshape(-1, 4)]
    visible = [pixel for pixel in pixels if pixel[3]]
    assert visible and any(0 < pixel[3] < 255 for pixel in visible)
    assert all(pixel[:3] == (255, 0, 0) for pixel in visible)
    assert all(pixel[:3] == (0, 0, 0) for pixel in pixels if pixel[3] == 0)


def test_fully_transparent_images_and_one_pixel_output_are_valid():
    image = Image.new("RGBA", (20, 20), (100, 80, 60, 0))
    result = apply_transform(image, {"crop": {"x": 19, "y": 19, "width": 1, "height": 1},
                                     "resize": {"width": 2, "height": 2}})
    assert result.size == (2, 2) and result.getbbox() is None
    assert output_size(image.size) == image.size
    assert normalize_transform(image.size) == {"crop": None, "resize": None}


@pytest.mark.parametrize("settings", [
    {"crop": {"x": -1, "y": 0, "width": 1, "height": 1}},
    {"crop": {"x": 9, "y": 0, "width": 2, "height": 1}},
    {"crop": {"x": 0, "y": 9, "width": 1, "height": 2}},
    {"crop": {"x": 0, "y": 0, "width": 0, "height": 1}},
    {"crop": {"x": 0.5, "y": 0, "width": 1, "height": 1}},
    {"crop": {"x": False, "y": 0, "width": 1, "height": 1}},
    {"crop": {"x": 0, "y": 0, "width": 1, "height": 1, "extra": 1}},
    {"resize": {"width": "2", "height": 2}},
    {"resize": {"width": 0, "height": 2}},
    {"resize": {"width": 12001, "height": 1}},
    {"resize": {"width": 6000, "height": 4001}},
    {"resize": {"width": 2}},
    {"unknown": 1},
])
def test_invalid_geometry_is_rejected_before_image_allocation(settings):
    with pytest.raises(ValueError):
        normalize_transform((10, 10), settings)


def test_output_limits_are_inclusive():
    assert output_size((10, 10), {"resize": {"width": 12000, "height": 2000}}) == (12000, 2000)
