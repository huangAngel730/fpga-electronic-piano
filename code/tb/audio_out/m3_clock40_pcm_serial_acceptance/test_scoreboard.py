"""Fail-closed checks on real positive captures, plus fixed integer oracles."""
from pathlib import Path


def run_checks(out, oracle):
    known = {0: 0, 127: 0, 128: 1, 129: 1, -127: 0, -128: 0,
             -129: -1, -256: -1, 8388607: 32767, 8388479: 32767,
             8388480: 32767, -8388608: -32768, -8388481: -32768,
             -8388480: -32767, 8448: 33, -12544: -49}
    for source, expected in known.items():
        if oracle.pcm16(source) != expected:
            raise ValueError("INTEGER_ORACLE_SELFTEST")
    for source in [-8388609, 8388608]:
        try:
            oracle.pcm16(source)
        except ValueError:
            pass
        else:
            raise ValueError("PCM_RANGE_FALSE_PASS")
    normal = (out / "normal/capture.txt").read_text(encoding="utf-8").splitlines()
    diag = (out / "diagnostic/capture.txt").read_text(encoding="utf-8").splitlines()

    def replace_first(lines, prefix, transform):
        copy = list(lines)
        position = next(i for i, line in enumerate(copy) if line.startswith(prefix))
        copy[position] = " ".join(transform(copy[position].split()))
        return copy

    def number(row, field, delta=1):
        row[field] = str(int(row[field])+delta)
        return row

    variants = {
        "empty": ([], "normal"),
        "missing_end": (normal[:-1], "normal"),
        "zero_serial": ([s for s in normal if not s.startswith("S ")], "normal"),
        "zero_handshakes": ([s for s in normal if not s.startswith("H ")], "normal"),
        "missing_adoption": ([s for s in normal if not s.startswith("A ")], "normal"),
        "missing_counter": ([s for s in normal if not s.startswith("V ")], "normal"),
        "wrong_id": (replace_first(diag, "H ", lambda r: number(r, 2)), "diagnostic"),
        "wrong_sample": (replace_first(diag, "H ", lambda r: number(r, 4)), "diagnostic"),
        "slot_31": (replace_first(diag, "S ", lambda r: number(r, 4, -1)), "diagnostic"),
        "counter": (replace_first(diag, "V ", lambda r: number(r, 5)), "diagnostic"),
        "unknown_bit": (replace_first(diag, "S ", lambda r: r[:5]+["xxxxxxxx"]+r[6:]), "diagnostic"),
        "missing_four_scene": ([s for s in normal if " FOUR " not in s], "normal"),
        "missing_release_states": ([s for s in normal if not s.startswith("STATE ")], "normal"),
        "missing_gap": ([s for s in diag if not s.startswith("G ")], "diagnostic"),
        "duplicate_slot": (replace_first(diag, "S ", lambda r: number(r, 2)), "diagnostic"),
    }
    folder = out / "checker_negative"
    folder.mkdir()
    rejected = {}
    for name, (lines, scenario) in variants.items():
        path = folder / (name+".txt")
        path.write_text("\n".join(lines)+"\n", encoding="utf-8")
        try:
            oracle.check_capture(path, scenario)
        except (ValueError, IndexError, KeyError) as error:
            rejected[name] = str(error)
        else:
            raise ValueError("CHECKER_FALSE_PASS "+name)
    print(f"SELFTEST PASS integer={len(known)+2} corruptions={len(rejected)}", flush=True)
    return {"passed": True, "integer_checks": len(known)+2, "capture_rejections": rejected}
