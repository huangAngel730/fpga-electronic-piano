"""Seal only this task's explicit new files; never overwrite a prior seal."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
files = [HERE / name for name in (
    "D_INTEGRATION_GAPS.txt", "audit_snapshot.py", "STATIC_EVIDENCE.json",
    "audit.stderr.log", "EXECUTION_AND_HANDOFF.txt", "seal_delivery.py",
)]
files.append(ROOT / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/"
             "successor_R03/chat8_20261016/B_RECEIPT_ALIGNMENT.txt")
target = HERE / "BD_CHAT8_STATIC_ALIGNMENT_20261016.zip"
receipt = HERE / "SEAL_RECEIPT.json"
if target.exists() or receipt.exists():
    raise SystemExit("Refusing to overwrite existing delivery")
payloads = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}
manifest = {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in payloads.items()}
with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
    for name, raw in payloads.items():
        archive.writestr(name, raw)
    archive.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for name, raw in payloads.items():
        assert archive.read(name) == raw
data = target.read_bytes()
result = {"zip": target.name, "bytes": len(data),
          "sha256": hashlib.sha256(data).hexdigest(),
          "payload_count": len(payloads), "verified": True,
          "level": "L0 static alignment only", "files": manifest}
with receipt.open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "files"}))
