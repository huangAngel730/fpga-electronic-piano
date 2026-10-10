"""Exactly one new-combo build using qualified new-combo proofs only."""
from pathlib import Path
import datetime
import json
import sys

import prepare_138k_night_cache_combo as prepared
import check_138k_night_cache_combo as gate
import run_138k_score_bram_build_once as original


def main():
    # Reuse the same bounded process/overwrite safeguards. Binding is process-
    # local; no old runner source or previous frozen receipt is edited.
    started = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    wrapper_sha = original.sha(Path(__file__))
    original.prepared = prepared
    original.gate = gate
    original.RUNS = prepared.BUILD_ROOT / "runs"
    code = original.main()
    if "--preflight-only" not in sys.argv and "--output" in sys.argv:
        run = Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
        path = run / "build_receipt.json"
        if path.exists():
            result = json.loads(path.read_bytes())
            result["tools_and_sources_sha256"].update({str(Path(__file__).resolve()): original.sha(Path(__file__))})
            result["base_build_runner_sha256"] = original.sha(Path(original.__file__))
            result["new_combo_version"] = prepared.VERSION
            result["combo_execution_started_Asia_Shanghai"] = started
            result["combo_execution_finished_Asia_Shanghai"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
            result["wrapper_sha256_before"] = wrapper_sha
            if original.sha(Path(__file__)) != wrapper_sha:
                result["execution_source_unchanged"] = False
                code = 1
            original.dump(path, result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
