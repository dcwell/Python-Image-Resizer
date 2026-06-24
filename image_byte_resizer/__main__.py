"""Enable ``python -m image_byte_resizer``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
