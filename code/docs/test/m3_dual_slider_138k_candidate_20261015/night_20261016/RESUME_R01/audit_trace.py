"""Read existing negative captures; compare facts with the sealed positive."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    lines = path.read_text(encoding="ascii").splitlines()
    assert lines[0] == "C_PCM_SERIAL_PUBLIC_V1,NEW_MODULE_RTL_FIXTURE,40000000,PRE_NBA,PT8211_LSBJ"
    assert lines[-1] == "END,160024"
    data = [line.split(",") for line in lines[1:-1]]
    assert len(data) == 160024
    assert all(len(r) == 23 and int(r[0]) == i+1 for i, r in enumerate(data))
    return data


def main():
    normal = HERE.parent / "RUN_03/positive/capture.csv"
    baseline = rows(normal)
    output = {"normal_capture_sha256": sha(normal), "normal_rerun": False, "cases": []}
    for mutation in (1, 2, 3, 4):
        folder = HERE / f"RUN_01/negative_{mutation}"
        path = folder / "capture.csv"
        values = rows(path)
        pcm_diffs = []
        pin_diffs = []
        for a, b in zip(baseline, values):
            if a[:20] != b[:20]:
                pcm_diffs.append(int(b[0]))
            if a[20:] != b[20:]:
                pin_diffs.append(int(b[0]))
        commits = sum(r[2] == "1" and r[7] == "1" and r[8] == "1" for r in values)
        missing48 = sum(r[1] == "1" and r[9] == "48" and r[7] == "1" and r[8] == "1" for r in values)
        max_underflow = {str(e): max(int(r[19]) for r in values if int(r[1]) == e) for e in (1, 2)}
        assert pin_diffs
        if mutation == 1:
            assert commits == 189 and missing48 == 0 and max_underflow == {"1": 1, "2": 0}
            assert pcm_diffs
        else:
            assert commits == 190 and max_underflow == {"1": 0, "2": 0}
            assert not pcm_diffs
            assert all(a[20:22] == b[20:22] for a, b in zip(baseline, values))
        result = json.loads((folder / "CHECK.json").read_text())
        assert result["passed"] is False
        output["cases"].append({
            "mutation": mutation, "capture_sha256": sha(path), "rows": len(values),
            "public_pcm_commits": commits, "epoch1_req48_commits": missing48,
            "max_underflow_by_epoch": max_underflow,
            "pcm_public_trace_identical_to_normal": not pcm_diffs,
            "pcm_different_rows": len(pcm_diffs), "pin_different_rows": len(pin_diffs),
            "first_pin_difference_cycle": pin_diffs[0],
            "actual_reject_diagnostic": result["diagnostic"],
            "source_of_fault": "REAL_RTL_TB_RUNTIME_INJECTION_NOT_CAPTURE_EDIT",
        })
    output["passed"] = True
    with (HERE / "TRACE_FACTS.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
