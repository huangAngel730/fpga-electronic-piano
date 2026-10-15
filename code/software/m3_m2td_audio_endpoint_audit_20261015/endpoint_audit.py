"""Fail-closed, read-only audit of exact endpoint pairs in Gowin HTML reports.

This is not an STA runner. It parses raw report tables, not user-authored
observations. Exit zero means only that the specified raw report shows all
specified setup/hold pairs under the independently supplied target identity.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import zipfile


SCHEMA = "m3_audio_endpoint_targets_v1"
FROZEN_ZIP_SHA = (
    "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff"
)
FROZEN_REPORT_SHA = (
    "524cea6ebb93eca719c5aa86cd6413129299ac2c9da78467ac7709cdf4e8ec62"
)
PATH_COLUMNS = (
    "Path Number", "Path Slack", "From Node", "To Node", "From Clock",
    "To Clock", "Relation", "Clock Skew", "Data Delay",
)
IDENTITY_FIELDS = (
    "Report Title", "Design File", "Physical Constraints File",
    "Timing Constraint File", "Tool Version", "Part Number", "Device",
    "Device Version", "Created Time",
)
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
INACTIVE = re.compile(
    r"\b(?:inactive|disabled|unconstrained|unavailable)\b|no timing paths",
    re.IGNORECASE,
)
BAD_DIAGNOSTIC = re.compile(
    r"\b(?:error|fatal|failure)\s*:|\berrors\s*:\s*[1-9][0-9]*\b",
    re.IGNORECASE,
)


class AuditError(ValueError):
    """A deterministic refusal with a machine-readable diagnostic."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


def reject(code: str, detail: str) -> None:
    raise AuditError(code, detail)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(text: str) -> str:
    return " ".join(text.split())


def literal_glob(name: str) -> str:
    """Literal bus/lane indexes in Gowin glob collections, NOT Tcl execution."""
    if any(character in name for character in ("\\", "{", "}", "*", "?")):
        reject("TARGET_SCHEMA", "unsupported special object character")
    return name.replace("[", "\\[").replace("]", "\\]")


def directed_prefixes(kind: str, target: dict) -> list[str]:
    """Derive exact collection types without mistaking RAM pins for FF cells.

    Launch is an FF /Q node: get_regs names its parent register. Capture is
    a named pin: get_pins retains the WHOLE endpoint. Only a /D endpoint also
    admits get_regs naming its parent FF, never RAM /AD[n] or /WAD[n].
    Every literal [] is escaped in collection patterns, unlike raw node names.
    """
    if not target["from_node"].endswith("/Q"):
        reject("TARGET_SCHEMA", "directed launch supports only FF /Q")
    from_reg = literal_glob(target["from_node"][:-2])
    to_node = literal_glob(target["to_node"])
    to_queries = [f"get_pins {{{to_node}}}"]
    if target["to_node"].endswith("/D"):
        to_queries.append(f"get_regs {{{literal_glob(target['to_node'][:-2])}}}")
    return [
        f"Report Command:report_timing -{kind} "
        f"-from [get_regs {{{from_reg}}}] -to [{query}]"
        for query in to_queries
    ]


