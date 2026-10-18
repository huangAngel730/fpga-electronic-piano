"""Publication gate reuse; this stage adds no Pro execution permission."""
import hashlib
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[6]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/PUBLICATION_GATE"
LEGACY = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/coordinator_20261017/run_gate.py"


def main():
    source = LEGACY.read_bytes()
    if hashlib.sha256(source).hexdigest() != "3fcd3a5f036e4aa9bd4f3d2ccd15e6bcfd327154d1522552528894c584a61543":
        raise RuntimeError("EXISTING_GATE_SOURCE_CHANGED")
    old = b"C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    new = b"C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
    if source.count(old) != 1:
        raise RuntimeError("GATE_HOST_DERIVATION_NOT_UNIQUE")
    derived = source.replace(old, new)
    DOC.mkdir(exist_ok=True, parents=True)
    (DOC / "DERIVED_GATE_SOURCE.py").write_bytes(derived)
    module = types.ModuleType("_n10_existing_gate")
    module.__file__ = str(LEGACY)
    exec(compile(derived, str(LEGACY), "exec"), module.__dict__)
    module.DOC = DOC
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
