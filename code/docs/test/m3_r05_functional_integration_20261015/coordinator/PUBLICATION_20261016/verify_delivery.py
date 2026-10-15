"""Read-only archive/source verification; no simulator or EDA execution."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
PACKAGES = {
    "A": ("code/docs/test/m3_r05_functional_integration_20261015/SEAL_REWORK_20261016_R02/M3_A_R05_WATCHDOG_REPAIR_20261016.zip", "92b8c3e36196c7c5996b724e04054909d8eeb5cc6a2e37f0eec3338b854faaf0"),
    "B": ("code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/delivery_night_r03/B_DIRECTED_STA_CANDIDATE_20261016.zip", "59f40000f25bccc492199e4a0f6e843e4a7ccf68ddaeab5823c756b888d44ce3"),
    "C": ("code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/SEAL_20261016_R02/M3_C_PCM_SERIAL_MODULE_HISTORY_20261016.zip", "da480517d5729f6cd15227549a43c59a0b56c883fad9242d53f999b613196aca"),
    "D": ("code/docs/test/m3_dual_slider_138k_candidate_20261015/delivery_repair_20261016/DUAL_SLIDER_REPAIR_PASS_20261016.zip", "ac3df441c8bda0d9b839bff903b520b5705df4ebbba9c666a749f0fb8a68a56d"),
}
SOURCE_ROOTS = {
    "A": ["code/software/m3_r05_functional_integration_20261015", "code/tb/board/m3_r05_functional_integration_20261015"],
    "B": ["code/software/m3_m2td_audio_endpoint_audit_20261015/successor_R03"],
    "C": ["code/software/m3_40mhz_pcm_i2s_latency_20261015", "code/tb/audio_out/m3_40mhz_pcm_i2s_latency_20261015"],
    "D": ["code/rtl/input/m3_dual_slider_138k_candidate_20261015", "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015"],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    results = {}
    publication = []
    for label, (relative, expected) in PACKAGES.items():
        path = REPO / relative
        raw = path.read_bytes()
        assert sha(raw) == expected, (label, "outer SHA")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)), (label, "duplicate members")
            assert archive.testzip() is None, (label, "CRC")
            for name in names:
                p = PurePosixPath(name)
                assert not p.is_absolute() and ".." not in p.parts and "\\" not in name, name
                assert p.suffix.lower() not in {".exe", ".dll", ".fs", ".binx", ".pr"}, (label, "tool/bitstream/database", name)
            manifest = json.loads(archive.read("MANIFEST.json"))
            files = manifest.get("files", manifest)
            for name, ident in files.items():
                blob = archive.read(name)
                assert len(blob) == ident["bytes"] and sha(blob) == ident["sha256"], (label, name)
            assert set(files) == set(names) - {"MANIFEST.json"}, (label, "manifest coverage")
            sources = {}
            for root in SOURCE_ROOTS[label]:
                for source in sorted((REPO / root).rglob("*")):
                    if not source.is_file() or "__pycache__" in source.parts:
                        continue
                    rel = source.relative_to(REPO).as_posix()
                    blob = source.read_bytes()
                    candidates = [n for n in names if n == rel or n.endswith("/" + rel)]
                    exact = [n for n in candidates if archive.read(n) == blob]
                    assert exact, (label, "current source not sealed", rel, candidates)
                    if source.suffix == ".py":
                        ast.parse(blob, filename=rel)
                    sources[rel] = {"bytes": len(blob), "sha256": sha(blob), "sealed_members": exact}
                    publication.append(rel)
            results[label] = {"archive": relative, "bytes": len(raw), "sha256": sha(raw),
                              "members": len(names), "verified_manifest_entries": len(files),
                              "current_sources": sources, "status": "PASS"}
        publication.append(relative)
    report = {"status": "PASS", "scope": "ARCHIVE_CRC_MANIFEST_CURRENT_SOURCE_AST_ONLY",
              "packages": results, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
              "new_simulator_or_EDA_calls": 0, "board_release_allowed": False}
    with (HERE / "DELIVERY_VERIFICATION.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    with (HERE / "SOURCE_PUBLICATION_LIST.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(sorted(publication), stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: {"members": v["members"], "sources": len(v["current_sources"]), "status": v["status"]} for k, v in results.items()}))


if __name__ == "__main__":
    main()
