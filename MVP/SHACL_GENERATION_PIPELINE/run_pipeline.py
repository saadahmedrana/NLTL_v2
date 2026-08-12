#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from nltl_pipeline.cli import main  # noqa: E402


if __name__ == "__main__":
    main()

