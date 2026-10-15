"""Explicit synthetic Gowin-format fixtures; never real STA evidence."""

from copy import deepcopy
from html import escape
import json
from pathlib import Path
import zipfile

from endpoint_audit import (
    FROZEN_REPORT_SHA, FROZEN_ZIP_SHA, IDENTITY_FIELDS, PATH_COLUMNS,
    SCHEMA, parse_report, reject, sha256,
    literal_glob,
)


ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = (
    ROOT / "code/docs/evidence/m2_m1td_physical_20261015/"
    "M2_138K_M1TD_整机PnR_STA_20261015.zip"
)
FROM = (
    "g_polyphonic.u_audio_core/u_chain/u_audio/u_bank/u_pitch_mod/"
    "g_lane[3].u_control/total_s2_10_s0/Q"
)
TO = (
    "g_polyphonic.u_audio_core/u_chain/u_audio/u_bank/u_pitch_mod/"
    "g_lane[3].u_control/oct_lut_oct_lut_0_0_s/AD[7]"
)


def original() -> tuple[bytes, dict]:
    archive_bytes = ARCHIVE.read_bytes()
    if sha256(archive_bytes) != FROZEN_ZIP_SHA:
        reject("ARCHIVE_SHA", "physical original differs")
    with zipfile.ZipFile(ARCHIVE) as source:
        data = source.read("pnr/timing.html")
        manifest = json.loads(source.read("MANIFEST.json"))
    if sha256(data) != FROZEN_REPORT_SHA:
        reject("REPORT_SHA", "physical member differs")
    if manifest["files"]["pnr/timing.html"] != {
        "bytes": len(data), "sha256": sha256(data),
    }:
        reject("MANIFEST_SHA", "physical manifest differs")
    return data, parse_report(data)


def target_plan(data: bytes, metadata: dict, *, frozen=False) -> dict:
    source = {
        "kind": "FROZEN_PHYSICAL_ZIP" if frozen else "SYNTHETIC_TEST_ONLY",
        "report_sha256": sha256(data), "metadata": deepcopy(metadata),
    }
    if frozen:
        source.update({
            "archive_sha256": FROZEN_ZIP_SHA, "member": "pnr/timing.html",
        })
    return {
        "schema": SCHEMA, "clock": "sys_clk", "period_ns": "25.000",
        "source": source,
        "targets": [{
            "id": "pitch_mod_lane3_total_to_oct_address",
            "from_node": FROM, "to_node": TO, "require_directed": False,
        }],
    }


def row(cells: list[str], *, header=False) -> str:
    tag = "th" if header else "td"
    return "<tr>" + "".join(
        f"<{tag}>{escape(value)}</{tag}>" for value in cells
    ) + "</tr>\r\r\n"


def synthetic(*, omit=None, inactive=False, unrelated=False,
              negative=False, wrong_clock=False, directed=False,
              metadata=None) -> tuple[bytes, dict]:
    """Use real table/header grammar, no invented JSON timing records.

    Exact audio endpoint spellings come from original Hold path number 4.
    The Setup row and synthetic slack are deliberately NOT physical evidence.
    """
    metadata = metadata or {
        "Report Title": "Timing Analysis Report",
        "Design File": "SYNTHETIC_TEST_ONLY/design.vg",
        "Physical Constraints File": "SYNTHETIC_TEST_ONLY/design.cst",
        "Timing Constraint File": "SYNTHETIC_TEST_ONLY/design.sdc",
        "Tool Version": "SYNTHETIC_TEST_ONLY (Gowin V1.9.11.03 grammar)",
        "Part Number": "SYNTHETIC_TEST_ONLY",
        "Device": "SYNTHETIC_TEST_ONLY",
        "Device Version": "SYNTHETIC_TEST_ONLY",
        "Created Time": "SYNTHETIC_TEST_ONLY",
    }
    text = '<html><head><title>Timing Analysis Report</title></head><body>\r\r\n'
    text += "<!-- SYNTHETIC_TEST_ONLY, NOT AN EDA RUN -->\r\r\n"
    text += '<h1><a name="Message">Timing Messages</a></h1><table>\r\r\n'
    for key in IDENTITY_FIELDS:
        text += row([key, metadata[key]])
    text += '</table><h2><a name="Clock_Report">Clock Summary:</a></h2><table>\r\r\n'
    text += row([
        "NO.", "Clock Name", "Type", "Period", "Frequency(MHz)", "Rise",
        "Fall", "Source", "Master", "Objects",
    ], header=True)
    text += row([
        "1", "sys_clk", "Generated", "25.000", "40.000", "0.000",
        "12.500", "sys_clk", "ref_clk", "SYNTHETIC/PLL/CLKOUT2",
    ])
    text += '</table><h1><a name="Detail">Timing Details</a></h1>\r\r\n'
    start, finish = FROM, TO
    if unrelated:
        start = "g_polyphonic.u_audio_core/u_other/unrelated_s0/Q"
        finish = "g_polyphonic.u_audio_core/u_other/unrelated_s1/D"
    for kind in ("setup", "hold"):
        if kind == omit:
            continue
        text += (
            f'<h3><a name="{kind.title()}_Slack_Table">'
            f'{kind.title()} Paths Table</a></h3>\r\r\n'
        )
        command = f"report_timing -{kind}"
        if directed:
            command += (
                f" -from [get_regs {{{literal_glob(start.rsplit('/', 1)[0])}}}]"
                f" -to [get_pins {{{literal_glob(finish)}}}]"
            )
        command += " -max_paths 10 -max_common_paths 1"
        text += f"<h4>Report Command:{escape(command)}</h4><table>\r\r\n"
        text += row(list(PATH_COLUMNS), header=True)
        clock = "other_clk:[R]" if wrong_clock else "sys_clk:[R]"
        slack = "-0.001" if negative else "0.125"
        if inactive:
            slack = "inactive"
        text += row([
            "1", slack, start, finish, clock, clock,
            "25.000" if kind == "setup" else "0.000", "0.000", "0.500",
        ])
        text += "</table>\r\r\n"
    text += "</body></html>\r\r\n"
    data = text.encode("utf-8")
    return data, target_plan(data, metadata)


def serialize(plan: dict) -> bytes:
    return (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def matrix() -> list[tuple[str, bytes, dict, str]]:
    cases = []
    for name, options, expected in (
        ("synthetic_positive", {}, "SPECIFIED_REPORT_ENDPOINTS_SHOWN"),
        ("synthetic_missing_endpoint", {"unrelated": True}, "ENDPOINT_ABSENT"),
        ("synthetic_inactive", {"inactive": True}, "INACTIVE_PATH"),
        ("synthetic_only_unrelated_audio", {"unrelated": True}, "ENDPOINT_ABSENT"),
        ("synthetic_setup_only", {"omit": "hold"}, "MISSING_HOLD"),
        ("synthetic_hold_only", {"omit": "setup"}, "MISSING_SETUP"),
        ("synthetic_negative_slack", {"negative": True}, "NEGATIVE_SLACK"),
        ("synthetic_wrong_clock", {"wrong_clock": True}, "PATH_CLOCK"),
    ):
        data, plan = synthetic(**options)
        if name == "synthetic_missing_endpoint":
            # Unlike the unrelated-audio case, the exact target start occurs.
            data, plan = synthetic()
            data = data.replace(TO.encode("utf-8"), (TO + "_missing").encode("utf-8"))
            plan["source"]["report_sha256"] = sha256(data)
        cases.append((name, data, plan, expected))
    return cases
