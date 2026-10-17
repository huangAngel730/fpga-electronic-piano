"""Mandatory repository gate only, separate from the five R08 software groups."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"
SOURCE = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/coordinator_20261017/run_gate.py"


if __name__ == "__main__":
    spec = importlib.util.spec_from_file_location("r08_repository_gate", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DOC = DOC
    raise SystemExit(module.main())
