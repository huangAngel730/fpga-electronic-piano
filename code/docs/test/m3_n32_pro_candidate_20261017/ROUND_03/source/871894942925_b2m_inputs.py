"""Restore only verified original B2K normal logs; do not execute old RTL."""
import base64
import hashlib
import io
import json
from pathlib import PurePosixPath
import zipfile

from inventory import ROOT

PACKAGE = ROOT / "code/docs/hardware/polyphony_scaling_v1/B2K_20261011"
ZIP_SHA = "ce06a926ce1bc8d3618f361a4aaafec0fd6b010235c04e8a8d8e060f45a21bde"
CARRIER_SHA = "119ddda5956a37f376b5644bf254c4529ae425e0974c9a6b6d11ebc42f46e836"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def originals():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    carrier = (PACKAGE / "evidence.zip.b64").read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if (sha(raw) != ZIP_SHA or sha(carrier) != CARRIER_SHA
            or manifest["zip_sha256"] != ZIP_SHA or manifest["carrier_sha256"] != CARRIER_SHA):
        raise ValueError("B2M_ORIGINAL_SEAL_IDENTITY")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if archive.testzip() or len(set(names)) != len(names) or set(names) != set(manifest["members"]):
            raise ValueError("B2M_ORIGINAL_MEMBERS")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                raise ValueError("B2M_ORIGINAL_PATH")
            data, item = archive.read(name), manifest["members"][name]
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("B2M_ORIGINAL_MEMBER_SHA")
        receipt_raw = archive.read(manifest["qualified_receipt"])
        receipt = json.loads(receipt_raw)
        if (receipt["exit_code"] != 0 or type(receipt["exit_code"]) is not int
                or receipt["status"] != "B2K_INFLIGHT_CANCEL_PASS_T061_PARTIAL"):
            raise ValueError("B2M_ORIGINAL_RECEIPT")
        sources = {}
        # Exact executed inputs, not merely names that look like the same RTL.
        for item in receipt["candidate_sources_before"] + receipt["frozen_inputs_before"]:
            name = item["path"]
            data = archive.read(name)
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("B2M_ORIGINAL_SOURCE_BINDING")
            if (ROOT / name).read_bytes() != data:
                raise ValueError("B2M_CURRENT_SOURCE_DRIFT:" + name)
            sources[name] = data
        captures = {}
        for n, response in ((4, 1), (32, 1), (32, 64)):
            label = f"B2K_N{n}_R{response}_simulate"
            step = next(s for s in receipt["steps"] if s["label"] == label)
            if step["exit_code"] != 0 or step["timed_out"]:
                raise ValueError("B2M_ORIGINAL_SIMULATION_NOT_QUALIFIED")
            item = step["stdout"]
            data = archive.read(item["path"])
            if sha(data) != item["sha256"] or len(data) != item["bytes"]:
                raise ValueError("B2M_ORIGINAL_CAPTURE_BINDING")
            captures[f"N{n}_R{response}"] = dict(raw=data, original_member=item["path"],
                                                original_identity=item)
    return captures, sources, dict(zip_sha256=ZIP_SHA, carrier_sha256=CARRIER_SHA,
        receipt_member=manifest["qualified_receipt"], receipt_sha256=sha(receipt_raw),
        original_members_verified=len(names), new_RTL_execution=False)
