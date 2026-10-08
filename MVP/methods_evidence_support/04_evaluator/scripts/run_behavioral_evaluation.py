#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


EVALUATION = Path(__file__).resolve().parent
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

