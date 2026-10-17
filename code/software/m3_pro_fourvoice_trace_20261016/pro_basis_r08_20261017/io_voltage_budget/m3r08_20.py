"""Offline interval margins from explicitly sourced values. No wiring approval."""
from decimal import Decimal, InvalidOperation
import importlib.util
from pathlib import Path
import re
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_IO_BUDGET_REQUEST_V1", "IO_BUDGET_SCHEMA")
    c.need(request["origin"] in ("SYNTHETIC", "REAL_CANDIDATE"), "IO_BUDGET_ORIGIN")
    c.need(not request.get("approved") and not request.get("board_release_allowed"), "NO_ELECTRICAL_SELF_APPROVAL")
    driver, sink = request["driver"], request["sink"]
    c.need(driver["direction"] == "OUTPUT" and sink["direction"] == "INPUT", "DIRECTION_MISMATCH")
    c.need(request["fpga_endpoint"] in ("driver", "sink"), "FPGA_ENDPOINT_REQUIRED")
    c.need(request["common_ground"] is not False, "NO_COMMON_GROUND")
    sources, links, unknown = {}, [], []
    for entry in request["evidence"]:
        c.need(entry["id"] not in sources, "DUPLICATE_EVIDENCE_ID")
        _, ident = c.checked_file(entry["file"])
        c.need(entry["kind"] in ("OFFICIAL_DOCUMENT", "ACTUAL_MEASUREMENT", "SYNTHETIC"), "VOLTAGE_EVIDENCE_KIND")
        sources[entry["id"]] = {**entry, "verified_file": ident}

    def value(container, key):
        record = container.get(key)
        if record is None or record.get("value") is None:
            unknown.append(key)
            return None
        c.need(record.get("unit") == "V" and record.get("evidence_id") in sources and
               type(record.get("page")) is int and record["page"] >= 1 and
               type(record.get("quote")) is str and record["quote"].strip(), "VALUE_SOURCE_PAGE_QUOTE_REQUIRED")
        try:
            v = Decimal(str(record["value"]))
            tokens = [Decimal(t) for t in re.findall(r"[-+]?\d+(?:\.\d+)?", record["quote"])]
        except InvalidOperation as error:
            raise c.CheckError("VOLTAGE_NUMBER") from error
        c.need(v.is_finite() and v >= 0 and v in tokens, "VALUE_NOT_IN_QUOTE_OR_RANGE")
        source = sources[record["evidence_id"]]
        if request["origin"] == "REAL_CANDIDATE" and source["kind"] == "SYNTHETIC":
            unknown.append("SYNTHETIC_SOURCE_FOR_REAL:" + key)
        links.append({"field": key, **record, "source_file": source["verified_file"], "quote_truth_verified": False})
        return v

    voh, vol, peak = (value(driver, k) for k in ("voh_min", "vol_max", "signal_peak_max"))
    vih, vil, absolute = (value(sink, k) for k in ("vih_min", "vil_max", "abs_input_max"))
    bank = request["bank"]
    measured_min, measured_max, allowed_min, allowed_max = (value(bank, k) for k in
        ("vccio_measured_min", "vccio_measured_max", "vccio_allowed_min", "vccio_allowed_max"))
    fpga = request[request["fpga_endpoint"]]
    if not request["bank_id"] or not request["observed_bank_id"] or not fpga.get("bank_id"):
        unknown.append("BANK_ID_OR_PIN_MAPPING")
    else:
        c.need(request["bank_id"] == request["observed_bank_id"] == fpga["bank_id"], "BANK_ID_MISMATCH")
    if request["common_ground"] is None:
        unknown.append("COMMON_GROUND_EVIDENCE")
    if request["level_shifter"] is not False:
        unknown.append("POST_SHIFTER_PROFILE_AND_SUPPLY")
    if (request["level_shifter"] is False and request["fpga_endpoint"] == "sink" and
            sink.get("five_v_tolerant") is False and peak is not None and peak >= Decimal("5")):
        raise c.CheckError("FIVE_V_DIRECT_TO_NON_TOLERANT_FPGA")
    margins = {}
    if not unknown:
        c.need(measured_min <= measured_max and allowed_min <= allowed_max, "VCCIO_RANGE_ORDER")
        margins = {"high": str(voh - vih), "low": str(vil - vol), "absolute_input": str(absolute - peak),
                   "supply_low": str(measured_min - allowed_min), "supply_high": str(allowed_max - measured_max)}
        c.need(all(Decimal(v) >= 0 for v in margins.values()), "NEGATIVE_VOLTAGE_MARGIN")
    if request["origin"] == "REAL_CANDIDATE":
        unknown.append("SAME_BOARD_BANK_MEASUREMENT_AND_OFFICIAL_VALUES_NOT_HUMAN_SIGNED")
    report = {"origin": request["origin"], "interface_id": request["interface_id"], "bank_id": request["bank_id"],
              "source_links": links, "minimum_margins_V": margins,
              "minimum_margin_V": str(min(Decimal(v) for v in margins.values())) if margins else None,
              "unknown": unknown, "safe_to_wire": None, "measurement_or_device_actions": 0}
    return c.result("M3_R08_IO_VOLTAGE_BUDGET_V1", "PENDING_UNKNOWN" if unknown else "ACCEPT",
                    report=report, artifacts={"io_voltage_budget.json": report})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
