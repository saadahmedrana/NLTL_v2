#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


EVALUATION_ROOT = Path(__file__).resolve().parent
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from experiment_runner.rejected_attempt4_diagnostic import main


if __name__ == "__main__":
    raise SystemExit(main())
