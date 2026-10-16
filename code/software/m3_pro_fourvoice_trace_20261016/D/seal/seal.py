"""Package existing D evidence without executing functional/EDA tests."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile


SOURCE = Path(__file__).resolve().parents[1]
ROOT = SOURCE.parents[3]
DOCS = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D"


def identity(path):
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    begin = time.monotonic()
    seal = DOCS / "SEAL_20261017"
    seal.mkdir(exist_ok=False)
    write(seal / "LAUNCH.json", {"argv": [sys.executable, "-X", "utf8", str(Path(__file__).resolve())],
          "cwd": str(Path.cwd()), "machine": platform.node(), "started_utc": datetime.now(timezone.utc).isoformat(),
          "purpose": "ARTIFACT_INTEGRITY_UTILITY_NO_FUNCTIONAL_OR_EDA_ROUND", "source": identity(Path(__file__).resolve())})
    rounds = [read(DOCS / f"round_{n}/RUN_RECEIPT.json") for n in (1, 2, 3)]
    for r in rounds:
        assert r["source_before"] == r["source_after"]
        assert not r["timeout"]
    for item in rounds[-1]["source_after"].values():
        assert identity(Path(item["path"])) == item, "POST_DELTA_SOURCE_DRIFT"
    positive = read(DOCS / "round_1/cases/positive/RESULT.json")
    r1 = read(DOCS / "round_1/cases/RESULTS.json")
    r2 = read(DOCS / "round_2/cases/RESULTS.json")
    delta = read(DOCS / "round_3/cases/RESULT.json")
    assert [r["exit_code"] for r in rounds] == [1, 0, 0]
    assert len(r1) == 3 and r1[0]["passed"] and r1[1]["passed"] and not r1[2]["passed"]
    assert len(r2) == 11 and all(c["passed"] for c in r2) and delta["passed"]
    active = [r for r in positive["request_ledger"] if "request_to_serial_cycles" in r]
    tool_seconds = sum(r["seconds"] for r in rounds)
    preflight = read(DOCS / "preflight_20261017/PREFLIGHT.json")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    refresh_inputs = [ROOT / "code/docs/M3_完赛任务单_2026-10-15.md",
                      ROOT / "code/docs/138K四声部后续集成任务总览_2026-10-15.md",
                      ROOT / "code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json"]
    input_copies = seal / "inputs"
    input_copies.mkdir()
    inputs = []
    source_inputs = [Path(i["path"]) for i in preflight["input_facts"]]
    source_inputs += [Path(i["path"]) for i in delta["inputs"] if "/C/" in i["path"].replace("\\", "/")]
    source_inputs += refresh_inputs
    for number, p in enumerate(dict.fromkeys(source_inputs)):
        dest = input_copies / f"{number:02}_{p.name}"
        raw = p.read_bytes()
        dest.write_bytes(raw)
        now = identity(p)
        original = next((i for i in preflight["input_facts"] if i["path"] == str(p)), None)
        inputs.append({"current": now, "copy": identity(dest), "T0_identity": original,
                       "T0_bytes_same": now == original if original else None,
                       "capture_phase": "SEAL_TIME_READ_ONLY_COPY"})
    write(seal / "INPUT_SNAPSHOTS.json", inputs)
    receipt = {"status": "DONE_D_D2_FIXTURE__PRO_DUT_PENDING", "level": "L1_SOFTWARE_FIXTURE_ONLY",
          "initial_head": preflight["head"], "seal_head": head,
          "machine": preflight["machine"], "python_version": preflight["python_version"],
          "python_dependencies_at_preflight_and_round_launch": preflight["dependencies"],
          "rounds_consumed": 3, "rounds_max_D_D2": 4, "D3_reserved_rounds": 2,
          "round_exit_codes": [1, 0, 0], "functional_seconds": tool_seconds,
          "preflight_seconds_separate": preflight["seconds"], "per_round_limit_s": 90,
          "round_receipts": [identity(DOCS / f"round_{n}/RUN_RECEIPT.json") for n in (1, 2, 3)],
          "positive": {"cycles": positive["cycles"], "request_commit_count": len(positive["request_ledger"]),
                       "serial_frames_including_startup": len(positive["serial_frames"]),
                       "complete_request_serial_count": len(active), "serial_half_frames": len(positive["serial_half_frames"]),
                       "hand_vectors": positive["hand_vectors_covered"], "frame_intervals": positive["frame_intervals"],
                       "max_request_to_serial_cycles": max(r["request_to_serial_cycles"] for r in active),
                       "serial_dispositions_derived_audit": delta["reset_dispositions"],
                       "PA_policy": "HIGH_ACTIVE_8_STABLE_CYCLES_FIXTURE_ONLY"},
          "serial_negative_cases": [r1[1]] + r2,
          "delta_result": identity(DOCS / "round_3/cases/RESULT.json"),
          "C_identity_crosswalk": identity(DOCS / "round_3/cases/C_IDENTITY_LINK.json"),
          "C_negative_links_rejected": 5, "source_drift_guard": "PASS_AND_ALL_THREE_ROUNDS_UNCHANGED",
          "final_checker_scope": "new reset metadata helper tested by delta, full original serial groups reused unchanged",
          "first_failure": identity(DOCS / "round_1/cases/shift_one_bit/CASE_RECEIPT.json"),
          "M1_status": "OLD_R05_FIVE_DIRECTORIES_PUBLISHED_NOW__NOT_NEW_PRO_GOLD", "Pro_status": "PENDING_EXACT_SOURCE_ROM_TOP_TRACE",
          "EDA_calls": 0, "Icarus_calls": 0, "hardware_calls": 0, "Git_writes": 0,
          "unverified": ["Pro actual PCM/clip mathematics, source and real lane-to-output identity",
                         "Pro actual sample/deadline/clock and PA enable behavior", "same-version STA/PnR",
                         "analog <=10ms, real Bank/levels/PA polarity, headphones/amplifier, board"],
          "inputs": identity(seal / "INPUT_SNAPSHOTS.json"), "board_release_allowed": False,
          "handoff": "LOCAL_SEALED_READY_FOR_AUTHORIZED_COORDINATOR__M2_HUMAN_NOT_NOTIFIED"}
    write(DOCS / "NIGHT_RUN_RECEIPT.json", receipt)
    report = f"""# D/D2 10月17日限定结果

