# Python-Image-Resizer

Leveraging Copilot with promt enginnering to make a quick image resizer.

Reduce an image's **file size in bytes** (e.g. *"reduce to 2 MB"*) **without
changing its pixel dimensions**. This is re-compression, not resampling — the
photo stays the same resolution, it just takes fewer bytes.

It writes a **copy** next to the original named:

```
{originalName}_Resized_{size}{ext}
```

e.g. `vacation.jpg` → `vacation_Resized_2MB.jpg`.

## Why

Upload forms often say *"file too large — must be under 2 MB"* but you don't
want to shrink the image's width/height. This tool drops the encoder quality
(JPEG/WebP) just enough to slip under the byte cap, leaving the dimensions
untouched.

## Design rules

| Rule | Behavior |
|------|----------|
| **Dimensions** | Never changed (no resizing). |
| **Format** | Never converted — PNG stays PNG, JPG stays JPG. |
| **Sizes** | Whole numbers only (`2MB`, not `1.5MB`). |
| **Units** | Decimal by default (`MB` = 1,000,000 B); binary `MiB`/`KiB` accepted. |
| **Safety margin** | Aims a configurable % under the cap (default 2%). |
| **JPEG / WebP** | Binary-search the quality for the best size ≤ target. |
| **PNG** | Lossless by default — **may miss the target** (writes best-effort + warns). `--png-strategy quantize` opts into lossy palette reduction (still a PNG, transparency preserved). |

## Install

Requires Python 3.9+.

```bash
# from the project directory
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

or just install the dependency and run it as a module:

```bash
pip install -r requirements.txt
python -m image_byte_resizer <image> <size>
```

## Usage

```
image-byte-resizer <image_path> <target_size> [options]
```

| Option | Description |
|--------|-------------|
| `--png-strategy {lossless,quantize}` | PNG handling. Default `lossless` (may miss target). |
| `--margin FLOAT` | Headroom below the target. Default `0.02` (2%). |
| `--min-quality INT` | Lower bound for JPEG/WebP search. Default `1`. |
| `--max-quality INT` | Upper bound for JPEG/WebP search. Default `95`. |
| `--output-dir PATH` | Where to write the copy. Default: next to the source. |
| `--dry-run` | Show what would happen; write nothing. |
| `-v, --verbose` | Show each binary-search trial. |

### Examples

```bash
# Get a photo under 2 MB
image-byte-resizer vacation.jpg 2MB

# Squeeze a PNG under 300 KB by reducing colors (stays a PNG)
image-byte-resizer screenshot.png 300KB --png-strategy quantize

# Tighter 5% headroom, show the search
image-byte-resizer photo.jpg 500KB --margin 0.05 -v
```

### Example output

```
$ image-byte-resizer vacation.jpg 2MB -v
Source : vacation.jpg  (4.80 MB, 4032x3024, JPEG)
Target : 2 MB (2,000,000 bytes, decimal) − 2% margin → 1,960,000 bytes
Trial 1: quality=48 → 1.79 MB  ✓ (under)
Trial 2: quality=71 → 2.43 MB  ✗
Trial 3: quality=59 → 2.05 MB  ✗
Trial 4: quality=53 → 1.91 MB  ✓
Result : JPEG quality=53, 1.91 MB, dimensions unchanged (4032x3024)
Saved     : vacation_Resized_2MB.jpg
```

## Behavior notes

- **Already small enough?** If the source already fits under the target, it's
  copied through unchanged (no needless re-encode).
- **Impossible target?** There's a floor (lowest quality / smallest palette).
  If even that exceeds the target, the tool writes the best-effort file and
  **warns** — it never resizes or converts format to force it. Exit code stays
  `0`; the warning goes to stderr.
- **Metadata** (EXIF) is stripped on re-encode — a small, free size win.
- **Animated** GIF/WebP are refused in v1 (resizing would drop frames).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT © Denali Cornwell
