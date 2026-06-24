"""Image Byte-Size Resizer.

Reduce an image's file size *in bytes* (e.g. "get under 2 MB") **without changing
its pixel dimensions**, writing a copy named ``{stem}_Resized_{size+unit}{ext}``
next to the original.

Key design rules (see the project plan):
  * Pixel dimensions are never changed (no resampling).
  * The image format is never converted (PNG stays PNG, JPG stays JPG).
  * Target sizes are whole numbers only (e.g. ``2MB``, not ``1.5MB``).
  * JPEG/WebP are compressed via a binary search on encoder quality.
  * PNG stays lossless by default and may miss the target (best-effort + warn);
    ``--png-strategy quantize`` opts into lossy palette reduction.
"""

from .errors import (
    ImageResizerError,
    SizeParseError,
    UnsupportedImageError,
)
from .sizing import (
    TargetSize,
    parse_target_size,
    format_bytes,
    effective_target_bytes,
)
from .resizer import ResizeResult, Trial, resize_to_target

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "ImageResizerError",
    "SizeParseError",
    "UnsupportedImageError",
    "TargetSize",
    "parse_target_size",
    "format_bytes",
    "effective_target_bytes",
    "ResizeResult",
    "Trial",
    "resize_to_target",
]
