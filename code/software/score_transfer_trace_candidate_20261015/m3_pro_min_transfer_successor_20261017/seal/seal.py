"""Seal existing E3 evidence; no new functional, compiler, simulator or EDA call."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
TAG = "m3_pro_min_transfer_successor_20261017"
DOCS = ROOT / "code/docs/test" / TAG
RTL_DIR = ROOT / "code/rtl/input/score_transfer_candidate" / TAG
TB_DIR = ROOT / "code/tb/input/score_transfer_candidate" / TAG


def identity(path):
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    begin = time.monotonic()
    out = DOCS / "SEAL_R01"
    out.mkdir(exist_ok=False)
    write(out / "LAUNCH.json", {"argv": [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve())],
          "cwd": str(Path.cwd()), "time_utc": datetime.now(timezone.utc).isoformat(),
          "scope": "ARTIFACT_INTEGRITY_ONLY_NO_NEW_FUNCTIONAL_ROUND", "source": identity(Path(__file__).resolve())})
    rounds = [read(DOCS / f"ROUND_{n:02}/RUN_RECEIPT.json") for n in range(1, 7)]
    assert [r["exit_code"] for r in rounds] == [1, 1, 1, 0, 0, 0]
    assert all(r["source_before"] == r["source_after"] and r["runtime_after_same"] for r in rounds)
    for item in rounds[-1]["source_after"]:
        assert identity(Path(item["path"])) == item, "FINAL_SOURCE_DRIFT"
    preflight = read(DOCS / "PREFLIGHT/PREFLIGHT.json")
    positive = read(DOCS / "ROUND_05/checked/RESULT.json")
    strict = read(DOCS / "ROUND_05/frozen_strict_trace/report.json")
    negative = read(DOCS / "ROUND_05/mutant_checked/RESULT.json")
    delta = read(DOCS / "ROUND_06/delta/RESULT.json")
    assert positive["passed"] and strict["status"] == "PASS" and delta["passed"]
    assert negative["first_difference"]["code"] == "RESPONSE_ERROR"
    assert negative["first_difference"]["expected"] == [3, 9] and negative["first_difference"]["actual"] == [3, 0]
    task = Path(preflight["task"]["path"])
    contract = Path(preflight["protocol"]["path"])
    originals = out / "inputs"
    originals.mkdir()
    facts = [task, contract, ROOT / "AGENTS.md", ROOT / "code/AGENTS.md", ROOT / "code/rtl/input/AGENTS.md",
             ROOT / "code/docs/协作入口.md", ROOT / "code/docs/夜间任务通用执行规范.md",
             ROOT / "code/docs/M3_完赛任务单_2026-10-15.md", ROOT / "code/docs/138K四声部后续集成任务总览_2026-10-15.md",
             ROOT / "code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/task2_coordinator/NIGHT_PLAN_20261017_TASK2.md"]
    copies = []
    for n, p in enumerate(facts):
        dest = originals / f"{n:02}_{p.name}"
        dest.write_bytes(p.read_bytes())
        copies.append({"original": identity(p), "copy": identity(dest), "phase": "SEAL_TIME_READ_ONLY_SNAPSHOT"})
    assert identity(task) == preflight["task"] and identity(contract) == preflight["protocol"]
    write(out / "INPUT_SNAPSHOTS.json", copies)
    seconds = sum(r["seconds"] for r in rounds)
    source = identity(RTL_DIR / "score_transfer_e3_successor.sv")
    old = identity(ROOT / "code/rtl/input/score_transfer_candidate/score_transfer_candidate.sv")
    assert old["sha256"] == "551fc393621d2f4b014e0d19f8c5d47ce39b594f040d4ed273929805f63fc537"
    receipt = {"status": "E3_PARTIAL__OFFLINE_SUCCESSOR_L2_COMPLETE__PHYSICAL_PENDING",
          "level": "L2_ISOLATED_RTL_UART_RAM_PLUS_L1_SOURCE_AND_METADATA", "source": source, "original_read_only": old,
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
          "initial_head": preflight["head"], "machine": preflight["machine"], "python_version": preflight["python_version"],
          "Icarus_version_stdout": identity(DOCS / "PREFLIGHT/iverilog.stdout.bin"),
          "runtime_bound_files": len(preflight["runtime"]), "preflight": identity(DOCS / "PREFLIGHT/PREFLIGHT.json"),
          "real_midi": preflight["midi"], "records": identity(DOCS / "ROUND_05/inputs/records.bin"),
          "source_rights": "Existing SOURCE_RIGHTS.txt records GolhaMedia Commons revision1224484831/CC0; original300bytes unchanged",
          "rounds_consumed": 6, "rounds_max": 6, "round_exit_codes": [1, 1, 1, 0, 0, 0],
          "round_seconds_total": seconds, "preflight_seconds_separate": sum(s["seconds"] for s in preflight["steps"]),
          "round_receipts": [identity(DOCS / f"ROUND_{n:02}/RUN_RECEIPT.json") for n in range(1, 7)],
          "positive": {k: positive[k] for k in ("events", "records_bytes", "cases", "packets", "capture_cycles", "public_ram_full_snapshots")},
          "strict_clean_trace": {"status": strict["status"], "summary": strict["summary"],
                                 "scope": "clean106frames/53request-response/3exactreplays only, fullNACKtrace not strictPASS"},
          "negative_protocol_NACKs": positive["negative_responses"], "CRC_bypass_behavior_mutant": negative,
          "NACK8_fix": "v1 EXEC errors4/5/6/8 invalidate session/cache before metadata; following DATA rejected, oldbank intact, fresh BEGIN recovery",
          "scope_limit": "version/framing prechecks unchanged; default5s session not reexecuted, isolated50ms parameter only",
          "final_checker_metadata_delta": delta, "whole_final_checker_full_rerun": False,
          "verification_relation": "ROUND05 proves RTL/protocol checks; ROUND06 only guards final coverage label, no repeated serial/RTL groups",
          "first_failures": "ROUND01..03 compile crash0xC0000005 emptyrawstreams preserved, normal permission ROUND04 resolves execution block",
          "failure_history": identity(DOCS / "FAILURE_HISTORY.md"),
          "self_review": "own implementation and own read-only subagent incremental review, no blocker in final delta; not formal audit制度 or M2 acceptance",
          "unverified": ["formal Pro source/ROM/top and UART pin/Bank/CST/levels", "RAM/BSRAM synthesis and same-version full STA/PnR",
                         "approved Pro bitstream/download and real wired/phone hardware ACK/fullREAD", "playback and PCM outside this transport result"],
          "ModelSim_calls": 0, "Gowin_calls": 0, "hardware_calls": 0, "Git_writes": 0,
          "board_release_allowed": False, "publication": "NOT_COMMITTED_NOT_PUSHED_BY_THIS_WINDOW__COORDINATOR_SERIAL_PUBLICATION",
          "communication_authorization": {"thread": "01a14050-cd98-7c41-8004-5d3e25765167", "direct_user_message": "01a145c8-5120-7840-aaad-88154b268e21"},
          "M2_human_handoff": "待用户转发，尚未送达"}
    write(DOCS / "NIGHT_RUN_RECEIPT.json", receipt)
    report = f"""# E3一份真实文件最小传谱后继

