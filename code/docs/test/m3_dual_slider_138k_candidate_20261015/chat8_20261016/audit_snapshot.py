"""Read-only provenance inventory; never launches HDL/EDA or edits old inputs."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[5]
BASE = "code/docs/test/m3_dual_slider_138k_candidate_20261015/"
BBASE = "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/"
ZIP_PATH = "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R06_XSAFE_7ms_ModelSim输入_20261016.zip"
INPUTS = [
    "code/docs/M3_40MHz音频端点准备_72561ce_M2限定复核_2026-10-16.md",
    "code/docs/M2_夜间R05功能与音频端点_限定复核_2026-10-16.md",
    "code/docs/M2_R06同版闭包与双滑块受控接入清单_2026-10-16.md",
    "code/rtl/input/m3_dual_slider_138k_candidate_20261015/dual_slider_candidate.sv",
    "code/rtl/common/visual_control_bridge.sv",
    "code/rtl/common/visual_event_bridge.sv",
    "code/rtl/common/visual_mailbox_cdc.sv",
    "code/rtl/common/reset_sync.sv",
    "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/tb_slider_audio_coexist.sv",
    BASE + "night_20261016/RESULT.md",
    BASE + "night_20261016/RESUME_R01/RESULT.md",
    BASE + "night_20261016/RESUME_R01/TRACE_FACTS.json",
    BBASE + "delivery_night_r03/B_DIRECTED_STA_CANDIDATE_20261016.zip",
    ZIP_PATH,
]
MEMBERS = {
    "inputs/sources/audio_visual_display_probe.sv": (1, 136),
    "inputs/sources/m2_fourvoice_timbre_delay_board_top.sv": (670, 690),
    "inputs/sources/video_scan_timing.sv": (1, 45),
    "inputs/constraints/audio_visual_hold055.sdc": (295, 330),
}
EXPECTED = {
    ZIP_PATH: "4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483",
    BBASE + "delivery_night_r03/B_DIRECTED_STA_CANDIDATE_20261016.zip":
        "59f40000f25bccc492199e4a0f6e843e4a7ccf68ddaeab5823c756b888d44ce3",
    INPUTS[3]: "a8116d04f7fa70ba4500c4819e3ffb939fcc7096acef9bb7f87004e1e648868f",
    INPUTS[8]: "92b8a1873fef2b6d296596c0ba6bfb92ad99ae090869e17b3b3eed958c47ed7b",
}


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    before = {name: identity((ROOT / name).read_bytes()) for name in INPUTS}
    members = {}
    with zipfile.ZipFile(ROOT / ZIP_PATH) as archive:
        for name, (start, end) in MEMBERS.items():
            raw = archive.read(name)
            lines = raw.decode("utf-8-sig").splitlines()
            members[name] = {
                **identity(raw),
                "lines": {str(i): line for i, line in enumerate(lines, 1)
                          if start <= i <= end},
            }
    after = {name: identity((ROOT / name).read_bytes()) for name in INPUTS}
    mismatches = [name for name, sha in EXPECTED.items()
                  if before[name]["sha256"] != sha]
    passed = before == after and not mismatches
    print(json.dumps({
        "scope": "L0 inventory only; not HDL/CDC/timing validation",
        "python": sys.executable,
        "python_identity": identity(Path(sys.executable).read_bytes()),
        "script_identity": identity(Path(__file__).read_bytes()),
        "before": before, "after": after,
        "zip_members": members, "expected_identity_mismatches": mismatches,
        "unchanged": before == after, "inventory_pass": passed,
        "new_hdl_eda_device_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
