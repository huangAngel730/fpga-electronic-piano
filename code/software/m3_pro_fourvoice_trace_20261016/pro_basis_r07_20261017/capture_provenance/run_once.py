"""Reuse only the new frozen R7 software runner; no B checker/test execution."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'public_equivalence_tb'))
from run_once import main

if __name__ == '__main__':
    raise SystemExit(main())