def strict_json(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                reject("DUPLICATE_JSON_KEY", key)
            result[key] = value
        return result

    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        reject("TARGET_FORMAT", str(exc))
    if not isinstance(result, dict):
        reject("TARGET_FORMAT", "target document must be an object")
    return result


def decimal(text: str, where: str) -> Decimal:
    if not isinstance(text, str) or not NUMBER.fullmatch(text):
        reject("INVALID_NUMBER", f"{where}: {text!r}")
    try:
        value = Decimal(text)
    except InvalidOperation:
        reject("INVALID_NUMBER", where)
    if not value.is_finite():
        reject("INVALID_NUMBER", where)
    return value


@dataclass
class Row:
    cells: list[str]
    start: int
    end: int


@dataclass
class Table:
    rows: list[Row]
    start: int
    end: int
    headings: dict[int, str]
    anchors: dict[int, str]


class GowinHTML(HTMLParser):
    """Capture tables and exact character ranges, tolerate Gowin's unclosed td.

    V1.9.11.03 omits several </td> tags in its Clock Summary. New cells
    implicitly close previous ones. Nested tables and structurally incomplete
    rows/tables are refused rather than interpreted as complete evidence.
    """

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer("\n", text))
        self.tables: list[Table] = []
        self.headings: dict[int, str] = {}
        self.anchors: dict[int, str] = {}
        self.heading_level = None
        self.heading_text: list[str] = []
        self.heading_anchor = ""
        self.table: Table | None = None
        self.row: Row | None = None
        self.cell: list[str] | None = None
        self.hidden_depth = 0
        self.visible_text: list[str] = []

    def char_offset(self) -> int:
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def finish_cell(self) -> None:
        if self.cell is not None:
            if self.row is None:
                reject("HTML_STRUCTURE", "cell outside row")
            self.row.cells.append(normalized("".join(self.cell)))
            self.cell = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag in ("script", "style"):
            self.hidden_depth += 1
            return
        if self.hidden_depth:
            return
        if re.fullmatch(r"h[1-4]", tag):
            if self.heading_level is not None:
                reject("HTML_STRUCTURE", "nested headings")
            self.heading_level = int(tag[1])
            self.heading_text = []
            self.heading_anchor = ""
        if tag == "a" and self.heading_level:
            self.heading_anchor = attributes.get("name", "")
        if tag == "table":
            if self.table is not None:
                reject("HTML_STRUCTURE", "nested tables")
            self.table = Table(
                [], self.char_offset(), 0, dict(self.headings), dict(self.anchors),
            )
        elif tag == "tr" and self.table is not None:
            if self.row is not None:
                reject("HTML_STRUCTURE", "unclosed row")
            self.row = Row([], self.char_offset(), 0)
        elif tag in ("td", "th") and self.table is not None:
            self.finish_cell()
            if self.row is None:
                reject("HTML_STRUCTURE", "cell outside row")
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.hidden_depth = max(0, self.hidden_depth - 1)
            return
        if self.hidden_depth:
            return
        if self.heading_level and tag == f"h{self.heading_level}":
            level = self.heading_level
            for old in tuple(self.headings):
                if old >= level:
                    self.headings.pop(old, None)
                    self.anchors.pop(old, None)
            self.headings[level] = normalized("".join(self.heading_text))
            self.anchors[level] = self.heading_anchor
            self.heading_level = None
        if tag in ("td", "th"):
            self.finish_cell()
        elif tag == "tr" and self.table is not None:
            self.finish_cell()
            if self.row is None:
                reject("HTML_STRUCTURE", "closing absent row")
            self.row.end = self.char_offset() + len("</tr>")
            self.table.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.row is not None:
                reject("HTML_STRUCTURE", "table ends inside row")
            self.table.end = self.char_offset() + len("</table>")
            self.tables.append(self.table)
            self.table = None

    def handle_data(self, data: str) -> None:
        if self.hidden_depth:
            return
        self.visible_text.append(data)
        if self.heading_level:
            self.heading_text.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def finish(self) -> None:
        if self.table is not None or self.row is not None or self.heading_level:
            reject("HTML_STRUCTURE", "incomplete HTML report")


def span(data: bytes, text: str, start: int, end: int) -> dict:
    # UTF-8 offsets refer to ORIGINAL bytes, not newline-normalized text.
    lo = len(text[:start].encode("utf-8"))
    hi = len(text[:end].encode("utf-8"))
    return {
        "byte_start": lo, "byte_end_exclusive": hi,
        "line_start": text.count("\n", 0, start) + 1,
        "line_end": text.count("\n", 0, end) + 1,
        "fragment_sha256": sha256(data[lo:hi]),
    }


