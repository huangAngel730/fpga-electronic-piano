"""Mechanical source-authority graph checker; it cannot certify REAL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROLES = ("source", "capture", "clock", "reset", "calendar", "frame",
         "oracle", "receipt")
DEPENDENCIES = {
    "source": [],
    "capture": ["source"],
    "clock": ["source", "capture"],
    "reset": ["clock", "capture"],
    "calendar": ["clock", "reset"],
    "frame": ["calendar", "capture"],
    "oracle": ["source", "capture"],
    "receipt": ["capture", "frame", "oracle"],
}


class AuthorityReject(ValueError):
    pass


def check_graph(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"requested_mode", "capture_id", "nodes"}:
        raise AuthorityReject("GRAPH_SHAPE")
    nodes = value["nodes"]
    if not isinstance(nodes, dict) or set(nodes) != set(ROLES):
        raise AuthorityReject("NODE_SET")
    source_ids = set()
    for role, node in nodes.items():
        if set(node) != {"sha256", "source_id", "capture_id", "origin",
                         "trusted_receipt", "depends_on"}:
            raise AuthorityReject(f"NODE_SHAPE_{role}")
        if node["capture_id"] != value["capture_id"]:
            raise AuthorityReject(f"CAPTURE_ID_MISMATCH_{role}")
        if not isinstance(node["source_id"], str) or not node["source_id"]:
            raise AuthorityReject(f"SOURCE_ID_{role}")
        source_ids.add(node["source_id"])
        if node["depends_on"] != DEPENDENCIES[role]:
            raise AuthorityReject(f"DEPENDENCY_REFERENCE_{role}")
        digest = node["sha256"]
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise AuthorityReject(f"SHA256_{role}")
    if len(source_ids) != 1:
        raise AuthorityReject("SOURCE_ID_MISMATCH")
    origins = {node["origin"] for node in nodes.values()}
    if value["requested_mode"] == "SYNTHETIC":
        if origins != {"SYNTHETIC"}:
            raise AuthorityReject("SYNTHETIC_MIXED_ORIGIN")
        status = "SYNTHETIC_ONLY"
    elif value["requested_mode"] == "REAL":
        if origins != {"REAL_CANDIDATE"}:
            raise AuthorityReject("REAL_MIXED_SYNTHETIC_DEPENDENCY")
        if not all(node["trusted_receipt"] is True for node in nodes.values()):
            status = "PENDING_TRUSTED_REAL_RECEIPTS"
        else:
            status = "PENDING_M2_REAL_ADMISSION"
    else:
        raise AuthorityReject("MODE")
    return {"schema": "M3_R08_REAL_AUTHORITY_GRAPH_V1", "status": status,
            "mechanical_only": True, "real_certified": False,
            "source_id": next(iter(source_ids)),
            "edges": [[dependency, role] for role in ROLES
                      for dependency in DEPENDENCIES[role]]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check_graph(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
