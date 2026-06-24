"""Integration tests for the resize engine using synthetic images."""

from __future__ import annotations

from PIL import Image

from image_byte_resizer.formats import has_transparency
from image_byte_resizer.resizer import resize_to_target
from image_byte_resizer.sizing import parse_target_size


def _save(img: Image.Image, path, **kw):
    img.save(path, **kw)
    return path


# --------------------------------------------------------------------------- #
# JPEG (lossy) — guaranteed path
# --------------------------------------------------------------------------- #
def test_jpeg_hits_target_and_preserves_dimensions(tmp_path, noise_rgb):
    src = _save(noise_rgb(256, 256), tmp_path / "src.jpg", quality=95)
    target = parse_target_size("40KB")

    result = resize_to_target(src, target)

    assert result.met_target is True
    assert result.output_path.exists()
    assert result.final_bytes <= result.effective_bytes
    assert result.no_op is False

    with Image.open(result.output_path) as out:
        assert out.size == (256, 256)          # dimensions unchanged
        assert out.format == "JPEG"            # format unchanged


def test_jpeg_output_name_and_extension(tmp_path, noise_rgb):
    src = _save(noise_rgb(256, 256), tmp_path / "vacation.jpg", quality=95)
    result = resize_to_target(src, parse_target_size("30KB"))
    assert result.output_path.name == "vacation_Resized_30KB.jpg"


def test_jpeg_floor_writes_best_effort_when_target_impossible(tmp_path, noise_rgb):
    # 1KB is unreachable for a 256x256 noise JPEG without resizing.
    src = _save(noise_rgb(256, 256), tmp_path / "src.jpg", quality=95)
    result = resize_to_target(src, parse_target_size("1KB"))

    assert result.met_target is False
    assert result.output_path.exists()
    assert result.warnings  # explains the miss
    with Image.open(result.output_path) as out:
        assert out.size == (256, 256)
        assert out.format == "JPEG"


# --------------------------------------------------------------------------- #
# PNG — stays PNG; lossless default may miss, quantize opt-in
# --------------------------------------------------------------------------- #
def test_png_lossless_misses_target_but_writes_and_warns(tmp_path, noise_rgb):
    src = _save(noise_rgb(200, 200), tmp_path / "src.png")
    result = resize_to_target(src, parse_target_size("5KB"), png_strategy="lossless")

    assert result.met_target is False
    assert result.output_path.exists()
    assert result.final_bytes > result.effective_bytes
    assert any("quantize" in w for w in result.warnings)
    with Image.open(result.output_path) as out:
        assert out.size == (200, 200)
        assert out.format == "PNG"  # never converted


def test_png_quantize_hits_target(tmp_path, noise_rgb):
    src = _save(noise_rgb(200, 200), tmp_path / "src.png")
    result = resize_to_target(src, parse_target_size("30KB"), png_strategy="quantize")

    assert result.met_target is True
    assert result.final_bytes <= result.effective_bytes
    assert "quantize" in result.method
    with Image.open(result.output_path) as out:
        assert out.size == (200, 200)
        assert out.format == "PNG"


def test_png_quantize_preserves_transparency(tmp_path, noise_rgba):
    src = _save(noise_rgba(200, 200), tmp_path / "icon.png")
    # Sanity: the source really has transparency.
    with Image.open(src) as original:
        assert has_transparency(original)

    result = resize_to_target(src, parse_target_size("30KB"), png_strategy="quantize")

    assert result.output_path.name == "icon_Resized_30KB.png"
    with Image.open(result.output_path) as out:
        assert out.size == (200, 200)
        assert out.format == "PNG"
        assert has_transparency(out)  # alpha survived quantization


# --------------------------------------------------------------------------- #
# No-op and dry-run
# --------------------------------------------------------------------------- #
def test_no_op_when_target_exceeds_original(tmp_path, noise_rgb):
    src = _save(noise_rgb(16, 16), tmp_path / "tiny.jpg", quality=95)
    original_bytes = src.stat().st_size
    result = resize_to_target(src, parse_target_size("10MB"))

    assert result.no_op is True
    assert result.met_target is True
    assert result.final_bytes == original_bytes
    assert result.output_path.exists()
    # The copy is byte-identical to the source.
    assert result.output_path.read_bytes() == src.read_bytes()


def test_dry_run_writes_nothing(tmp_path, noise_rgb):
    src = _save(noise_rgb(256, 256), tmp_path / "src.jpg", quality=95)
    result = resize_to_target(src, parse_target_size("30KB"), dry_run=True)

    assert result.dry_run is True
    assert result.final_bytes > 0
    assert not result.output_path.exists()  # nothing written


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
def test_missing_file_raises(tmp_path, noise_rgb):
    from image_byte_resizer.errors import UnsupportedImageError
    import pytest

    with pytest.raises(UnsupportedImageError):
        resize_to_target(tmp_path / "nope.jpg", parse_target_size("1MB"))


def test_non_image_file_raises(tmp_path):
    from image_byte_resizer.errors import UnsupportedImageError
    import pytest

    bogus = tmp_path / "notimage.jpg"
    bogus.write_text("this is not an image")
    with pytest.raises(UnsupportedImageError):
        resize_to_target(bogus, parse_target_size("1MB"))