整体E3=PARTIAL；离线后继限定L2完成，实体串口/手机有线、正式Pro工程与码流准入PENDING，board_release_allowed=false。未提交/推送，由夜间总控统一发布并交M2。

只用本地GolhaMedia MIDI_sample_2018-03-21.mid原件300字节，SHA {preflight['midi']['sha256']}；22音符/44记录、Type0单轨默认tempo。原严格导入器/T057编码及独立MIDI oracle只读，产生352字节records；实际RTL UART115200/40MHz→RAM→全部44条UART READ逐字节核同，不是离线伪造应答或自动演奏。

新score_transfer_e3_successor来源旧SHA {old['sha256']}，新SHA {source['sha256']}。按PROTOCOL第26行，v1执行层COMMIT错误4/5/6/8清会话与缓存，次拍响应active0；旧文件/公共协议不改，成功请求ACK重放优先级保留。旧版ROUND04结果与修复后ROUND05分开，不能倒签旧分歧已修。

ROUND05：127场景、112个完整应答、11次完整44条公开RAM快照通过；干净段44条完整UART READ及3次精确ACK重放，冻结严格checker106帧PASS。14个预期NACK覆盖丢DATA/帧CRC/20ms帧超时/50ms参数会话超时/整曲CRC/失败COMMIT清会话/旧cached DATA与新DATA拒收，异常后旧曲谱保留，fresh BEGIN恢复。完整含NACK轨迹不冒称冻结严格checker PASS。

