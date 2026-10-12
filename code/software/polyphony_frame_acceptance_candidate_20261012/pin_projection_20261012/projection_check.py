"""Strict software projection from the isolated adapter pins to frame semantics."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


SCHEMA = "PIN_PROJECTION_V1"
CONTRACT = "REAL_PUBLIC_PIN_PROJECTION_CANDIDATE_20261013"
ORIGIN = "HANDWRITTEN_SOFTWARE_FIXTURE"
SOURCE_SHA256 = {
    "premixed_frame_adapter.sv":
        "d7952a5f986eb8b609cbe657907e418cfe751c6492d6e49469b5e37c390bb56c",
    "pcm_result_hold.sv":
        "7656fd0089efd140de784352d1e7809169240e6a09263c8ce9428298b424d52f",
    "pcm_frame_buffer.sv":
        "f8bc454a2e627809c2f9f9029c1e5128acf2fd543d7fcc2d3d83b50685f40997",
    "b2d_event_audio.sv":
        "5f1a0d2e89fcb6f2d6ff97964e96953c2e9247e828536b521a43327d80c0a0ce",
    "b2d_event_audio_clipped.sv":
        "3fd292ab7a3748f10054ec5eb26d44f20b83880073a220aa6b4ddc2f1a98427f",
}
CAPABILITIES = {
    "raw_result_credit": "OBSERVER_ONLY_DERIVED_NOT_ADAPTER_PORT",
    "qualified_result_ready": "PUBLIC_CANDIDATE_RESULT_READY",
    "true_result_handshake": "PUBLIC_VALID_AND_QUALIFIED_READY",
    "play_pin": "PUBLIC_COMBINATIONAL_PENDING_ELSE_HELD",
    "frame_tx_sample": "PRE_NBA_PLAY_PIN_AT_FRAME_EDGE",
    "result_epoch": "UNMAPPED_SOFTWARE_ONLY",
    "result_sink_ready": "UNMAPPED_SOFTWARE_ONLY",
    "pcm_sink_ready": "UNMAPPED_SOFTWARE_ONLY",
    "clipped": "B2D_EVENT_AUDIO_CLIPPED_CANDIDATE_ONLY",
}
META_KEYS = {"tag", "schema", "contract", "origin", "source_sha256",
             "capabilities", "capture_phase"}
EDGE_KEYS = {
    "tag", "cycle", "rst_n", "frame_tick", "adapter_dispatched",
    "current_id", "result_valid", "result_id", "result_left",
    "result_right", "result_clipped", "raw_result_credit",
    "qualified_result_ready", "true_result_handshake", "commit_pulse",
    "committed_id", "committed_left", "committed_right", "committed_clip",
    "pre_pending_valid", "pre_play_left", "pre_play_right",
    "post_pending_valid", "post_play_left", "post_play_right",
    "frame_tx_valid", "frame_tx_left", "frame_tx_right",
}
END_KEYS = {"tag", "cycles", "result_handshakes", "commits", "frames"}
BITS = {
    "rst_n", "frame_tick", "adapter_dispatched", "result_valid",
    "result_clipped", "raw_result_credit", "qualified_result_ready",
    "true_result_handshake", "commit_pulse", "committed_clip",
    "pre_pending_valid", "post_pending_valid", "frame_tx_valid",
}
UINT32 = {"current_id", "result_id", "committed_id"}
PCM24 = {"result_left", "result_right", "committed_left", "committed_right",
         "pre_play_left", "pre_play_right", "post_play_left", "post_play_right",
         "frame_tx_left", "frame_tx_right"}


class ProjectionError(ValueError):
    """A stable diagnostic for one projection contract violation."""


def reject(code, cycle=None):
    suffix = "" if cycle is None else ":cycle=" + str(cycle)
    raise ProjectionError(code + suffix)


def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            reject("JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def strict_int(value, name, cycle, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        reject("FIELD_NOT_INTEGER:" + name, cycle)
    if not low <= value <= high:
        reject("FIELD_RANGE:" + name, cycle)


def load_trace(path):
    records = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            reject("EMPTY_RECORD", number)
        try:
            item = json.loads(raw, object_pairs_hook=object_pairs,
                              parse_constant=lambda value: reject("JSON_NONFINITE:" + value))
        except ProjectionError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ProjectionError("JSON_SYNTAX:line=" + str(number)) from error
        if not isinstance(item, dict):
            reject("RECORD_NOT_OBJECT", number)
        records.append(item)
    if len(records) < 3:
        reject("TRACE_TOO_SHORT")
    return records


class PinProjection:
    """Independent state calendar for the three read-only RTL blocks."""

    def __init__(self):
        self.request_window = False
        self.hold_valid = False
        self.hold_id = 0
        self.hold_left = 0
        self.hold_right = 0
        self.hold_clip = 0
        self.request_active = False
        self.current_id = 0
        self.pending_valid = False
        self.pending_left = 0
        self.pending_right = 0
        self.held_left = 0
        self.held_right = 0
        self.handshakes = 0
        self.commits = 0
        self.frames = 0

    def play(self):
        if self.pending_valid:
            return self.pending_left, self.pending_right
        return self.held_left, self.held_right

    def check_edge(self, edge, expected_cycle):
        if set(edge) != EDGE_KEYS:
            reject("EDGE_FIELDS_EXACT", expected_cycle)
        cycle = edge.get("cycle")
        strict_int(cycle, "cycle", expected_cycle, 1, 0x7fff_ffff)
        if cycle != expected_cycle:
            reject("CYCLE_CONTIGUOUS", expected_cycle)
        for name in BITS:
            strict_int(edge[name], name, cycle, 0, 1)
        for name in UINT32:
            strict_int(edge[name], name, cycle, 0, 0xffff_ffff)
        for name in PCM24:
            strict_int(edge[name], name, cycle, -0x800000, 0x7fffff)

        if edge["current_id"] != self.current_id:
            reject("CURRENT_ID_PUBLIC_PIN", cycle)
        pre_left, pre_right = self.play()
        if edge["pre_pending_valid"] != int(self.pending_valid):
            reject("PENDING_PRE_EDGE", cycle)
        if (edge["pre_play_left"], edge["pre_play_right"]) != (pre_left, pre_right):
            reject("PLAY_PRE_EDGE", cycle)

        rst = bool(edge["rst_n"])
        frame = bool(edge["frame_tick"])
        dispatched = bool(edge["adapter_dispatched"])
        raw_credit = bool(rst and dispatched and self.request_window
                          and not frame and not self.hold_valid)
        if edge["raw_result_credit"] != int(raw_credit):
            reject("RAW_RESULT_CREDIT", cycle)
        qualified = raw_credit and edge["result_id"] == self.current_id
        if edge["qualified_result_ready"] != int(qualified):
            if raw_credit and edge["result_id"] != self.current_id:
                reject("QUALIFIED_READY_ID", cycle)
            if frame:
                reject("FRAME_OLD_RESULT_REJECT", cycle)
            reject("QUALIFIED_READY_RAW", cycle)
        handshake = qualified and bool(edge["result_valid"])
        if edge["true_result_handshake"] != int(handshake):
            reject("TRUE_RESULT_HANDSHAKE", cycle)

        commit = bool(rst and not frame and self.hold_valid
                      and self.request_active and not self.pending_valid
                      and self.hold_id == self.current_id)
        if edge["commit_pulse"] != int(commit):
            reject("COMMIT_PUBLIC_PIN", cycle)
        if commit:
            expected_commit = (self.hold_id, self.hold_left, self.hold_right,
                               self.hold_clip)
            observed_commit = (edge["committed_id"], edge["committed_left"],
                               edge["committed_right"], edge["committed_clip"])
            if observed_commit != expected_commit:
                reject("COMMITTED_PAYLOAD_IDENTITY", cycle)

        frame_tx = bool(rst and frame)
        if edge["frame_tx_valid"] != int(frame_tx):
            reject("FRAME_TX_VALID", cycle)
        expected_tx = (pre_left, pre_right) if frame_tx else (0, 0)
        if (edge["frame_tx_left"], edge["frame_tx_right"]) != expected_tx:
            reject("FRAME_TX_PRE_PLAY", cycle)

        if not rst:
            self.__init__()
        elif frame:
            self.frames += 1
            self.request_window = True
            self.hold_valid = False
            self.hold_clip = 0
            self.current_id = (self.current_id + 1) & 0xffff_ffff
            self.request_active = True
            if self.pending_valid:
                self.held_left = self.pending_left
                self.held_right = self.pending_right
                self.pending_valid = False
        else:
            if commit:
                self.pending_valid = True
                self.pending_left = self.hold_left
                self.pending_right = self.hold_right
                self.request_active = False
                self.hold_valid = False
                self.hold_clip = 0
                self.commits += 1
            if handshake:
                self.request_window = False
                self.hold_valid = True
                self.hold_id = edge["result_id"]
                self.hold_left = edge["result_left"]
                self.hold_right = edge["result_right"]
                self.hold_clip = edge["result_clipped"]
                self.handshakes += 1

        post_left, post_right = self.play()
        if edge["post_pending_valid"] != int(self.pending_valid):
            reject("PENDING_POST_EDGE", cycle)
        if (edge["post_play_left"], edge["post_play_right"]) != (post_left, post_right):
            reject("PLAY_POST_EDGE", cycle)


def check(path):
    records = load_trace(path)
    meta, end = records[0], records[-1]
    if set(meta) != META_KEYS or meta.get("tag") != "META":
        reject("META_FIELDS_EXACT")
    if (meta["schema"], meta["contract"], meta["origin"],
            meta["capture_phase"]) != (SCHEMA, CONTRACT, ORIGIN, "PRE_AND_POST_NBA_EXPLICIT"):
        reject("META_IDENTITY")
    if meta["source_sha256"] != SOURCE_SHA256:
        reject("META_SOURCE_SHA256")
    if meta["capabilities"] != CAPABILITIES:
        reject("META_CAPABILITIES")
    if set(end) != END_KEYS or end.get("tag") != "END":
        reject("END_FIELDS_EXACT")
    model = PinProjection()
    for cycle, edge in enumerate(records[1:-1], 1):
        model.check_edge(edge, cycle)
    expected_end = {
        "tag": "END", "cycles": len(records) - 2,
        "result_handshakes": model.handshakes, "commits": model.commits,
        "frames": model.frames,
    }
    if end != expected_end:
        reject("END_LEDGER")
    return expected_end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.trace)
        print(json.dumps({"status": "PIN_PROJECTION_PASS", **result}, sort_keys=True))
        return 0
    except (OSError, ProjectionError, ValueError) as error:
        print("PIN_PROJECTION_REJECT:" + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
