"""Isolated snapshot selector test, not a parser or physical build."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import random
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "code/tb/common/control_arbiter_deep_pipeline"
CAD = Path("D:/Gowin/oss-cad-suite")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    out = args.output.resolve()
    out.relative_to(ROOT / "code/output")
    out.mkdir(parents=True, exist_ok=False)
    rng = random.Random(0x20261005)
    masks = ([0, 0xffffffff] + [1 << k for k in range(32)] +
             [(1 << k) | (1 << ((k+1) % 32)) for k in range(32)] +
             [0xaaaaaaaa, 0x55555555, 0x80000001] +
             [rng.getrandbits(32) for _ in range(512)])
    assert len(masks) == 581
    rows = []
    ordinal = 0
    for rr in range(32):
        for mask in masks:
            winners = [(rr+k) % 32 for k in range(32)
                       if mask & (1 << ((rr+k) % 32))]
            first = winners[0] if winners else 0
            second = winners[1] if len(winners) > 1 else 0
            epoch = (ordinal * 67123 + 0xffffff00) & 0xffffffff
            rows.append(f"{ordinal} {mask:08x} {rr} {epoch:08x} "
                        f"{int(bool(winners))} {first} "
                        f"{int(len(winners)>1)} {second}\n")
            ordinal += 1
    assert ordinal == 18592
    vectors = out / "vectors.txt"
    vectors.write_text("".join(rows), encoding="ascii", newline="\n")
    env = os.environ.copy()
    env["PATH"] = str(CAD / "lib") + ";" + str(CAD / "bin") + ";" + env["PATH"]
    runs = {}

    def run(name, command, positive=True, marker=None):
        log = out / (name + ".log")
        with log.open("wb") as stream:
            result = subprocess.run(list(map(str, command)), cwd=out, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=45)
        text = log.read_text(encoding="utf-8", errors="replace")
        runs[name] = {"exit": result.returncode, "expected_success": positive,
                      "log_sha": sha(log), "command": list(map(str, command))}
        print(name, result.returncode, text[-700:], flush=True)
        if ((result.returncode == 0) != positive or
                marker is not None and marker not in text):
            raise RuntimeError("Unexpected behavior " + name)

    try:
        source = SCOPE / "control_snapshot_selector.sv"
        bench = SCOPE / "tb_control_snapshot_selector.sv"
        run("compile", [CAD / "bin/iverilog.exe", "-g2012", "-s",
                       "tb_control_snapshot_selector", "-o", out / "positive.vvp",
                       source, bench])
        run("positive", [CAD / "bin/vvp.exe", out / "positive.vvp",
                         "+VECTORS=" + str(vectors)],
            marker="PASS deep snapshot selector cases=18592")
        text = source.read_text(encoding="utf-8")
        faults = [
            ("wrong_wrap", "higher_mask[k]<=request_mask[k]&&(k>=request_rr);",
             "higher_mask[k]<=request_mask[k]&&(k<request_rr);",
             "snapshot roundrobin oracle"),
            ("wrong_second", "second_index<=higher_pair[10]?higher_pair[4:0]",
             "second_index<=higher_pair[10]?higher_pair[9:5]",
             "snapshot roundrobin oracle"),
            ("broken_epoch", "result_epoch<=request_epoch;",
             "result_epoch<=request_epoch^32'd1;", "id and epoch aligned frozen"),
        ]
        for name, before, after, reason in faults:
            assert text.count(before) == 1
            mutant = out / (name + ".sv")
            mutant.write_text(text.replace(before, after, 1), encoding="utf-8", newline="\n")
            run(name + "_compile", [CAD / "bin/iverilog.exe", "-g2012", "-s",
                "tb_control_snapshot_selector", "-o", out / (name + ".vvp"), mutant, bench])
            run(name + "_run", [CAD / "bin/vvp.exe", out / (name + ".vvp"),
                "+VECTORS=" + str(vectors)], positive=False, marker=reason)
        empty = out / "empty.txt"
        empty.write_text("", encoding="ascii")
        short = out / "short.txt"
        short.write_text(rows[0], encoding="ascii")
        for name, path in [("empty", empty), ("short", short)]:
            run(name, [CAD / "bin/vvp.exe", out / "positive.vvp", "+VECTORS=" + str(path)],
                positive=False, marker="vacuous or truncatedcount")
        record = {"date": "2026-10-05", "snapshot_cases": 18592, "rr_origins": 32,
                  "latency": "E_to_E+2", "minimum_II_cycles": 4,
                  "passed": True, "source_sha": sha(source), "bench_sha": sha(bench),
                  "vectors_sha": sha(vectors), "runs": runs, "Gowin_or_STA": False,
                  "integrated_parser_equivalence_claimed": False,
                  "production_modified": False}
        (out / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return 0
    finally:
        (out / "run_status.json").write_text(json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())