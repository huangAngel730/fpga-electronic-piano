"""Fail-closed corruption tests against complete actual captures, not fake PASS."""
from pathlib import Path


def run_checks(out, oracle):
    normal = (out/"normal/capture.txt").read_text(encoding="utf-8").splitlines()
    overflow = (out/"overflow/capture.txt").read_text(encoding="utf-8").splitlines()
    cases = {
        "empty": ([], "normal"),
        "missing_end": (normal[:-1], "normal"),
        "zero_events": ([r for r in normal if not r.startswith(("U ", "A ", "R ", "V "))], "normal"),
        "zero_pcm": ([r for r in normal if not r.startswith("P ")], "normal"),
        "missing_frame": ([r for r in normal if not r.startswith("C ")], "normal"),
        "missing_scan_lines": ([r for r in normal if not r.startswith("L ")], "normal"),
        "missing_publish": ([r for r in normal if not r.startswith("F ")], "normal"),
        "missing_video_event": ([r for r in normal if not r.startswith("V ")], "normal"),
        "missing_audio_event": ([r for r in normal if not r.startswith("A ")], "normal"),
        "missing_fixture": ([r for r in normal if not r.startswith("B ")], "normal"),
        "missing_drop_evidence": ([r for r in overflow if not r.startswith("D ")], "overflow"),
    }

    def change(kind, field, value, source=normal):
        rows = list(source)
        index = next(n for n, row in enumerate(rows) if row.startswith(kind+" "))
        fields = rows[index].split()
        fields[field] = value
        rows[index] = " ".join(fields)
        return rows

    cases.update({
        "wrong_scan_hash": (change("L", 7, "00000000"), "normal"),
        "short_scan_line": (change("L", 4, "799"), "normal"),
        "short_frame": (change("C", 3, "10000"), "normal"),
        "unknown_pcm": (change("P", 4, "x"), "normal"),
        "wrong_pcm": (change("P", 5, "1234567"), "normal"),
        "missing_pcm_handshake": (change("P", 2, "0"), "normal"),
        "wrong_publish": (change("F", 3, "80"), "normal"),
        "repeated_video_event": (normal[:-1]+[next(r for r in normal if r.startswith("V "))]+normal[-1:], "normal"),
    })
    rejected = {}
    folder = out/"checker_corruptions"
    folder.mkdir()
    for name, (rows, scenario) in cases.items():
        path = folder/(name+".txt")
        path.write_text("\n".join(rows)+("\n" if rows else ""), encoding="utf-8")
        try:
            oracle.check_capture(path, scenario)
        except (ValueError, IndexError, KeyError) as error:
            rejected[name] = str(error)
        else:
            raise RuntimeError("CHECKER_FALSE_PASS "+name)
    print(f"PASS {len(rejected)} corrupted-capture refusals", flush=True)
    return {"passed": True, "capture_rejections": rejected}
