"""One new static source/anchor audit; never invokes HDL or EDA tools."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

sys.dont_write_bytecode = True
HERE = Path(sys.argv[1]).resolve()
PRODUCTS = Path(sys.argv[2]).resolve()
ROOT = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(name, value):
    with (PRODUCTS / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    items = load("INPUT_IDENTITIES.json")
    by_id = {item["id"]: item for item in items}
    assert len(items) == len(by_id) == 42, "INPUT_COUNT_OR_DUPLICATE"
    texts = {}
    for item in items:
        source, frozen = Path(item["source"]), Path(item["frozen"])
        assert sha(source) == sha(frozen) == item["sha256"], "INPUT_DRIFT:" + item["id"]
        assert frozen.stat().st_size == item["bytes"], "INPUT_BYTES"
        if frozen.suffix != ".zip":
            texts[item["id"]] = frozen.read_text(encoding="utf-8-sig")
    assert by_id["task_day"]["sha256"] == "4142a701d0f48c3965c0596641be859d85cf7788b2d17d5d3af64f0e1745af75"
    assert by_id["task_finish"]["sha256"] == "7235fb23d4584687259d2743aaa4b91a517e2b5bd3dc8867f0e29857f3b14033"
    expected_old = {
        "old_top": "f2a8f30fef8ad2da26d1d3b80793b727f45806b6d5c78f2a071fb383322639be",
        "old_shell": "df1f05b4a6a06deddd9d3a2244106ec29bb0d15e5dd808fc9bef9436d710a5cf",
        "old_sdc": "a8791f826c0bd8630483ce28c44636c24e4e28c041a9622d17d0b1764a8f888f",
        "old_cst": "1f22af2d963315cfe625af5f22b25c9ce68152ee0ec2bed859d36b3a196e723d",
    }
    for name, expected in expected_old.items():
        assert by_id[name]["sha256"] == expected, "OLD_CONTRACT_IDENTITY:" + name
    anchors = []
    for item in load("ANCHOR_SPEC.json"):
        text = texts[item["source"]]
        lines = text.splitlines()
        excerpt = "\n".join(lines[item["first"] - 1:item["last"]])
        assert 1 <= item["first"] <= item["last"] <= len(lines), "LINE_RANGE:" + item["id"]
        for expected in item["contains"]:
            assert expected in excerpt, "ANCHOR_MISMATCH:" + item["id"] + ":" + expected
        anchors.append({**item, "source_sha256": by_id[item["source"]]["sha256"],
                        "source_path": by_id[item["source"]]["source"], "excerpt": excerpt,
                        "status": "OBSERVED_SOURCE_TEXT_ONLY"})
    write("ANCHORS_VERIFIED.json", anchors)
    package = texts["event_package"].split("} performance_event_t;", 1)[0]
    package = package.rsplit("typedef struct packed {", 1)[1]
    widths = [int(high) - int(low) + 1
              for high, low in re.findall(r"logic\s+\[(\d+):(\d+)\]", package)]
    assert len(widths) == 9 and sum(widths) == 64, "EVENT_SOURCE_WIDTH"
    frame_width = int(re.search(r"parameter integer FRAME_WIDTH = (\d+)", texts["control_bridge"])[1])
    assert 34 + 2 * frame_width == 98, "SCORE_SOURCE_WIDTH"
    first_stage = [line for line in texts["old_sdc"].splitlines()
                   if line.startswith("set_false_path -to") and "u_visual/" in line]
    assert len(first_stage) == 7, "OLD_FIRST_STAGE_COUNT"
    payload_setup = [line for line in texts["old_sdc"].splitlines()
                     if line.startswith("report_timing -setup") and "payload_hold" in line]
    payload_hold = [line for line in texts["old_sdc"].splitlines()
                    if line.startswith("report_timing -hold") and "payload_hold" in line]
    assert len(payload_setup) == 2 and not payload_hold, "OLD_PAYLOAD_REPORT_BOUNDARY"
    for literal in ("TMDS_PLL u_video_pll", "video_scan_timing u_scan", "DVI_TX_Top u_video_tx"):
        assert texts["old_shell"].count(literal) == 1, "OLD_SINGLE_ROLE:" + literal
    assert "clkout2" not in texts["current_board_shell"]
    assert by_id["current_board_shell"]["sha256"] != by_id["old_shell"]["sha256"]
    pairs = {}
    for current, old in (("event_package", "old_package"), ("event_bridge", "old_event_bridge"),
                         ("control_bridge", "old_control_bridge"), ("mailbox", "old_mailbox"),
                         ("scanner", "old_scanner")):
        pairs[current] = {"old_id": old, "same_bytes": by_id[current]["sha256"] == by_id[old]["sha256"]}
    old_delivery = json.loads(texts["previous_delivery"])
    old_zip = Path(by_id["previous_zip"]["frozen"])
    assert sha(old_zip) == old_delivery["sha256"] == "2de22e136aa074604407592b7df91af9ff2db05357b1d508a61de9ec7c313757"
    with zipfile.ZipFile(old_zip) as archive:
        assert archive.testzip() is None and len(archive.namelist()) == 129
    previous = json.loads(texts["previous_receipt"])
    assert previous["passed"] and previous["identity_stable"]
    for name, file_name in (("candidate", "dual_slider_pro_parallel.sv"), ("testbench", "tb_pro_parallel.sv")):
        recorded = [value["sha256"] for key, value in previous["before"]["inputs"].items()
                    if Path(key).name == file_name]
        assert recorded == [by_id[name]["sha256"]], "PREVIOUS_SIGNED_SOURCE_DRIFT:" + name
    inventory = load("DISCOVERY_INVENTORY.json")
    for item in inventory:
        assert sha(Path(item["path"])) == item["sha256"], "INVENTORY_FILE_DRIFT"
    pro_sources = [item for item in inventory if item["scope"] == "code/rtl/138K_Pro"
                   and Path(item["path"]).suffix.lower() in (".sv", ".v", ".gprj", ".sdc")]
    assert not pro_sources, "PRO_SCOPE_CHANGED_REASSESS_PENDING"
    write("READ_ONLY_REFERENCES.json", {"baseline_head_at_discovery": "414e1a9d3ee0617c5e8ba72dd4b22c36122c9926",
                                       "git_blob_identity": "NOT_RECOMPUTED_THIS_WINDOW",
                                       "input_copies_local_only_not_republished": True,
                                       "references": items})
    lines = ["# 冻结原件索引\n", "每项SHA是原始字节，行号仅UTF-8文本。本地INPUT_ORIGINALS保留副本但不入新zip/发布清单；旧材料只读引用原Git/文件位置。\n",
             "| ID | 原路径 | 原字节 | SHA256 | 本体 |", "| --- | --- | ---: | --- | --- |"]
    for item in items:
        lines.append(f"| {item['id']} | {item['source']} | {item['bytes']} | {item['sha256']} | INPUT_ORIGINALS/{Path(item['frozen']).name} |")
    with (PRODUCTS / "FINAL_SOURCE_INDEX.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    result = {
        "task": "TASK_DAY_E1_PRO_INTEGRATION_STATIC_DIFF", "limited_preparation": "DONE_L0",
        "formal_integration": "PENDING_PRO_SOURCE_OR_PRODUCERS", "actual_level": "L0_STATIC_ONLY",
        "source_originals_verified": len(items), "line_anchors_verified": len(anchors),
        "inventory_members_verified": len(inventory), "old_first_stage_groups": 7,
        "declared_event_width": sum(widths), "declared_score_width": 34 + 2 * frame_width,
        "old_payload_setup_reports": len(payload_setup), "old_payload_hold_reports": len(payload_hold),
        "old_to_current_common_source_comparison": pairs,
        "current_shell_versus_old_shell": "DIFFERENT_50MHZ_TWO_OUTPUT_VS_40MHZ_THREE_OUTPUT",
        "old_L2_zip_sha256": sha(old_zip), "old_L2_members": 129,
        "old_L2_read_only_reused": True, "old_487_4_reruns": 0,
        "old_cases_and_zip_republished": False, "input_copies_in_new_zip": False,
        "new_RTL_positive_negative_tests": "NOT_RUN_NOT_AUTHORIZED_THIS_TASK",
        "ModelSim_Icarus_Gowin_STA_device_calls": 0, "software_validation_round": int(PRODUCTS.parent.name[-2:]),
        "git_index_commit_push_gate_state_writes": 0, "board_release_allowed": False,
        "Pro_mode_producer": "UNKNOWN", "Pro_score_producer": "UNKNOWN", "Pro_frame_epoch": "UNKNOWN",
        "Pro_accepted_copy_point": "UNKNOWN", "Pro_PLL_source_ROM_top_trace": "NOT_RECEIVED",
        "Pro_CDC_matched_objects_and_payload_bits": "UNKNOWN", "Pro_full_STA_screen": "NOT_RUN",
        "next_owner": "M2 freezes new Pro closure/producers and controlled integration after base+timbre; M3 later screen originals",
        "communication": "NO_SEND_TOOL_PER_LATEST_COORDINATOR_INSTRUCTION; coordinator reads local files",
        "real_M2_delivery": "待用户转发，尚未送达", "time_utc": datetime.now(timezone.utc).isoformat(),
    }
    write("RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
