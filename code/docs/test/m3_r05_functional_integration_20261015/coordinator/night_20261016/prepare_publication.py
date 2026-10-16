"""Select only this night's isolated sources and sealed deliverables."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]


def main():
    docs = ROOT / "code/docs/test"
    names = ("m3_r05_functional_integration_20261015",
             "m3_40mhz_pcm_i2s_latency_20261015",
             "m3_dual_slider_138k_candidate_20261015")
    paths = []
    for name in names:
        folder = docs / name / "night_20261016"
        assert (folder / "RESULT.md").is_file(), name
        assert (folder / "NIGHT_RUN_RECEIPT.json").is_file(), name
        paths.extend(p for p in folder.iterdir() if p.is_file() and p.name != "BOARD.diff")
    a_seal = docs / names[0] / "night_20261016/SEAL_PARTIAL_R03"
    paths.extend(a_seal / n for n in (
        "M3_NIGHT_A_STATIC_SOFTWARE_PARTIAL_R03.zip", "MANIFEST.json", "SEAL_RECEIPT.json"))
    c_seal = docs / names[1] / "night_20261016/SEAL_PARTIAL_R01"
    paths.extend(c_seal / n for n in (
        "M3_NIGHT_C_REAL_CONSUMER_SOFTWARE_PARTIAL_R01.zip", "MANIFEST.json", "SEAL_RECEIPT.json"))
    for relative in (
        "code/software/m3_r05_functional_integration_20261015/night_20261016",
        "code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016",
        "code/tb/board/m3_r05_functional_integration_20261015/night_20261016",
        "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016",
        "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/night_20261016",
    ):
        paths.extend(p for p in (ROOT / relative).iterdir() if p.suffix in (".py", ".sv", ".md") and p.is_file())
    paths.extend(p for p in HERE.iterdir() if p.is_file() and p.name not in (
        "PUBLICATION_PLAN.json", "PUBLICATION_RECEIPT.json", "FORWARD_PACKAGE_SHA.json"))
    files = sorted({p.relative_to(ROOT).as_posix() for p in paths})
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0"))
    assert not set(files) & tracked, "publication must add only isolated new files"
    identities = {}
    for relative in files:
        raw = (ROOT / relative).read_bytes()
        identities[relative] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    plan = {"baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
            "status": "PARTIAL_EVIDENCE_NOT_BOARD_RELEASE", "files": files,
            "file_identities": identities, "board_release_allowed": False}
    with (HERE / "PUBLICATION_PLAN.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"selected_files": len(files), "bytes": sum(r["bytes"] for r in identities.values())}))


if __name__ == "__main__":
    main()
