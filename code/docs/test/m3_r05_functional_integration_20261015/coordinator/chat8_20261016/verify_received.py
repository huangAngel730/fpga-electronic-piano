"""Verify new chat8 deliverables without executing child tests or HDL tools."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
PACKAGES = {
    "dialogue2_chat9": (
        "code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016/SEAL_CHAT9R02/M3_CHAT9_R05_PCM_REPLAY_20261016.zip",
        "832947a0a0bacb3d604a01e0bb726cf943d007f506e5b51c67d941ee55e31b12",
    ),
    "dialogue3": (
        "code/docs/test/t052_publication_acceptance_20261012/LONG_WINDOW_PREPARATION_20261015/chat8_readiness_20261016/T052_CHAT8_READINESS.zip",
        "281a4fb92fd25c75a16bf6017b1f66ede198a3c23592235ca4f77da809580b7c",
    ),
    "dialogue2": (
        "code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016/SEAL_R01/M3_CHAT8_A_C_MATH_SCOPE_DELTA_20261016.zip",
        "37dff3bf0507d28ad940c740e79f6f89cbedd5248d9e23e557adb54844a4570e",
    ),
    "dialogue4": (
        "code/docs/test/m3_dual_slider_138k_candidate_20261015/chat8_20261016/BD_CHAT8_STATIC_ALIGNMENT_20261016.zip",
        "a7d683d2ec41a5e3b55291ce6941eb821e32ded723d78f59c76301035109886b",
    ),
}


def main():
    report = {}
    for label, (relative, expected) in PACKAGES.items():
        path = REPO / relative
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == expected, label
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None, label
            names = archive.namelist()
            assert len(names) == len(set(names)), label
            manifest = json.loads(archive.read("MANIFEST.json"))
            files = manifest.get("members", manifest.get("files", manifest))
            if isinstance(files, list):
                entries = files
                files = {item["path"]: item for item in entries}
                assert len(files) == len(entries), (label, "duplicate manifest paths")
            assert set(names) == set(files) | {"MANIFEST.json"}, label
            for name, item in files.items():
                blob = archive.read(name)
                assert len(blob) == item["bytes"], name
                assert hashlib.sha256(blob).hexdigest() == item["sha256"], name
            report[label] = {"status": "PASS", "bytes": len(raw), "sha256": digest, "payloads_verified": len(files)}
    print(json.dumps(report))
    with (HERE / "VERIFIED_NEW_PACKAGES.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
