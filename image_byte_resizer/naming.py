"""Build the output filename.

The output is named ``{stem}_Resized_{token}{ext}`` next to the source (or in
``output_dir``). The **source extension is always preserved** because the format
is never converted. If the target name already exists, a `` (1)``, `` (2)``, ...
suffix is appended so the original and any prior runs are never overwritten.
"""

from __future__ import annotations

from pathlib import Path


def build_output_path(
    source_path: str | Path,
    token: str,
    output_dir: str | Path | None = None,
) -> Path:
    """Return a collision-free output path for the resized copy.

    Args:
        source_path: Path to the original image.
        token: The size token to embed, e.g. ``"2MB"``.
        output_dir: Directory for the output; defaults to the source's directory.
    """
    source = Path(source_path)
    directory = Path(output_dir) if output_dir is not None else source.parent
    stem = source.stem
    ext = source.suffix  # includes the dot, original case; "" if none

    base = f"{stem}_Resized_{token}"
    candidate = directory / f"{base}{ext}"

    index = 1
    while candidate.exists():
        candidate = directory / f"{base} ({index}){ext}"
        index += 1
    return candidate