DONE_D_D2_FIXTURE；真实Pro对照仍PENDING。L1独立Python夹具，board_release_allowed=false。本窗口仅写D自有目录，未改coordinator/ingest、正式RTL或共享状态，未提交/推送；由夜间总控统一发布。

正例38000拍、44次请求/提交、16组手算PCM24边界、42个完整立体声帧（含两段启动零值）、88个完整半帧。40笔请求串行完整，最大请求到串行末位1673拍=41.825μs，仅为夹具数字结果。各epoch间隔833拍14次、834拍7次，连续三个间隔和2500；PA策略高有效、稳定指示8拍后开，均非Pro实测。

12个串行/期限/epoch/PA坏例均实际CLI exit1并符合首差异。首轮错位坏例已被拒收，但预期诊断写错导致整体exit1；修正后只续跑11个未完成组。所有首失败和源码原件保留。源码漂移门禁已补，三个历史轮前后源码一致。

复位审计明确：epoch0 ID21已采样串行未完、ID22已提交未采样，均在19001拍被复位取消；epoch1 ID21串行尾、ID22下帧采样因END未知。旧正例RESULT保持原样，修正见round_3/cases/RESET_DISPOSITION_AUDIT.json；新增helper已定向验证，没有以最终checker重复原13组。

C只读身份crosswalk保留76个lane ID（71消费、5取消），映射18组已有诊断串行请求，5个新映射坏例拒收。映射按epoch内消费帧序号，原C/D拍号分开；诊断PCM与音符无数学关系，不签C→PCM算法、共同执行时间轴或真实Pro请求身份。

消耗3/4轮，真实功能用时{tool_seconds:.6f}秒；round exits=1/0/0，均无超时。Python预检另{preflight['seconds']:.6f}秒。Icarus/ModelSim/Gowin/STA/硬件均0；D3仍由总控管理。剩余额度不自动消费。

当前仓库HEAD {head}；M1旧R05五目录已发布，Pro source/ROM/top/trace仍缺。输入更新不触发旧专项重跑。未验项包括真实Pro数学/期限/PA、同版物理时序、Bank与模拟/板测。M2/M1真人交接由总控提供，待用户转发。

入口：NIGHT_RUN_RECEIPT.json、FIXTURE_CONTRACT.md、各round的LAUNCH/CONSUMED/RUN_RECEIPT、round_3身份表。封包以LATEST_RECEIPT.json为准；含原捕获本体、失败原件、每轮源码、输入快照、SHA清单和CRC验证。
"""
    with (DOCS / "RESULT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
    with (DOCS / "SELF_REVIEW.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("# 自审边界\n\n本窗口及自身只读子智能体自审。发现并修复复位disposition、源码漂移拒签两处具体缺口；round3定向验证PASS，子智能体只读复查增量未发现具体阻断，未运行程序或修改文件。未启用审核员/预审员制度，不替代M2最终复核。C映射仅诊断身份，旧R05已发布与新Pro待件分开。\n")
    payload = []
    for base in (SOURCE, DOCS):
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base)
            if any(part in {"coordinator", "ingest", "__pycache__", ".pytest_cache"} for part in rel.parts):
                continue
            if base == DOCS and rel.parts[0] == "SEAL_20261017":
                if rel.name not in {"LAUNCH.json", "INPUT_SNAPSHOTS.json"} and rel.parts[1] != "inputs":
                    continue
            payload.append((p.relative_to(ROOT).as_posix(), p))
    manifest = [{"archive_path": name, **identity(p)} for name, p in payload]
    write(seal / "MANIFEST.json", manifest)
    archive = seal / "M3_D_D2_PCM24_PT8211_FIXTURE_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, p in payload:
            z.write(p, name)
        z.write(seal / "MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, "ZIP_CRC"
        assert len(z.namelist()) == len(manifest) + 1
        for item in manifest:
            data = z.read(item["archive_path"])
            assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"]
    verification = {"exit_code": 0, "purpose": "ARTIFACT_INTEGRITY_ONLY", "payload_members_verified": len(manifest),
                    "CRC_size_SHA": "ALL_MATCH", "seconds": time.monotonic() - begin, "archive": identity(archive)}
    write(seal / "VERIFICATION.json", verification)
    latest = {"status": receipt["status"], "receipt": identity(DOCS / "NIGHT_RUN_RECEIPT.json"),
              "result": identity(DOCS / "RESULT.md"), "archive": identity(archive),
              "manifest": identity(seal / "MANIFEST.json"), "verification": identity(seal / "VERIFICATION.json"),
              "rounds_consumed": 3, "functional_seconds": tool_seconds, "Git_published_by_this_window": False,
              "board_release_allowed": False}
    write(DOCS / "LATEST_RECEIPT.json", latest)
    print(json.dumps(latest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
