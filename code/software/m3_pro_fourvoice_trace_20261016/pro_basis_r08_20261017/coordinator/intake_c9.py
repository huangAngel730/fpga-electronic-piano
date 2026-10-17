"""Read-only Git/ZIP identity checks for the newly published C9 inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"
OLD = "cf370156fb882df3e8fe8bf04b45d3e12ad4c08b"
NEW = "16ac226552f6fb65347b229b8fad42146ed45644"


def ident(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def save(name, value):
    with (DOC / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    assert git("rev-parse", "HEAD").decode().strip() == NEW
    names = [n for n in git("diff", "--name-only", "-z", OLD, NEW).decode().split("\0") if n]
    assert len(names) == 76 and not any("m3_pro_fourvoice_trace_20261016" in n for n in names)
    baseline = json.loads((DOC / "PUBLICATION_BASELINE.json").read_text(encoding="utf-8"))
    transitions = {}
    for name, expected in baseline.items():
        if name not in names:
            assert ident((ROOT / name).read_bytes()) == expected, name
    for name in names:
        raw = git("show", NEW + ":" + name)
        assert (ROOT / name).read_bytes() == raw, name
        transitions[name] = {"before": baseline.get(name), "after": ident(raw)}
        baseline[name] = ident(raw)
    save("PUBLICATION_BASELINE_C9.json", baseline)
    save("M2_C9_PUBLICATION_ADVANCE.json", {"from": OLD, "to": NEW, "changed": transitions, "M3_changed": 0, "new_groups": 0})
    folder = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/c9_m1_semantics_20261017"
    decision_path = folder / "SOURCE_DECISION_R06C9.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    archive_path = ROOT / decision["package"]["path"]
    archive_identity = ident(archive_path.read_bytes())
    assert archive_identity == {k: decision["package"][k] for k in ("bytes", "sha256")}
    verified = {}
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == len(set(archive.namelist()))
        manifest = json.loads(archive.read("MANIFEST.json"))
        assert manifest["payloads"] == decision["payloads"]
        assert set(archive.namelist()) == set(decision["payloads"]) | {"MANIFEST.json"}
        for name, expected in decision["payloads"].items():
            actual = ident(archive.read(name))
            assert actual == expected, name
            verified[name] = actual
    m1_path = ROOT / "code/docs/test/m2_m1_r07_intake_20261017/M1_R07_ORIGINAL.zip"
    m1_identity = ident(m1_path.read_bytes())
    assert m1_identity["sha256"] == decision["M1_packet_sha256"]
    m1_members = {}
    with zipfile.ZipFile(m1_path) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 61
        assert len(set(archive.namelist())) == 61
        manifest = json.loads(archive.read("MEMBER_MANIFEST.json"))
        assert len(manifest["files"]) == 60
        for item in manifest["files"]:
            actual = ident(archive.read(item["path"]))
            assert actual == {k: item[k] for k in ("bytes", "sha256")}, item["path"]
            m1_members[item["path"]] = actual
    save("C9_INTAKE_RECEIPT.json", {"status": "BYTE_SHA_CRC_VERIFIED_L0_ONLY", "baseline": NEW, "C9_archive": {"path": archive_path.relative_to(ROOT).as_posix(), **archive_identity}, "C9_decision": {"path": decision_path.relative_to(ROOT).as_posix(), **ident(decision_path.read_bytes())}, "C9_payloads": verified, "M2_declared_counts_not_compilation": {k: decision[k] for k in ("source_units", "ROMs", "headers", "literal_modules")}, "M1_archive": {"path": m1_path.relative_to(ROOT).as_posix(), **m1_identity}, "M1_payloads": m1_members, "functional_runs": 0, "HDL_EDA_device": 0, "R08_consumption_restored": False, "M1_note_on_erratum": "PENDING_OWNER_CONFIRMATION_NO_FIXED_DELAY_ASSUMPTION", "independent_apply_event_seq_audio_stable_REAL": "PENDING", "board_release_allowed": False})
    print(json.dumps({"remote_files_verified": len(names), "C9_payloads": len(verified), "M1_payloads": len(m1_members), "functional_runs": 0}))


if __name__ == "__main__":
    main()
