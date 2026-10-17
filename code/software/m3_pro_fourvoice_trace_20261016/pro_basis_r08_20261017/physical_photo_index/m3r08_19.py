"""Photo/claim identity links only; no OCR or physical authentication claim."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
FIELDS = ("part_full", "device_version", "core_revision", "dock_revision", "bank_map", "measurement_board_binding")


def evaluate(request):
    c.need(set(request) == {"schema", "origin", "board_id", "claims", "evidence", "measurements"} and
           request["schema"] == "M3_R08_PHOTO_INDEX_REQUEST_V1", "PHOTO_INDEX_SCHEMA")
    c.need(request["origin"] in ("SYNTHETIC", "REAL_CANDIDATE"), "PHOTO_ORIGIN")
    c.need(type(request["board_id"]) is str and request["board_id"], "BOARD_ID_REQUIRED")
    sources, links, missing = {}, [], []
    for entry in request["evidence"]:
        c.need(entry["id"] not in sources, "DUPLICATE_EVIDENCE_ID")
        path, ident = c.checked_file(entry["file"])
        c.need(entry["kind"] in ("ORIGINAL_PHOTO", "REFERENCE_DOCUMENT", "SYNTHETIC"), "PHOTO_SOURCE_KIND")
        if entry["kind"] != "REFERENCE_DOCUMENT":
            c.need(entry.get("board_id") == request["board_id"], "BOARD_ID_MISMATCH")
        if entry["kind"] == "ORIGINAL_PHOTO":
            raw = path.read_bytes()
            c.need(raw.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")) or
                   (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"), "ORIGINAL_PHOTO_FORMAT")
        sources[entry["id"]] = {**entry, "verified_file": ident}
    for name in FIELDS:
        claim = request["claims"].get(name)
        if claim is None or claim.get("value") in (None, "", []):
            missing.append(name)
            continue
        c.need(claim.get("evidence_id") in sources, "CLAIM_WITHOUT_EVIDENCE")
        c.need(type(claim.get("page")) is int and claim["page"] >= 1 and
               type(claim.get("region")) is str and bool(claim["region"].strip()), "PAGE_REGION_REQUIRED")
        entry = sources[claim["evidence_id"]]
        links.append({"field": name, "value_as_claimed": claim["value"], "page": claim["page"],
                      "region": claim["region"], "evidence_id": entry["id"], "file": entry["verified_file"],
                      "source_kind": entry["kind"], "physical_truth_verified": False})
        if request["origin"] == "REAL_CANDIDATE" and entry["kind"] != "ORIGINAL_PHOTO":
            missing.append("REAL_PHOTO_FOR:" + name)
    for measurement in request["measurements"]:
        c.need(measurement["board_id"] == request["board_id"] and measurement["evidence_id"] in sources,
               "MEASUREMENT_BOARD_MISMATCH")
    if request["origin"] == "REAL_CANDIDATE":
        missing.append("HUMAN_PART_VERSION_BANK_AND_SESSION_CONFIRMATION")
    report = {"origin": request["origin"], "board_id": request["board_id"], "source_files": list(sources.values()),
              "claim_links": links, "missing": missing, "actual_image_semantics_verified": False,
              "physical_identity_signed": False, "reference_or_synthetic_is_real_photo": False}
    return c.result("M3_R08_PHYSICAL_PHOTO_INDEX_V1", "PENDING_UNKNOWN" if missing else "ACCEPT",
                    report=report, artifacts={"physical_photo_index.json": report})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
