"""Independent prefix-selection guards; machine-field adapters are explicit.

Normalized binary maps preserve X/Z. They are never translated to fabricated
integers or used to claim startup initialization passed.
"""
from consume_capture import require


BOUNDARY_FIELDS = {"startup_edges", "main_first_absolute_cycle", "main_first_time_ps",
                   "main_first_time_ns", "main_first_relative_cycle"}


def binary_map(values, widths):
    require(type(values) is dict and set(values) == set(widths), "STARTUP_BINARY_FIELDS")
    for name, width in widths.items():
        value = values[name]
        require(type(value) is str and len(value) == width
                and all(bit in "01xXzZ" for bit in value), "STARTUP_BINARY_WIDTH_OR_VALUE")
    return all(all(bit in "01" for bit in value) for value in values.values())


def validate_selection(prefix, first_audio, first_inputs, raw_boundary,
                       audio_widths, input_widths, first_main_time_ns):
    require(type(raw_boundary) is dict and set(raw_boundary) == BOUNDARY_FIELDS,
            "STARTUP_BOUNDARY_RAW_FIELDS")
    require(all(type(v) is int and v >= 0 for v in raw_boundary.values()),
            "STARTUP_BOUNDARY_RAW_TYPE")
    count = raw_boundary["startup_edges"]
    require(count == len(prefix) and 1 <= count + 1 <= 64
            and raw_boundary["main_first_absolute_cycle"] == count + 1
            and raw_boundary["main_first_relative_cycle"] == 1, "STARTUP_CYCLE_BOUNDARY")
    first_ps = raw_boundary["main_first_time_ps"]
    require(raw_boundary["main_first_time_ns"] == (first_ps + 500) // 1000
            and first_main_time_ns == raw_boundary["main_first_time_ns"], "STARTUP_MAIN_TIME_MAPPING")
    require(binary_map(first_audio, audio_widths) and binary_map(first_inputs, input_widths)
            and first_audio["rst_n"] == "0", "MAIN_FIRST_NOT_ALL_KNOWN_RESET_LOW")
    unknown_edges = 0
    for index, record in enumerate(prefix, 1):
        require(set(record) == {"absolute_cycle", "time_ps", "audio", "inputs"}
                and type(record["absolute_cycle"]) is int and record["absolute_cycle"] == index
                and type(record["time_ps"]) is int and record["time_ps"] >= 0,
                "STARTUP_ABSOLUTE_SEQUENCE")
        require(record["time_ps"] == first_ps - (count + 1 - index) * 25000,
                "STARTUP_25000PS_SPACING")
        audio_known = binary_map(record["audio"], audio_widths)
        inputs_known = binary_map(record["inputs"], input_widths)
        require(not (audio_known and inputs_known and record["audio"]["rst_n"] == "0"),
                "MAIN_NOT_FIRST_ELIGIBLE_EDGE")
        require(not (record["audio"]["rst_n"] == "1"
                     and record["inputs"]["event_valid"] == "1"
                     and record["inputs"]["event_ready"] == "1"), "PERFORMANCE_ACCEPT_BEFORE_MAIN")
        unknown_edges += int(not (audio_known and inputs_known))
    return {"startup_edges": count, "main_first_absolute_cycle": count + 1,
            "main_first_time_ps": first_ps, "main_first_time_ns": first_main_time_ns,
            "prefix_edges_with_unknown": unknown_edges, "selection": "FIRST_KNOWN_RESET_LOW_WITHIN_64",
            "absolute_cycle_mapping": "absolute_cycle=relative_cycle+startup_edges",
            "startup_unknown": True, "startup_signoff": "UNKNOWN_NOT_VALIDATED",
            "analog_latency": "UNKNOWN_NOT_MEASURED", "board_release_allowed": False}
