#!/usr/bin/env python3
"""UniFi OS API helper — entry point. The implementation lives in udmlib/.

Run `python udm.py --help` for the command list.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from udmlib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
