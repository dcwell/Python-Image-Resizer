"""Command-line interface for the image byte-size resizer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import ImageResizerError, SizeParseError, UnsupportedImageError
from .resizer import ResizeResult, resize_to_target
from .sizing import format_bytes, parse_target_size


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-byte-resizer",
        description=(
            "Reduce an image's file size in BYTES without changing its pixel "
            "dimensions or its format. Writes a copy named "
            "{name}_Resized_{size}{ext} next to the original."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  image-byte-resizer vacation.jpg 2MB\n"
            "  image-byte-resizer screenshot.png 300KB --png-strategy quantize\n"
            "  image-byte-resizer photo.jpg 500KB --margin 0.05 -v\n"
        ),
    )
    parser.add_argument("image_path", help="Path to the source image.")
    parser.add_argument(
        "target_size",
        help="Whole-number target size with unit, e.g. 2MB, 500KB, 3MiB (no decimals).",
    )
    parser.add_argument(
        "--png-strategy",
        choices=["lossless", "quantize"],
        default="lossless",
        help=(
            "PNG stays PNG. 'lossless' (default) may miss the target; "
            "'quantize' reduces colors to try harder to hit it."
        ),
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.02,
        help="Safety headroom fraction below the target (default 0.02 = 2%%).",
    )
    parser.add_argument(
        "--min-quality",
        type=int,
        default=1,
        help="Lower bound for the JPEG/WebP quality search (default 1).",
    )
    parser.add_argument(
        "--max-quality",
        type=int,
        default=95,
        help="Upper bound for the JPEG/WebP quality search (default 95).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write the copy into (default: same as the source).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen, but write nothing.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show each binary-search trial.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _print_report(result: ResizeResult, verbose: bool) -> None:
    src = Path(result.source_path)
    out = Path(result.output_path)

    print(
        f"Source : {src.name}  ({format_bytes(result.original_bytes)}, "
        f"{result.width}x{result.height}, {result.image_format})"
    )

    kind = "binary" if result.target.is_binary else "decimal"
    target_line = (
        f"Target : {result.target.value} {result.target.unit} "
        f"({result.requested_bytes:,} bytes, {kind})"
    )
    if result.margin > 0:
        target_line += (
            f" \u2212 {result.margin * 100:g}% margin "
            f"\u2192 {result.effective_bytes:,} bytes"
        )
    print(target_line)

    if verbose and result.trials:
        for i, trial in enumerate(result.trials, 1):
            mark = "\u2713" if trial.fits else "\u2717"
            suffix = " (under)" if trial.fits else ""
            print(f"Trial {i}: {trial.label} \u2192 {format_bytes(trial.size)}  {mark}{suffix}")

    if result.no_op:
        print(
            f"Result : already within target \u2014 copied unchanged, "
            f"{format_bytes(result.final_bytes)}, dimensions unchanged "
            f"({result.width}x{result.height})"
        )
    else:
        status = "" if result.met_target else "  \u26a0\ufe0f over target (best effort)"
        print(
            f"Result : {result.method}, {format_bytes(result.final_bytes)}, "
            f"dimensions unchanged ({result.width}x{result.height}){status}"
        )

    shown = out.name if out.parent == src.parent else str(out)
    label = "Would save" if result.dry_run else "Saved     "
    print(f"{label}: {shown}")

    for warning in result.warnings:
        print(f"\u26a0\ufe0f  {warning}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not (0.0 <= args.margin < 1.0):
        parser.error("--margin must be in the range [0.0, 1.0).")
    if not (1 <= args.min_quality <= args.max_quality <= 100):
        parser.error("require 1 <= --min-quality <= --max-quality <= 100.")

    try:
        target = parse_target_size(args.target_size)
    except SizeParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = resize_to_target(
            args.image_path,
            target,
            margin=args.margin,
            png_strategy=args.png_strategy,
            min_quality=args.min_quality,
            max_quality=args.max_quality,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
    except UnsupportedImageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ImageResizerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_report(result, verbose=args.verbose)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