真实CRC旁路RTL变体编译/仿真均0，checker exit1：COMMIT应NACK9，实际ACK0；不是崩溃/超时伪反例。最终报告出口修复只在ROUND06定向验5个覆盖控制，缺新增覆盖时NOT_EXERCISED；没有重跑已成功串行组。最终checker未全量重跑，RTL和协议结论来自ROUND05固定源，标签helper来自ROUND06。

共6/6轮、{seconds:.6f}秒，整体轮退出1/1/1/0/0/0。前三轮沙盒编译0xC0000005原双流/源齐全，路径与环境尝试未解除；正常权限同工具编译0后完成，无安装/换工具。所有来源/工具前后同，runtime1152文件SHA冻结。工具版本Icarus14.0 devel与Python3.12.4见原probe；无ModelSim/Gowin/综合/STA/设备/Git写。

只读子智能体自审最终增量未见具体阻断，不代M2正式复核。正式接入/实物续做见FORMAL_INTEGRATION_GAPS.md：M2选定行为/BRAM后继、受控ProUART/完整时序/码流；M3取得安全链路后同一文件实体ACK及44条完整READ。50ms仅参数化隔离测试，不签生产默认5s新验证。播放/PCM/BLE/编辑器/多设备均未验。

原件入口：NIGHT_RUN_RECEIPT.json、各ROUND的LAUNCH/CONSUMED/RUN_RECEIPT与CAPTURE、ROUND05/checked及frozen_strict_trace、ROUND06/delta、RTL_PATCH_PROVENANCE.json。LATEST_RECEIPT.json链接原件ZIP与SHA/CRC清单。真人M2交接待用户转发，尚未送达。
"""
    with (DOCS / "RESULT.md").open("x", encoding="utf-8", newline="\n") as f:
        f.write(report)
    payload = []
    for base in (RTL_DIR, TB_DIR, HERE, DOCS):
        for p in sorted(base.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            rel = p.relative_to(base)
            if base == DOCS and rel.parts[0] == "SEAL_R01":
                if rel.name not in {"LAUNCH.json", "INPUT_SNAPSHOTS.json"} and rel.parts[1] != "inputs":
                    continue
            payload.append((p.relative_to(ROOT).as_posix(), p))
    manifest = [{"archive_path": name, **identity(p)} for name, p in payload]
    write(out / "MANIFEST.json", manifest)
    archive = out / "M3_E3_REAL_MIDI_UART_RAM_SUCCESSOR_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, p in payload:
            z.write(p, name)
        z.write(out / "MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(manifest) + 1
        for item in manifest:
            data = z.read(item["archive_path"])
            assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    verified = {"exit_code": 0, "scope": "ARTIFACT_CRC_SIZE_SHA_ONLY_NO_FUNCTIONAL_ROUND",
                "members_verified": len(manifest), "CRC_size_SHA": "ALL_MATCH",
                "seconds": time.monotonic() - begin, "archive": identity(archive)}
    write(out / "VERIFICATION.json", verified)
    latest = {"status": receipt["status"], "receipt": identity(DOCS / "NIGHT_RUN_RECEIPT.json"),
              "result": identity(DOCS / "RESULT.md"), "archive": identity(archive),
              "manifest": identity(out / "MANIFEST.json"), "verification": identity(out / "VERIFICATION.json"),
              "source": source, "rounds_consumed": 6, "round_seconds_total": seconds, "Git_published": False,
              "board_release_allowed": False}
    write(DOCS / "LATEST_RECEIPT.json", latest)
    print(json.dumps(latest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
