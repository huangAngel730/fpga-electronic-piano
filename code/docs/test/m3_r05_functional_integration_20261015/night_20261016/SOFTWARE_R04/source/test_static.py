"""Synthetic-only regression for new reset fix and static observation wiring."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parent))
from common import ROOT, DOCS, TB_DIR, identity, write_new, Refusal
from public_ledger import analyze
from input_binding import inspect_archive

OUT = Path(sys.argv[1])


def encode(rows):
    return ("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n").encode()


def fixture():
    rows = [{"kind": "HEADER", "schema": "M3_R05_PUBLIC_PRE_NBA_V1", "clock_hz": 40000000, "first_valid_observable": False}]
    frames = {834, 1667, 2500, 3334, 4167}
    accepts = {835: 0, 1668: 1, 2501: 2, 3335: 3, 4190: 4}
    commits = {855: 0, 1688: 1, 2521: 2, 3355: 3}
    for c in range(1, 4501):
        if c == 4201:
            rows.append({"kind": "RESET", "epoch": 1, "cycle": 4200, "time_ns": 105003})
        rows.append({"kind": "TICK", "cycle": c, "epoch": int(c >= 4201),
            "rst_n": int(c > 2 and not 4201 <= c <= 4203), "frame_tick": int(c in frames),
            "request_accept": int(c in accepts), "request_id": accepts.get(c, 0),
            "commit": int(c in commits), "committed_id": commits.get(c, 0),
            "left": 0, "right": 0, "clipped": 0, "pending": 0,
            "play_left": 0, "play_right": 0, "clip_count": 0, "underflow": 0,
            "bclk": 0, "ws": 0, "din": 0, "first_valid": None})
    rows.append({"kind": "END", "cycle": 4500, "epoch": 1})
    return rows


def tick(rows, cycle):
    return next(r for r in rows if r.get("kind") == "TICK" and r["cycle"] == cycle)


def main():
    OUT.mkdir(exist_ok=False)
    write_new(OUT / "EVIDENCE_KIND.json", {"kind": "SYNTHETIC_SOFTWARE_AND_STATIC_ONLY", "real_rtl_executed": False})
    base = fixture()
    results = []
    def case(name, rows, expected=None, post=None):
        raw = encode(rows)
        path = OUT / ("SYNTHETIC_" + name + ".jsonl")
        path.write_bytes(raw)
        try:
            result = analyze(raw)
            actual = "PASS"
            if post:
                post(result)
        except Refusal as exc:
            result = {"diagnostic": exc.code, "message": str(exc)}
            actual = exc.code
        assert actual == (expected or "PASS"), (name, expected, actual)
        results.append({"name": name, "expected": expected or "PASS", "actual": actual,
            "fixture": identity(path), "result": result})

    def complete(result):
        assert result["accepted"] == 5 and result["committed"] == 4
        assert result["cancelled"] == 1 and result["pending_at_end"] == 0
        assert result["commits_without_observed_next_frame_boundary"] == 0
    case("legal_async_reset", base, post=complete)
    # Replay the same actual software fixture against old code to preserve bug.
    spec = importlib.util.spec_from_file_location("old_public_ledger", HERE.parent / "public_ledger.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    try:
        old.analyze(encode(base))
        raise AssertionError("old reset bug not reproduced")
    except Refusal as exc:
        assert exc.code == "CAPTURE_RESET"
        write_new(OUT / "OLD_RESET_REPRODUCTION.json", {"expected_old_refusal": exc.code,
            "old_source": identity(HERE.parent / "public_ledger.py"), "same_fixture": identity(OUT / "SYNTHETIC_legal_async_reset.jsonl")})
    rows = copy.deepcopy(base)
    rows = [r for r in rows if r["kind"] != "RESET"]
    for row in rows:
        if "epoch" in row:
            row["epoch"] = 0
    case("missing_reset_record", rows, "CAPTURE_RESET")
    rows = copy.deepcopy(base)
    next(r for r in rows if r["kind"] == "RESET")["epoch"] = 2
    case("wrong_reset_epoch", rows, "CAPTURE_RESET")
    rows = copy.deepcopy(base)
    tick(rows, 4201)["epoch"] = 0
    case("reset_tick_wrong_epoch", rows, "CAPTURE_ORDER")
    rows = copy.deepcopy(base)
    rows.remove(tick(rows, 100))
    case("missing_tick", rows, "CAPTURE_ORDER")
    rows = copy.deepcopy(base)
    tick(rows, 100)["left"] = "x"
    case("unknown_pcm", rows, "CAPTURE_X_OR_TYPE")
    case("missing_end", copy.deepcopy(base[:-1]), "CAPTURE_END")
    rows = copy.deepcopy(base)
    tick(rows, 855)["committed_id"] = 10
    case("wrong_commit_id", rows, "STALE_OR_DUPLICATE_COMMIT")
    rows = copy.deepcopy(base)
    tick(rows, 100)["underflow"] = 1
    case("unexpected_underflow", rows, "UNDERFLOW")
    rows = copy.deepcopy(base)
    tick(rows, 834)["request_accept"] = 1
    case("accept_on_frame_fence", rows, "SAME_FRAME_ACCEPT_OR_COMMIT")
    rows = copy.deepcopy(base)
    tick(rows, 100)["first_valid"] = 0
    case("invented_first_valid", rows, "CAPTURE_BIT")
    rows = copy.deepcopy(base)
    # A commit in a window with no future frame must remain UNKNOWN.
    tick(rows, 4190)["request_accept"] = 0
    tick(rows, 4180).update(request_accept=1, request_id=4)
    tick(rows, 4195).update(commit=1, committed_id=4)
    def unknown_tail(result):
        assert result["commits_without_observed_next_frame_boundary"] == 1
        assert result["per_request_deadline"] == "UNKNOWN_TAIL_BOUNDARY"
    case("tail_boundary_unknown", rows, post=unknown_tail)
    # Exercise the saturated public counter at an actual accepted commit.
    rows = copy.deepcopy(base)
    for row in rows:
        if row["kind"] == "TICK" and row["cycle"] < 4201:
            row["clip_count"] = 0xFFFFFFFF
    tick(rows, 855)["clipped"] = 1
    case("saturated_clip_counter", rows, post=complete)
    rows = copy.deepcopy(base)
    tick(rows, 855)["clipped"] = 1
    case("clip_increment_missing", rows, "CLIP_COUNT_ALIGNMENT")

    data, _ = inspect_archive()
    board = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/m2_fourvoice_timbre_delay_board_observed.sv"
    b = board.read_bytes()
    marker = b"\n    // NIGHT OBSERVATION ONLY:"
    start = b.index(marker)
    stop = b.index(b"\nendmodule", start)
    reversed_board = b[:start] + b[stop + 1:]
    reversed_board = reversed_board.replace(b".committed_clip(night_committed_clip)", b".committed_clip()")
    reversed_board = reversed_board.replace(b"        assign night_config_valid=m1_config_pending;\n        assign night_config_ready=m1_config_ready;\n", b"")
    assert reversed_board == data["inputs/sources/m2_fourvoice_timbre_delay_board_top.sv"]
    instrumentation = b[start:stop]
    assert b"g_polyphonic." not in instrumentation and b"#0;" in instrumentation
    assert instrumentation.index(b'HEADER') < instrumentation.index(b'#0;') < instrumentation.index(b'INITIAL_INPUTS')
    assert b"always @(midi_rx) if ($time > 0)" in instrumentation
    assert b"always @(sys_rst_n) if ($time > 0)" in instrumentation
    observer = (TB_DIR / "night_20261016/m3_r05_public_observer.sv").read_bytes()
    assert b"always @(negedge rst_n) if ($time > 0)" in observer
    for p in HERE.glob("*.py"):
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
    write_new(OUT / "TEST_RESULTS.json", {"status": "PASS", "cases": results,
        "static_checks": {"board_reverse_exact_r05": True, "header_before_initial_state": True,
            "no_time_zero_edge_writer": True, "no_new_hierarchical_observation": True,
            "observer_initial_epoch_zero": True, "python_compile_only": True},
        "board_source": identity(board), "level": "L1_SOFTWARE_AND_L0_STATIC_RTL_ONLY"})
    print("PASS NIGHT_A_STATIC_SOFTWARE cases=" + str(len(results)))


if __name__ == "__main__":
    main()
