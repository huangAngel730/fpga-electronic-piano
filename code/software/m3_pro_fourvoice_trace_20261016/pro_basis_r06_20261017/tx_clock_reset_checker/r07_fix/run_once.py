"""Read-only reuse of the bounded software runner, with this package's spec."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT / 'code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_equivalence_tb'))
from run_once import main

if __name__ == '__main__':
    raise SystemExit(main())
