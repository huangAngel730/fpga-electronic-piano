"""Read-only audit for M2's portable M1TD ModelSim input archive.

The default audit is self-contained. --original-stage additionally proves the
40 reversible path substitutions against M2's exact pre-portable staged tree.
This script does not compile HDL or alter files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip"
EXPECTED_ARCHIVE_SHA = "9af00c82d6b7a7a0a74bd195c823fc117ece1db0ba67fc2eb620b10c09b619f7"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-stage", type=Path)
    args = parser.parse_args()
    if digest(ARCHIVE.read_bytes()) != EXPECTED_ARCHIVE_SHA:
        raise ValueError("ARCHIVE_SHA_MISMATCH")
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip() is not None:
            raise ValueError("ARCHIVE_CRC")
        manifest = json.loads(archive.read("MANIFEST.json"))
        for name, item in manifest["members"].items():
            if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                raise ValueError("UNSAFE_MEMBER:" + name)
            data = archive.read(name)
            if len(data) != item["bytes"] or digest(data) != item["sha256"]:
                raise ValueError("MEMBER_IDENTITY:" + name)
        if len(manifest["members"]) != 91:
            raise ValueError("MEMBER_COUNT")
        prep = json.loads(archive.read("PREPARATION_RECEIPT.json"))
        if prep["status"] != "PORTABLE_MODELSIM_INPUT_PREPARED_NOT_EXECUTED" or prep["simulator_run"]:
            raise ValueError("WRONG_VALIDATION_LEVEL")
        units = [x.strip() for x in archive.read("inputs/compile.f").decode().splitlines() if x.strip()]
        if len(units) != 69 or len(units) != len(set(units)):
            raise ValueError("COMPILE_UNIT_LIST")
        if any("TMDS_PLL_800_600_60.v" in x or "DVI_TX_Top.v" in x for x in units):
            raise ValueError("PRODUCTION_VIDEO_IP_IN_NOMINAL_SIM")
        module_owners = {}
        for name in units:
            path = "inputs/" + name
            source = archive.read(path).decode("utf-8")
            if re.search(r'"[A-Za-z]:/[^"\r\n]+"', source):
                raise ValueError("ABSOLUTE_SOURCE_PATH:" + name)
            for inc in re.findall(r'`include\s+"([^"\r\n]+)"', source):
                if "inputs/include/" + inc not in manifest["members"] and "inputs/" + inc not in manifest["members"]:
                    raise ValueError("INCLUDE_NOT_BUNDLED:" + inc)
            for rom in re.findall(r'"(rom/[^"\r\n]+\.(?:mem|hex))"', source):
                if "inputs/" + rom not in manifest["members"]:
                    raise ValueError("ROM_NOT_BUNDLED:" + rom)
            for module in re.findall(r'^\s*module\s+(\w+)', source, re.M):
                if module in module_owners:
                    raise ValueError("DUPLICATE_MODULE:" + module)
                module_owners[module] = name
        if "tb_m2_m1td_real_chain" not in module_owners or "m2_fourvoice_timbre_delay_board_top" not in module_owners:
            raise ValueError("TOP_OR_TB_MISSING")
        rewrites = prep["path_adaptations"]
        if sum(map(len, rewrites.values())) != 40:
            raise ValueError("PATH_REWRITE_COUNT")
        if args.original_stage is not None:
            stage = args.original_stage.resolve()
            if len([n for n in prep["source_identities"] if not n.startswith("extra/")]) != 84:
                raise ValueError("STAGE_COUNT")
            for relative, item in prep["source_identities"].items():
                if relative.startswith("extra/"):
                    continue
                raw = archive.read(relative)
                for edit in reversed(rewrites.get(relative, [])):
                    old, new = edit["old"].encode(), edit["new"].encode()
                    if raw.count(new) < 1:
                        raise ValueError("MAPPING_LOST:" + relative)
                    raw = raw.replace(new, old, 1)
                original = (stage / relative).read_bytes()
                if raw != original or digest(raw) != item["sha256"] or len(raw) != item["bytes"]:
                    raise ValueError("INVERSE_MISMATCH:" + relative)
        print(json.dumps({"status": "PASS_PORTABLE_INPUT_L0", "archive_sha256": EXPECTED_ARCHIVE_SHA,
                          "members": len(manifest["members"]), "compile_units": len(units),
                          "path_rewrites": 40, "inverse_checked": args.original_stage is not None,
                          "ModelSim_executed": False, "physical_STA": "NOT_RUN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())