"""Tests for output-filename construction."""

from __future__ import annotations

from pathlib import Path

from image_byte_resizer.naming import build_output_path


def test_basic_name(tmp_path):
    src = tmp_path / "photo.jpg"
    out = build_output_path(src, "2MB")
    assert out == tmp_path / "photo_Resized_2MB.jpg"


def test_extension_is_preserved_including_case(tmp_path):
    src = tmp_path / "logo.PNG"
    out = build_output_path(src, "300KB")
    assert out.name == "logo_Resized_300KB.PNG"


def test_output_dir_override(tmp_path):
    src = tmp_path / "a" / "photo.jpg"
    dest = tmp_path / "out"
    dest.mkdir()
    out = build_output_path(src, "1MB", output_dir=dest)
    assert out == dest / "photo_Resized_1MB.jpg"


def test_collision_suffixing(tmp_path):
    src = tmp_path / "photo.jpg"
    # First output name is free.
    first = build_output_path(src, "2MB")
    assert first.name == "photo_Resized_2MB.jpg"

    # Occupy it; next call should pick " (1)".
    first.write_bytes(b"x")
    second = build_output_path(src, "2MB")
    assert second.name == "photo_Resized_2MB (1).jpg"

    # Occupy that too; next call should pick " (2)".
    second.write_bytes(b"x")
    third = build_output_path(src, "2MB")
    assert third.name == "photo_Resized_2MB (2).jpg"


def test_never_overwrites_original_named_collision(tmp_path):
    # An original that happens to share the output name must not be overwritten.
    src = tmp_path / "img.png"
    src.write_bytes(b"original")
    clashing = tmp_path / "img_Resized_50KB.png"
    clashing.write_bytes(b"prior-run")
    out = build_output_path(src, "50KB")
    assert out != clashing
    assert Path(out).name == "img_Resized_50KB (1).png"
