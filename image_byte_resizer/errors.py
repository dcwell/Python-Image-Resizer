"""Exception types for the image byte-size resizer."""

from __future__ import annotations


class ImageResizerError(Exception):
    """Base class for all errors raised by this package."""


class SizeParseError(ImageResizerError, ValueError):
    """Raised when a target-size string cannot be parsed.

    Examples that trigger this: fractional sizes (``1.5MB``), unknown units
    (``2ZB``), or strings that don't look like ``<integer><unit>`` at all.
    """


class UnsupportedImageError(ImageResizerError):
    """Raised when the input image cannot be processed.

    Covers missing files, files Pillow cannot identify, and inputs that v1 does
    not support (e.g. animated GIF/WebP).
    """
