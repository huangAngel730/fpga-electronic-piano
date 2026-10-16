"""Python-only environment observation inside the unchanged Windows Job."""
import hashlib
import json
import os
import sys


def main():
    if sys.argv[1:] == ["--synthetic-bad-root"]:
        os.environ["IVERILOG_ROOT"] = "SYNTHETIC_WRONG_ROOT_NOT_A_TOOL"
    elif sys.argv[1:]:
        raise SystemExit("PROBE_ARGUMENT_REJECTED")
    raw = json.dumps(dict(os.environ), sort_keys=True, ensure_ascii=True).encode("ascii")
    print(json.dumps({
        "scope": "PYTHON_ENVIRONMENT_ONLY_NOT_RTL", "pid": os.getpid(),
        "PATH": os.environ.get("PATH"),
        "IVERILOG_ROOT": os.environ.get("IVERILOG_ROOT"),
        "COMPUTERNAME": os.environ.get("COMPUTERNAME"),
        "environment_sha256": hashlib.sha256(raw).hexdigest(),
        "environment_item_sha256": {k: hashlib.sha256(v.encode("utf-8")).hexdigest()
                                    for k, v in os.environ.items()},
        "python": sys.executable, "actual_argv": sys.orig_argv,
        "windows_version": list(sys.getwindowsversion()),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
