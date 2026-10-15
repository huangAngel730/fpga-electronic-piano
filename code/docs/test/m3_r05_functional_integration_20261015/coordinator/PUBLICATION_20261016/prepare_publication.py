"""Build an explicit publication allow-list without touching Git or old files."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
EXTRAS = [
    "code/docs/test/m3_r05_functional_integration_20261015/REWORK_20261016_R02/RESULT_AND_HANDOFF.md",
    "code/docs/test/m3_r05_functional_integration_20261015/REWORK_20261016_R02/FROZEN_TB_SCHEDULE.json",
    "code/docs/test/m3_r05_functional_integration_20261015/SEAL_REWORK_20261016_R02/SEAL_RECEIPT.json",
    "code/docs/test/m3_r05_functional_integration_20261015/SEAL_REWORK_20261016_R02/SELF_AUDIT.json",
    "code/docs/test/m3_r05_functional_integration_20261015/SEAL_REWORK_20261016_R02/WATCHDOG_ONLY.diff",
    "code/docs/test/m3_r05_functional_integration_20261015/R05_FUNCTIONAL_ATTEMPT_CONSUMED.json",
    "code/docs/test/m3_r05_functional_integration_20261015/R05_WATCHDOG_USER_REPAIR_ATTEMPT_CONSUMED.json",
    "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/CURRENT_RESULT.txt",
    "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/HANDOFF_TO_M2.txt",
    "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/README.txt",
    "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/delivery_night_r03/DELIVERY.json",
    "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/SEAL_20261016_R02/NIGHT_RUN_RECEIPT.json",
    "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/SEAL_20261016_R02/SEAL_RECEIPT.json",
]
DROOT = "code/docs/test/m3_dual_slider_138k_candidate_20261015/"
EXTRAS += [DROOT + name for name in (
    "run_candidate.py", "run_repair.py", "seal_delivery.py", "seal_repair.py",
    "README.md", "AUTHORITY_AND_FAILURE_HISTORY.md", "REPAIR_AUTHORIZATION_20261016.txt",
    "REPAIR_REPORT_20261016.txt", "HANDOFF_REPAIR_TO_M2.txt", "delivery_repair_20261016/DELIVERY.json",
)]


def ident(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    sources = json.loads((HERE / "SOURCE_PUBLICATION_LIST.json").read_text(encoding="utf-8"))
    own = [p.relative_to(REPO).as_posix() for p in HERE.iterdir() if p.is_file() and p.suffix in (".py", ".txt", ".json")]
    plan = sorted(set(sources + EXTRAS + own))
    for relative in plan:
        path = REPO / relative
        assert path.is_file(), relative
        assert path.stat().st_size < 50 * 1024 * 1024, relative
    verification = json.loads((HERE / "DELIVERY_VERIFICATION.json").read_text(encoding="utf-8"))
    extra_bindings = {}
    for relative in EXTRAS:
        if relative.startswith(DROOT) and not relative.endswith("DELIVERY.json"):
            blob = (REPO / relative).read_bytes()
            with zipfile.ZipFile(REPO / verification["packages"]["D"]["archive"]) as archive:
                matches = [n for n in archive.namelist() if n == relative or n.endswith("/" + relative)]
                assert any(archive.read(n) == blob for n in matches), relative
                extra_bindings[relative] = ident(blob)
    result = {"files": plan, "count": len(plan), "file_identities": {p: ident((REPO / p).read_bytes()) for p in plan},
              "D_extra_source_bindings": extra_bindings,
              "status": "READY_FOR_SINGLE_FILE_STAGING_NOT_PUBLISHED", "board_release_allowed": False}
    with (HERE / "PUBLICATION_PLAN.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"files": len(plan), "total_bytes": sum(x["bytes"] for x in result["file_identities"].values())}))


if __name__ == "__main__":
    main()
