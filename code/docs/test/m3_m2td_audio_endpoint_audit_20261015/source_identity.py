"""Reconstruct staged source bytes from an original portable ZIP's own receipt.

Derived sources are labeled and are NOT original synthesis/routed netlists.
"""
import hashlib
import json
from pathlib import Path
import zipfile
import argparse

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    target = parser.parse_args().output.resolve()
    if target.parent != ROOT:
        raise ValueError("output must be a fresh immediate child of exclusive directory")
    if target.exists():
        raise ValueError("refuse existing output")
    portable = REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip"
    expected_zip = "1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf"
    if sha(portable.read_bytes()) != expected_zip:
        raise ValueError("portable identity mismatch")
    physical_receipt = json.loads((ROOT / "observed_r03/originals/PREPARATION_RECEIPT.json").read_bytes())
    output = []
    with zipfile.ZipFile(portable) as z:
        receipt_blob = z.read("PREPARATION_RECEIPT.json")
        receipt = json.loads(receipt_blob)
        for name, expected in (
            ("m1td_pitch_mod_fcw_pipeline.sv", "5997ae2eddb483f95dbb10cdac6cfdac3d61a857046e95e136099e11cf0ecabb"),
            ("m1td_pitch_mod_snapshot_pipeline.sv", "c35bc435a98d541e176ea59373bffd0ded9c346c1954118c6fde21c65a4ee601"),
        ):
            member = "inputs/sources/" + name
            raw = z.read(member)
            original = raw
            adaptations = receipt["path_adaptations"][member]
            # Keep the raw receipt and transformations rather than imply a recovered original.
            operations = adaptations if isinstance(adaptations, list) else adaptations["replacements"]
            for op in operations:
                old, new = op["old"].encode("utf-8"), op["new"].encode("utf-8")
                if raw.count(new) != 1:
                    raise ValueError("unexpected portable path multiplicity")
                raw = raw.replace(new, old)
            if sha(raw) != expected:
                raise ValueError("derived physical identity mismatch")
            matching = {k: v for k, v in physical_receipt["input_files"].items()
                        if k.replace("\\", "/").endswith("/" + name) and v["sha256"] == expected}
            if len(matching) != 1:
                raise ValueError("physical receipt missing exact derived input")
            output.append({"name": name, "portable_member": member, "portable_sha256": sha(original),
                           "portable_bytes": len(original), "derived_sha256": sha(raw), "derived_bytes": len(raw),
                           "classification": "DERIVED_RECONSTRUCTION_NOT_ORIGINAL", "reverse_adaptations": operations,
                           "physical_input_receipt_entry": matching, "blob": raw, "portable_blob": original})
        target.mkdir()
        (target / "portable_PREPARATION_RECEIPT.json").write_bytes(receipt_blob)
    for item in output:
        (target / item["name"]).write_bytes(item.pop("blob"))
        (target / (item["name"] + ".portable_original")).write_bytes(item.pop("portable_blob"))
    identity = {"classification": "DERIVED_RECONSTRUCTION_NOT_ORIGINAL", "netlist_provided": False,
                "portable_zip_sha256": expected_zip, "portable_receipt_sha256": sha(receipt_blob),
                "derived_files": output, "board_release_allowed": False}
    (target / "DERIVATION.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sha(portable.read_bytes()) != expected_zip:
        raise ValueError("portable input changed")
    print(json.dumps({"status": "DERIVED_SOURCE_SHA_MATCH", "files": len(output), "netlist_provided": False}))


if __name__ == "__main__":
    main()
