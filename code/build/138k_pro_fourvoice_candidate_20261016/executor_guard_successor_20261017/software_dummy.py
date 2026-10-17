"""Only software fixtures for the isolated M2 owned-process executor."""

from pathlib import Path
import subprocess
import sys
import time


def main():
    mode = sys.argv[1]
    folder = Path.cwd()
    if mode == "normal":
        print("DUMMY_NORMAL_STDOUT", flush=True)
        print("DUMMY_NORMAL_STDERR", file=sys.stderr, flush=True)
        return 0
    if mode == "error7":
        print("DUMMY_EXIT7_STDOUT", flush=True)
        print("DUMMY_EXIT7_STDERR", file=sys.stderr, flush=True)
        return 7
    if mode == "grandchild":
        (folder / "grandchild.ready").write_text("owned fixture\n", encoding="ascii")
        print("DUMMY_GRANDCHILD_READY", flush=True)
        time.sleep(4)
        (folder / "ESCAPED_GRANDCHILD.txt").write_text("FAIL\n", encoding="ascii")
        time.sleep(20)
    elif mode == "child":
        subprocess.Popen([sys.executable, "-I", "-S", "-B", __file__, "grandchild"])
        (folder / "child.ready").write_text("owned fixture\n", encoding="ascii")
        print("DUMMY_CHILD_READY", flush=True)
        time.sleep(4)
        (folder / "ESCAPED_CHILD.txt").write_text("FAIL\n", encoding="ascii")
        time.sleep(20)
    elif mode in {"timeout_tree", "parent_exit_tree"}:
        subprocess.Popen([sys.executable, "-I", "-S", "-B", __file__, "child"])
        deadline = time.monotonic() + 2
        while not (folder / "grandchild.ready").exists():
            if time.monotonic() >= deadline:
                print("DUMMY_DESCENDANT_START_FAILED", file=sys.stderr, flush=True)
                return 9
            time.sleep(0.01)
        print("DUMMY_PARENT_DESCENDANTS_READY", flush=True)
        if mode == "parent_exit_tree":
            return 0
        time.sleep(20)
    elif mode == "overflow":
        print("DUMMY_OVERFLOW_START", flush=True)
        for _ in range(128):
            sys.stdout.write("x" * 8192)
            sys.stdout.flush()
            time.sleep(0.001)
        time.sleep(20)
    else:
        raise ValueError("Unknown software fixture mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
