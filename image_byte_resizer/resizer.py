"""Core compression engine.

Reduces an image's byte size *without changing its dimensions or format*:

  * Lossy formats (JPEG/WebP): binary-search the encoder ``quality`` for the
    highest quality whose encoded size fits under the (margin-adjusted) target.
  * PNG: lossless ``optimize`` by default (may miss the target -> best-effort +
    warning). With ``png_strategy="quantize"``, binary-search the palette size
    (color count) to trade colors for bytes while staying a valid PNG.
  * Other lossless formats: best-effort lossless save.

Metadata/EXIF is dropped on re-encode (a free size win). The original file is
never modified; a new copy is written to a collision-free path.
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .errors import UnsupportedImageError
from .formats import (
    detect_format,
    has_transparency,
    is_animated,
    is_lossy,
    prepare_for_format,
)
from .naming import build_output_path
from .sizing import TargetSize, effective_target_bytes, format_bytes


@dataclass
class Trial:
    """One step of a binary search (for verbose output)."""

    label: str
    size: int
    fits: bool


@dataclass
class ResizeResult:
    """Outcome of a resize operation."""

    source_path: Path
    output_path: Path
    image_format: str
    width: int
    height: int
    original_bytes: int
    requested_bytes: int
    effective_bytes: int
    final_bytes: int
    method: str
    met_target: bool
    target: TargetSize
    margin: float
    dry_run: bool = False
    no_op: bool = False
    trials: list[Trial] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _encode(img: Image.Image, fmt: str, **params) -> bytes:
    """Encode ``img`` to an in-memory buffer and return the bytes.

    No EXIF/metadata is passed, so re-encoding strips it.
    """
    buffer = io.BytesIO()
    img.save(buffer, format=fmt, **params)
    return buffer.getvalue()


def _search_quality(
    img: Image.Image,
    fmt: str,
    target: int,
    q_min: int,
    q_max: int,
    max_iter: int,
    extra: dict,
    trials: list[Trial],
) -> tuple[bytes, str, bool]:
    """Binary-search encoder quality. Returns (blob, label, met_target)."""
    best: tuple[int, bytes] | None = None
    lo, hi = q_min, q_max
    iterations = 0
    while lo <= hi and iterations < max_iter:
        mid = (lo + hi) // 2
        blob = _encode(img, fmt, quality=mid, **extra)
        size = len(blob)
        fits = size <= target
        trials.append(Trial(f"quality={mid}", size, fits))
        if fits:
            best = (mid, blob)
            lo = mid + 1  # try for higher quality
        else:
            hi = mid - 1
        iterations += 1

    if best is not None:
        return best[1], f"quality={best[0]}", True

    # Floor: even the lowest quality is over target -> best effort at q_min.
    blob = _encode(img, fmt, quality=q_min, **extra)
    return blob, f"quality={q_min} (best effort)", len(blob) <= target


def _encode_png_quantized(base: Image.Image, colors: int, alpha: bool) -> bytes:
    """Quantize to ``colors`` and encode as an optimized PNG (stays PNG)."""
    method = Image.Quantize.FASTOCTREE if alpha else Image.Quantize.MEDIANCUT
    quantized = base.quantize(colors=colors, method=method)
    return _encode(quantized, "PNG", optimize=True)


def _resize_png(
    img: Image.Image,
    target: int,
    strategy: str,
    max_iter: int,
    trials: list[Trial],
    warnings: list[str],
) -> tuple[bytes, str, bool]:
    """PNG path: lossless first, optional palette quantization."""
    lossless = _encode(img, "PNG", optimize=True)
    trials.append(Trial("lossless", len(lossless), len(lossless) <= target))
    if len(lossless) <= target:
        return lossless, "lossless", True

    if strategy != "quantize":
        warnings.append(
            "PNG could not reach the target losslessly. Wrote the best-effort "
            "lossless PNG (format and quality preserved). Re-run with "
            "--png-strategy quantize to trade colors for size."
        )
        return lossless, "lossless (best effort)", False

    alpha = has_transparency(img)
    base = img.convert("RGBA") if alpha else img.convert("RGB")

    best: tuple[int, bytes] | None = None
    lo, hi = 2, 256
    iterations = 0
    while lo <= hi and iterations < max_iter:
        mid = (lo + hi) // 2
        blob = _encode_png_quantized(base, mid, alpha)
        size = len(blob)
        fits = size <= target
        trials.append(Trial(f"colors={mid}", size, fits))
        if fits:
            best = (mid, blob)
            lo = mid + 1  # try for more colors (higher fidelity)
        else:
            hi = mid - 1
        iterations += 1

    if best is not None:
        return best[1], f"quantize colors={best[0]}", True

    # Floor: even a 2-color palette is over target -> best effort.
    smallest = _encode_png_quantized(base, 2, alpha)
    if len(smallest) <= len(lossless):
        warnings.append(
            "PNG could not reach the target even at 2 colors. Wrote the "
            "smallest-palette best-effort PNG (format preserved)."
        )
        return smallest, "quantize colors=2 (best effort)", len(smallest) <= target
    warnings.append(
        "PNG could not reach the target; lossless was smaller than any palette. "
        "Wrote the best-effort lossless PNG (format preserved)."
    )
    return lossless, "lossless (best effort)", False


def _resize_generic_lossless(
    img: Image.Image,
    fmt: str,
    target: int,
    trials: list[Trial],
    warnings: list[str],
) -> tuple[bytes, str, bool]:
    """Best-effort lossless save for non-PNG lossless formats (BMP/TIFF/GIF)."""
    try:
        blob = _encode(img, fmt, optimize=True)
    except (OSError, ValueError):
        blob = _encode(img, fmt)
    met = len(blob) <= target
    trials.append(Trial("lossless", len(blob), met))
    if not met:
        warnings.append(
            f"{fmt} is lossless and has no quality knob; could not reach the "
            f"target without converting or resizing (both out of scope). Wrote "
            f"the best-effort file (format and dimensions preserved)."
        )
    return blob, "lossless", met


def resize_to_target(
    source_path: str | Path,
    target: TargetSize,
    *,
    margin: float = 0.02,
    png_strategy: str = "lossless",
    min_quality: int = 1,
    max_quality: int = 95,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
    max_iter: int = 12,
) -> ResizeResult:
    """Compress ``source_path`` to ``target`` and write a resized copy.

    Args:
        source_path: Path to the source image.
        target: Parsed :class:`~image_byte_resizer.sizing.TargetSize`.
        margin: Safety headroom fraction (0.02 = aim 2% under the target).
        png_strategy: ``"lossless"`` (default) or ``"quantize"``.
        min_quality / max_quality: JPEG/WebP quality search bounds.
        output_dir: Output directory (defaults to the source's directory).
        dry_run: If True, compute everything but write nothing.
        max_iter: Max binary-search iterations.

    Returns:
        A :class:`ResizeResult` describing what happened.

    Raises:
        UnsupportedImageError: missing/corrupt/unidentifiable file, or an
            animated image (unsupported in v1).
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise UnsupportedImageError(f"File not found: {source_path}")
    if not source_path.is_file():
        raise UnsupportedImageError(f"Not a file: {source_path}")

    original_bytes = source_path.stat().st_size

    try:
        img = Image.open(source_path)
        img.load()
    except UnidentifiedImageError as exc:
        raise UnsupportedImageError(
            f"{source_path.name!r} doesn't look like an image Pillow can read."
        ) from exc
    except OSError as exc:
        raise UnsupportedImageError(
            f"Could not read {source_path.name!r}: {exc}"
        ) from exc

    fmt = detect_format(img)
    if not fmt:
        raise UnsupportedImageError(
            f"Could not determine the format of {source_path.name!r}."
        )
    if is_animated(img):
        raise UnsupportedImageError(
            f"Animated {fmt} images aren't supported in v1 (resizing would drop "
            f"frames). Extract a single frame first."
        )

    width, height = img.size
    requested = target.bytes
    effective = effective_target_bytes(requested, margin)
    output_path = build_output_path(source_path, target.token, output_dir)

    trials: list[Trial] = []
    warnings: list[str] = []

    # No-op: the original already fits under the (margin-adjusted) target.
    if original_bytes <= effective:
        if not dry_run:
            shutil.copy2(source_path, output_path)
        return ResizeResult(
            source_path=source_path,
            output_path=output_path,
            image_format=fmt,
            width=width,
            height=height,
            original_bytes=original_bytes,
            requested_bytes=requested,
            effective_bytes=effective,
            final_bytes=original_bytes,
            method="copied unchanged (already within target)",
            met_target=True,
            target=target,
            margin=margin,
            dry_run=dry_run,
            no_op=True,
        )

    if is_lossy(fmt):
        prepared = prepare_for_format(img, fmt)
        if fmt == "WEBP":
            extra = {"method": 6}
        else:  # JPEG / MPO
            extra = {"optimize": True}
        blob, label, met = _search_quality(
            prepared, "JPEG" if fmt in ("JPG",) else fmt,
            effective, min_quality, max_quality, max_iter, extra, trials,
        )
        method = f"{fmt} {label}"
    elif fmt == "PNG":
        blob, label, met = _resize_png(
            img, effective, png_strategy, max_iter, trials, warnings
        )
        method = f"PNG {label}"
    else:
        blob, label, met = _resize_generic_lossless(
            img, fmt, effective, trials, warnings
        )
        method = f"{fmt} {label}"

    final_bytes = len(blob)

    if not met and not warnings:
        warnings.append(
            f"Could not reach the target: smallest achievable was "
            f"{format_bytes(final_bytes)} vs target {format_bytes(effective)}. "
            f"Wrote the best-effort file (dimensions and format preserved)."
        )

    if not dry_run:
        output_path.write_bytes(blob)

    return ResizeResult(
        source_path=source_path,
        output_path=output_path,
        image_format=fmt,
        width=width,
        height=height,
        original_bytes=original_bytes,
        requested_bytes=requested,
        effective_bytes=effective,
        final_bytes=final_bytes,
        method=method,
        met_target=met,
        target=target,
        margin=margin,
        dry_run=dry_run,
        no_op=False,
        trials=trials,
        warnings=warnings,
    )
