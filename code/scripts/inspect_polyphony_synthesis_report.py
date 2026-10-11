"""Read a real Gowin hierarchical synthesis XML; no resource/STA admission."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

RESOURCE_FIELDS = ("Logic", "Register", "Lut", "Bsram", "Ssram", "DSP")


def count(value: str | None):
    if value is None:
        return None
    if not re.fullmatch(r"\d+(?:\(\d+\))?", value):
        raise ValueError("RESOURCE_COUNT_FORMAT:" + value)
    return int(value.split("(")[0])


def inspect(path: Path) -> dict:
    raw = path.read_bytes()
    tree = ET.fromstring(raw)
    rows = []
    for node in tree.iter():
        if not any(k in node.attrib or "T_" + k in node.attrib for k in RESOURCE_FIELDS):
            continue
        values = {k: count(node.attrib.get("T_" + k, node.attrib.get(k)))
                  for k in RESOURCE_FIELDS}
        rows.append(dict(name=node.attrib.get("name"), resources=values,
                         other_operator_attributes={k: v for k, v in node.attrib.items()
                                                    if "MULT" in k or "DSP" in k},
                         raw_attributes=dict(node.attrib)))
    if not rows:
        raise ValueError("NO_RESOURCE_ROWS")
    return dict(status="REPORT_PARSED_NOT_ADMITTED", path=str(path.resolve()),
                sha256=hashlib.sha256(raw).hexdigest(), hierarchy=rows,
                missing_fields="UNKNOWN, not zero; DSP primitive fields are not summed blindly",
                synthetic_or_other_project_provenance_not_verified=True,
                resource_admission=False, physical_STA="NOT_RUN",
                board_release_allowed=False)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("report", type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    try:
        if args.output.exists():
            raise ValueError("REFUSE_EXISTING_REPORT_OUTPUT")
        result = inspect(args.report)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps(dict(status=result["status"], rows=len(result["hierarchy"]))))
        return 0
    except (ValueError, OSError, ET.ParseError) as exc:
        print(json.dumps(dict(status="REJECT", reason=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
