"""Tests for sizing: parsing, units, margin, formatting."""

from __future__ import annotations

import pytest

from image_byte_resizer.errors import SizeParseError
from image_byte_resizer.sizing import (
    effective_target_bytes,
    format_bytes,
    parse_target_size,
)


@pytest.mark.parametrize(
    "text, expected_value, expected_bytes, expected_unit, expected_binary",
    [
        ("2MB", 2, 2_000_000, "MB", False),
        ("500KB", 500, 500_000, "KB", False),
        ("1GB", 1, 1_000_000_000, "GB", False),
        ("10B", 10, 10, "B", False),
        ("3MiB", 3, 3 * 1024 * 1024, "MiB", True),
        ("4KiB", 4, 4 * 1024, "KiB", True),
        ("  2 MB ", 2, 2_000_000, "MB", False),  # whitespace tolerated
        ("2mb", 2, 2_000_000, "MB", False),       # case-insensitive
    ],
)
def test_parse_valid(text, expected_value, expected_bytes, expected_unit, expected_binary):
    target = parse_target_size(text)
    assert target.value == expected_value
    assert target.bytes == expected_bytes
    assert target.unit == expected_unit
    assert target.is_binary is expected_binary


def test_token_uses_canonical_unit_and_whole_number():
    assert parse_target_size("2mb").token == "2MB"
    assert parse_target_size("3MiB").token == "3MiB"
    assert parse_target_size("500kb").token == "500KB"


def test_reject_fractional():
    with pytest.raises(SizeParseError) as exc:
        parse_target_size("1.5MB")
    assert "whole number" in str(exc.value).lower()


def test_reject_unknown_unit():
    with pytest.raises(SizeParseError) as exc:
        parse_target_size("2ZB")
    assert "unit" in str(exc.value).lower()


def test_reject_zero():
    with pytest.raises(SizeParseError):
        parse_target_size("0MB")


def test_reject_garbage():
    with pytest.raises(SizeParseError):
        parse_target_size("abc")


def test_reject_missing_unit():
    with pytest.raises(SizeParseError):
        parse_target_size("1000")


def test_effective_target_applies_margin():
    assert effective_target_bytes(1_000_000, 0.02) == 980_000
    assert effective_target_bytes(1_000_000, 0.0) == 1_000_000
    assert effective_target_bytes(10, 0.999) == 1  # clamped to >= 1


def test_effective_target_rejects_bad_margin():
    with pytest.raises(ValueError):
        effective_target_bytes(1000, 1.0)
    with pytest.raises(ValueError):
        effective_target_bytes(1000, -0.1)


@pytest.mark.parametrize(
    "n, expected",
    [
        (2_000_000, "2.00 MB"),
        (1_910_000, "1.91 MB"),
        (1500, "1.5 KB"),
        (500, "500 B"),
        (2_500_000_000, "2.50 GB"),
    ],
)
def test_format_bytes(n, expected):
    assert format_bytes(n) == expected
