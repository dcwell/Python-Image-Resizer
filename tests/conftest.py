"""Shared pytest fixtures: synthetic image factories."""

from __future__ import annotations

import os

import pytest
from PIL import Image


def _noise_rgb(width: int, height: int) -> Image.Image:
    """A fully random RGB image (worst case for compression)."""
    return Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))


def _noise_rgba(width: int, height: int) -> Image.Image:
    """Random RGB with a real alpha gradient (genuine transparency)."""
    base = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3)).convert("RGBA")
    alpha = Image.linear_gradient("L").resize((width, height))
    base.putalpha(alpha)
    return base


@pytest.fixture
def noise_rgb():
    return _noise_rgb


@pytest.fixture
def noise_rgba():
    return _noise_rgba