def parse_report(data: bytes) -> dict:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        reject("REPORT_ENCODING", str(exc))
    parser = GowinHTML(text)
    parser.feed(text)
    parser.close()
    parser.finish()
    if BAD_DIAGNOSTIC.search(" ".join(parser.visible_text)):
        reject("REPORT_DIAGNOSTIC", "error/fatal/failure in visible report text")
    metadata = {}
    clocks = {}
    paths = []
    for table in parser.tables:
        for row in table.rows:
            if len(row.cells) == 2 and row.cells[0] in IDENTITY_FIELDS:
                key, value = row.cells
                if key in metadata:
                    reject("REPORT_IDENTITY", f"duplicate metadata {key}")
                metadata[key] = value
        if not table.rows:
            continue
        header = table.rows[0].cells
        if table.anchors.get(2) == "Clock_Report":
            if header != [
                "NO.", "Clock Name", "Type", "Period", "Frequency(MHz)",
                "Rise", "Fall", "Source", "Master", "Objects",
            ]:
                reject("CLOCK_FORMAT", repr(header))
            for row in table.rows[1:]:
                if len(row.cells) != 10:
                    reject("CLOCK_FORMAT", repr(row.cells))
                name = row.cells[1]
                if name in clocks:
                    reject("CLOCK_FORMAT", f"duplicate clock {name}")
                clocks[name] = {
                    "period_ns": row.cells[3], "frequency_mhz": row.cells[4],
                    "objects": row.cells[9],
                    "row_span": span(data, text, row.start, row.end),
                }
        if header != list(PATH_COLUMNS):
            continue
        kind = None
        anchor = table.anchors.get(3, "")
        if anchor == "Setup_Slack_Table":
            kind = "setup"
        elif anchor == "Hold_Slack_Table":
            kind = "hold"
        if kind is None:
            continue
        command = table.headings.get(4, "")
        if not command.startswith("Report Command:report_timing "):
            reject("REPORT_COMMAND", command)
        if not re.search(rf"(?:^|\s)-{kind}(?:\s|$)", command):
            reject("REPORT_COMMAND", command)
        if INACTIVE.search(command):
            reject("INACTIVE_PATH", command)
        for row in table.rows[1:]:
            if len(row.cells) != len(PATH_COLUMNS):
                reject("PATH_FORMAT", repr(row.cells))
            record = dict(zip(PATH_COLUMNS, row.cells))
            record.update({
                "analysis": kind, "command": command,
                "row_span": span(data, text, row.start, row.end),
                "table_span": span(data, text, table.start, table.end),
            })
            paths.append(record)
    if metadata.get("Report Title") != "Timing Analysis Report":
        reject("REPORT_FORMAT", "not a Gowin Timing Analysis Report")
    return {"metadata": metadata, "clocks": clocks, "paths": paths}


def validate_plan(plan: dict) -> None:
    if plan.get("schema") != SCHEMA:
        reject("TARGET_SCHEMA", "unsupported schema")
    if plan.get("clock") != "sys_clk":
        reject("TARGET_CLOCK", "this task only admits sys_clk")
    if decimal(plan.get("period_ns"), "period_ns") != Decimal("25"):
        reject("TARGET_CLOCK", "this task only admits 40 MHz / 25 ns")
    source = plan.get("source")
    if not isinstance(source, dict):
        reject("TARGET_SOURCE", "source missing")
    if source.get("kind") not in (
        "FROZEN_PHYSICAL_ZIP", "M2_NEW_REPORT", "SYNTHETIC_TEST_ONLY",
    ):
        reject("TARGET_SOURCE", "unsupported source kind")
    if not isinstance(source.get("report_sha256"), str) or not SHA.fullmatch(
        source["report_sha256"]
    ):
        reject("TARGET_SOURCE", "invalid report hash")
    metadata = source.get("metadata")
    if not isinstance(metadata, dict) or set(metadata) != set(IDENTITY_FIELDS):
        reject("TARGET_SOURCE", "all raw report identity fields required")
    if any(not isinstance(v, str) or not v for v in metadata.values()):
        reject("TARGET_SOURCE", "metadata must contain nonempty exact strings")
    targets = plan.get("targets")
    if not isinstance(targets, list) or not targets or len(targets) > 64:
        reject("TARGET_SCHEMA", "1..64 exact targets required")
    ids, pairs = set(), set()
    for target in targets:
        if not isinstance(target, dict) or set(target) != {
            "id", "from_node", "to_node", "require_directed",
        }:
            reject("TARGET_SCHEMA", "invalid target fields")
        if type(target["require_directed"]) is not bool:
            reject("TARGET_SCHEMA", "require_directed must be boolean")
        for key in ("id", "from_node", "to_node"):
            value = target[key]
            if not isinstance(value, str) or not value or value != value.strip():
                reject("TARGET_SCHEMA", f"invalid {key}")
        pair = (target["from_node"], target["to_node"])
        # Exact nodes, never patterns, substring search or normalization.
        if any(c in value for value in pair for c in ("*", "?", "\n", "\r")):
            reject("TARGET_SCHEMA", "wildcard endpoint is forbidden")
        if target["id"] in ids or pair in pairs:
            reject("TARGET_SCHEMA", "duplicate target")
        ids.add(target["id"])
        pairs.add(pair)
        if target["require_directed"]:
            directed_prefixes("setup", target)


