#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


EVALUATION = Path(__file__).resolve().parent
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.analysis import analyze


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive summaries from an authoritative raw behavioral ledger")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    output = analyze(args.ledger.resolve())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

