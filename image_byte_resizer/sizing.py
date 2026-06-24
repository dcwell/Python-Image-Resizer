"""Parse and format target sizes.

A *target size* is a whole-number value plus a unit, e.g. ``2MB`` or ``500KB``.

Units
-----
* Decimal (default): ``B``, ``KB``, ``MB``, ``GB``, ``TB`` (powers of 1000).
* Binary (explicit):  ``KiB``, ``MiB``, ``GiB``, ``TiB`` (powers of 1024).

Decimal is the default because a website cap is only honored if we stay under the
*smaller* possible byte count, and ``MB`` (x1,000,000) is smaller than ``MiB``
(x1,048,576). Targeting decimal therefore keeps us safely under either reading.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .errors import SizeParseError

# canonical unit -> (multiplier in bytes, is_binary)
_UNITS: dict[str, tuple[int, bool]] = {
    "B": (1, False),
    "KB": (1000, False),
    "MB": (1000**2, False),
    "GB": (1000**3, False),
    "TB": (1000**4, False),
    "KiB": (1024, True),
    "MiB": (1024**2, True),
    "GiB": (1024**3, True),
    "TiB": (1024**4, True),
}

# lowercased lookup -> canonical
_CANONICAL: dict[str, str] = {u.lower(): u for u in _UNITS}

_ACCEPTED_DISPLAY = "B, KB, MB, GB, TB, KiB, MiB, GiB, TiB"

# Accept an optional fractional part so we can give a *targeted* error for it.
_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")


@dataclass(frozen=True)
class TargetSize:
    """A parsed, whole-number target size.

    Attributes:
        value: The integer the user typed (e.g. ``2``).
        unit: Canonical unit string (e.g. ``"MB"``).
        bytes: ``value * multiplier`` in bytes.
        is_binary: True for binary units (``KiB``/``MiB``/...).
    """

    value: int
    unit: str
    bytes: int
    is_binary: bool

    @property
    def token(self) -> str:
        """Filename token, e.g. ``"2MB"`` (used in the output filename)."""
        return f"{self.value}{self.unit}"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.token


def parse_target_size(text: str) -> TargetSize:
    """Parse a string like ``"2MB"`` into a :class:`TargetSize`.

    Raises:
        SizeParseError: if the value is fractional, the unit is unknown, the
            value is not positive, or the string is otherwise unparseable.
    """
    if text is None:
        raise SizeParseError("No target size was provided.")

    match = _SIZE_RE.match(str(text))
    if not match:
        raise SizeParseError(
            f"Could not understand size {text!r}. "
            f"Use a whole number and a unit, e.g. 2MB, 500KB, 3MiB. "
            f"Accepted units: {_ACCEPTED_DISPLAY}."
        )

    number, unit_raw = match.group(1), match.group(2)

    if "." in number:
        raise SizeParseError(
            f"Target sizes must be whole numbers, not {text!r}. "
            f"Use an equivalent whole number in a smaller unit "
            f"(e.g. 1500KB instead of 1.5MB)."
        )

    canonical = _CANONICAL.get(unit_raw.lower())
    if canonical is None:
        raise SizeParseError(
            f"Unknown unit {unit_raw!r} in {text!r}. "
            f"Accepted units: {_ACCEPTED_DISPLAY}."
        )

    value = int(number)
    if value <= 0:
        raise SizeParseError(
            f"Target size must be a positive whole number, got {text!r}."
        )

    multiplier, is_binary = _UNITS[canonical]
    return TargetSize(
        value=value,
        unit=canonical,
        bytes=value * multiplier,
        is_binary=is_binary,
    )


def effective_target_bytes(target_bytes: int, margin: float) -> int:
    """Apply the safety margin to a raw target.

    Returns ``floor(target_bytes * (1 - margin))`` clamped to a minimum of 1 byte.
    A larger margin leaves more headroom under the website's stated cap.
    """
    if not (0.0 <= margin < 1.0):
        raise ValueError("margin must be in the range [0.0, 1.0).")
    return max(1, math.floor(target_bytes * (1.0 - margin)))


def format_bytes(n: int) -> str:
    """Human-readable byte count for display (decimal units)."""
    value = float(n)
    if value >= 1000**3:
        return f"{value / 1000**3:.2f} GB"
    if value >= 1000**2:
        return f"{value / 1000**2:.2f} MB"
    if value >= 1000:
        return f"{value / 1000:.1f} KB"
    return f"{int(n)} B"
