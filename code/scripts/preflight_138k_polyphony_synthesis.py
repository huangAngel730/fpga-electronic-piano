"""Read-only exact-project launch plan. This revision cannot execute synthesis."""
import argparse
import json
from pathlib import Path

import prepare_138k_polyphony_resource as prepared


def preflight(project: Path) -> dict:
    project = project.resolve()
    record = prepared.verify(project)
    return dict(status="PREFLIGHT_PASS_EXECUTION_LOCKED",
                project=record["output"], device=record["device"],
                configuration=record["configuration"],
                frozen_receipt_sha256=prepared.digest(
                    (project / "frozen_receipt.json").read_bytes()),
                command=[record["tool"]["identities"]["shell"]["path"],
                         "run_synthesis_only.tcl"],
                cwd=record["output"], timeout_seconds=900,
                stage="run syn ONLY", fresh_attempts=1,
                execution_authorized=False, execution_implemented=False,
                automatic_retry=False, automatic_N8_fallback=False,
                PnR=False, STA=False, device_operation=False)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--project", required=True, type=Path)
    cli.add_argument("--execute", action="store_true")
    args = cli.parse_args()
    if args.execute:
        print(json.dumps(dict(status="REJECT", reason="SYNTHESIS_NOT_AUTHORIZED")))
        return 1
    try:
        print(json.dumps(preflight(args.project), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(status="REJECT", reason=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