def check_report(data: bytes, plan: dict, *, archive_sha: str | None = None,
                 member: str | None = None) -> dict:
    validate_plan(plan)
    source = plan["source"]
    report_sha = sha256(data)
    if report_sha != source["report_sha256"]:
        reject("REPORT_SHA", "raw report differs from frozen target identity")
    if source["kind"] == "FROZEN_PHYSICAL_ZIP":
        if archive_sha != FROZEN_ZIP_SHA or source.get("archive_sha256") != archive_sha:
            reject("ARCHIVE_SHA", "wrong frozen physical archive")
        if member != "pnr/timing.html" or source.get("member") != member:
            reject("REPORT_MEMBER", "wrong frozen report member")
        if report_sha != FROZEN_REPORT_SHA:
            reject("REPORT_SHA", "wrong frozen physical report")
    elif archive_sha is not None:
        if source.get("archive_sha256") != archive_sha or source.get("member") != member:
            reject("ARCHIVE_SHA", "archive identity differs from targets")
    if source["kind"] != "SYNTHETIC_TEST_ONLY" and b"SYNTHETIC_TEST_ONLY" in data:
        reject("SYNTHETIC_SOURCE", "synthetic fixture cannot become a real report")
    parsed = parse_report(data)
    if parsed["metadata"] != source["metadata"]:
        reject("REPORT_IDENTITY", "raw metadata differs from target source")
    clock = parsed["clocks"].get(plan["clock"])
    if clock is None:
        reject("CLOCK_ABSENT", "sys_clk is not reported")
    if not clock["objects"] or INACTIVE.search(clock["objects"]):
        reject("CLOCK_INACTIVE", "sys_clk has no active bound object")
    if decimal(clock["period_ns"], "clock period") != Decimal("25"):
        reject("CLOCK_PERIOD", "sys_clk is not 25 ns")
    if decimal(clock["frequency_mhz"], "clock frequency") != Decimal("40"):
        reject("CLOCK_FREQUENCY", "sys_clk is not 40 MHz")
    observations = []
    for target in plan["targets"]:
        matches = [
            path for path in parsed["paths"]
            if path["From Node"] == target["from_node"]
            and path["To Node"] == target["to_node"]
        ]
        if not matches:
            reject("ENDPOINT_ABSENT", target["id"])
        for kind in ("setup", "hold"):
            typed = [p for p in matches if p["analysis"] == kind]
            if not typed:
                reject(f"MISSING_{kind.upper()}", target["id"])
            for path in typed:
                raw_fields = " ".join(path[column] for column in PATH_COLUMNS)
                if INACTIVE.search(raw_fields):
                    reject("INACTIVE_PATH", target["id"])
                expected_clock = plan["clock"] + ":[R]"
                if path["From Clock"] != expected_clock or path["To Clock"] != expected_clock:
                    reject("PATH_CLOCK", target["id"])
                slack = decimal(path["Path Slack"], "slack")
                if slack < 0:
                    reject("NEGATIVE_SLACK", target["id"])
                if not re.fullmatch(r"[1-9][0-9]*", path["Path Number"]):
                    reject("INACTIVE_PATH", "no real path number")
                relation = decimal(path["Relation"], "relation")
                if relation != (Decimal("25") if kind == "setup" else Decimal("0")):
                    reject("PATH_RELATION", target["id"])
                decimal(path["Clock Skew"], "clock skew")
                if decimal(path["Data Delay"], "data delay") < 0:
                    reject("INACTIVE_PATH", "negative data delay")
                if target["require_directed"]:
                    if not any(
                        re.fullmatch(
                            re.escape(prefix)
                            + r"(?: -max_paths [1-9][0-9]*)?"
                            + r"(?: -max_common_paths [1-9][0-9]*)?",
                            path["command"],
                        )
                        for prefix in directed_prefixes(kind, target)
                    ):
                        reject("DIRECTED_COMMAND_ABSENT", target["id"])
                observations.append({
                    "target_id": target["id"], "analysis": kind,
                    "from_node": path["From Node"], "to_node": path["To Node"],
                    "clock": plan["clock"], "slack_ns": str(slack),
                    "activity": "ACTIVE_REPORTED_FINITE_TIMING_ROW",
                    "command": path["command"],
                    "row_span": path["row_span"],
                    "table_span": path["table_span"],
                })
    return {
        "status": "SPECIFIED_REPORT_ENDPOINTS_SHOWN",
        "scope": "SOFTWARE_L0_L1_RAW_REPORT_AUDIT_ONLY",
        "board_release_allowed": False, "new_sta_executed": False,
        "physical_signoff": False, "source_kind": source["kind"],
        "report_sha256": report_sha, "metadata": parsed["metadata"],
        "clock_evidence": clock,
        "observations": observations,
        "limitation": "Pinned identities require independent M2 confirmation; hashes do not authenticate provenance.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--report", type=Path)
    inputs.add_argument("--zip", type=Path)
    parser.add_argument("--zip-sha256")
    parser.add_argument("--report-member", default="pnr/timing.html")
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--targets-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        target_data = args.targets.read_bytes()
        if not SHA.fullmatch(args.targets_sha256) or sha256(target_data) != args.targets_sha256:
            reject("TARGET_SHA", "independently pinned target identity mismatch")
        plan = strict_json(target_data)
        archive_sha = None
        if args.zip:
            archive = args.zip.read_bytes()
            archive_sha = sha256(archive)
            if not args.zip_sha256 or archive_sha != args.zip_sha256:
                reject("ARCHIVE_SHA", "independently pinned archive identity mismatch")
            with zipfile.ZipFile(args.zip) as source:
                names = source.namelist()
                if names.count(args.report_member) != 1:
                    reject("REPORT_MEMBER", "missing/duplicate member")
                if source.getinfo(args.report_member).file_size > 32 * 1024 * 1024:
                    reject("REPORT_SIZE", "report exceeds 32 MiB")
                data = source.read(args.report_member)
        else:
            if args.report.stat().st_size > 32 * 1024 * 1024:
                reject("REPORT_SIZE", "report exceeds 32 MiB")
            data = args.report.read_bytes()
        result = check_report(data, plan, archive_sha=archive_sha, member=args.report_member)
        result["targets_sha256"] = sha256(target_data)
        result["archive_sha256"] = archive_sha
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (AuditError, OSError, zipfile.BadZipFile, KeyError) as exc:
        print(json.dumps({
            "status": "REJECTED", "diagnostic": getattr(exc, "code", "INPUT_ERROR"),
            "detail": str(exc), "board_release_allowed": False,
            "new_sta_executed": False, "physical_signoff": False,
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
