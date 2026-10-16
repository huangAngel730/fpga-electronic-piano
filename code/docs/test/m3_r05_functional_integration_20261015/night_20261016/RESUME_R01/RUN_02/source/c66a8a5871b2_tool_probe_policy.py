"""Tool-specific preflight; vlib help is NOT a runtime version banner."""
import re

from common import Refusal
from receipt_check import BAD


MODEL_2020 = re.compile(r"Model(?:Sim|\s+Technology)[^\n]*\bSE-64\b[^\n]*\b2020\.4\b", re.I)


def probe_arguments(name):
    if name not in ("vlib", "vlog", "vsim"):
        raise Refusal("PROBE_TOOL", name)
    return ["-help"] if name == "vlib" else ["-version"]


def probe_valid(name, call, raw):
    if (type(call.get("exit_code")) is not int or call["exit_code"] != 0
            or call.get("timeout") is not False or call.get("error")
            or call.get("log_limit_exceeded")
            or call.get("process_created") is not True
            or call.get("argv", [])[1:] != probe_arguments(name)):
        return False
    text = raw.decode("utf-8", errors="replace")
    if BAD.search(text):
        return False
    if name == "vlib":
        return bool(re.search(r"(?im)^\s*Usage:\s*vlib\s+-help\s*$", text))
    return bool(MODEL_2020.search(text))


def pin_inventory(current, prior, metadata):
    # Exact recorded 2020.4 installation; no alternative version or DLL set.
    if current != prior:
        raise Refusal("TOOL_PIN_DRIFT", "installation differs from original 2020.4 probe")
    if metadata.decode("utf-8-sig").strip().strip('"') != "2020.4":
        raise Refusal("INSTALLATION_VERSION", "metadata is not 2020.4")
    return {
        "vlib_version_basis": "PINNED_EXE_AND_SAME_INSTALLATION_METADATA",
        "vlib_runtime_version": "NOT_EXPORTED_BY_HELP",
        "runtime_version_required_from": ["vlog", "vsim"],
    }
