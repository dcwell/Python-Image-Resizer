"""Image-format helpers: detection, transparency, animation, mode prep."""

from __future__ import annotations

from PIL import Image

# Formats that expose a lossy quality knob we can binary-search.
LOSSY_FORMATS = {"JPEG", "JPG", "WEBP", "MPO"}


def detect_format(img: Image.Image) -> str:
    """Return the canonical uppercase format string (e.g. ``"JPEG"``)."""
    return (img.format or "").upper()


def is_lossy(fmt: str) -> bool:
    """True if ``fmt`` is a lossy format with a usable quality knob."""
    return fmt.upper() in LOSSY_FORMATS


def is_animated(img: Image.Image) -> bool:
    """True for multi-frame images (animated GIF/WebP/APNG)."""
    return bool(getattr(img, "is_animated", False)) or int(getattr(img, "n_frames", 1)) > 1


def has_transparency(img: Image.Image) -> bool:
    """True if the image carries (real) transparency."""
    if img.mode in ("RGBA", "LA", "PA"):
        try:
            alpha = img.getchannel("A")
            return alpha.getextrema()[0] < 255
        except (ValueError, OSError):
            return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return "transparency" in img.info


def prepare_for_format(img: Image.Image, fmt: str) -> Image.Image:
    """Return an image in a mode the target encoder accepts.

    The format is never changed, so this only normalizes the *color mode*:
      * JPEG: must be RGB or L (grayscale); CMYK/alpha/palette -> RGB.
      * WebP: keep RGB/RGBA/L; palette/other -> RGBA (preserves any alpha) or RGB.
      * PNG and everything else: returned unchanged (PNG supports all modes).
    """
    fmt = fmt.upper()
    if fmt in ("JPEG", "JPG", "MPO"):
        if img.mode in ("RGB", "L"):
            return img
        return img.convert("RGB")
    if fmt == "WEBP":
        if img.mode in ("RGB", "RGBA", "L"):
            return img
        return img.convert("RGBA" if has_transparency(img) else "RGB")
    return img
