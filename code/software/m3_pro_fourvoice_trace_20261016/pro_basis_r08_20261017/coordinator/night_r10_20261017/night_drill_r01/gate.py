"""Reuse the publication gate with this host's existing PowerShell 7."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[7]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01/PUBLICATION_GATE"
LEGACY = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/coordinator_20261017/run_gate.py"


def main() -> int:
    source = LEGACY.read_bytes()
    if hashlib.sha256(source).hexdigest() != "3fcd3a5f036e4aa9bd4f3d2ccd15e6bcfd327154d1522552528894c584a61543":
        raise RuntimeError("PUBLICATION_GATE_SOURCE_CHANGED")
    old = b'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    new = b'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe'
    if source.count(old) != 1:
        raise RuntimeError("HOST_SHELL_DERIVATION_NOT_UNIQUE")
    derived = source.replace(old, new)
    DOC.mkdir(exist_ok=True, parents=True)
    (DOC / "DERIVED_GATE_SOURCE.py").write_bytes(derived)
    (DOC / "DERIVATION.json").write_text(json.dumps({"schema": "M3_DRILL_HOST_GATE_DERIVATION_R01",
        "source": str(LEGACY.relative_to(ROOT)), "sha256": hashlib.sha256(source).hexdigest(),
        "derived_sha256": hashlib.sha256(derived).hexdigest(),
        "only_change": "existing PowerShell7 executable; same wrapper/check_repo and checks",
        "execution_policy_changed": False}, indent=2) + "\n", encoding="utf-8")
    module = types.ModuleType("_m3_drill_existing_publication_gate")
    module.__file__ = str(LEGACY)
    exec(compile(derived, str(LEGACY), "exec"), module.__dict__)
    module.DOC = DOC
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
