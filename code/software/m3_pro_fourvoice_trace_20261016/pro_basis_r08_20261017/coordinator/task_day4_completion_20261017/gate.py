"""Mandatory nine-check publication gate, separately from the software batch."""
import hashlib
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
SOURCE = ROOT / 'code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/coordinator_20261017/run_gate.py'
DOC = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/task_day4_completion_20261017'


if __name__ == '__main__':
    raw = SOURCE.read_bytes()
    module = ModuleType('_d4_publication_gate')
    module.__file__ = str(SOURCE)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(SOURCE), 'exec'), module.__dict__)
    module.DOC = DOC
    raise SystemExit(module.main())
