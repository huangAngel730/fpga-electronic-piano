"""Generate small complete hand-authored pin-projection traces."""
import argparse
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projection_check import CAPABILITIES, CONTRACT, ORIGIN, SCHEMA, SOURCE_SHA256


def meta():
    return {"tag": "META", "schema": SCHEMA, "contract": CONTRACT,
            "origin": ORIGIN, "source_sha256": SOURCE_SHA256,
            "capabilities": CAPABILITIES,
            "capture_phase": "PRE_AND_POST_NBA_EXPLICIT"}


class Builder:
    """Separate fixture calendar used only to write deterministic examples."""

    def __init__(self):
        self.cycle = 0
        self.request_window = False
        self.hold = None
        self.request_active = False
        self.current_id = 0
        self.pending = None
        self.held = (0, 0)
        self.handshakes = self.commits = self.frames = 0
        self.edges = []

    def add(self, *, rst=1, frame=0, dispatched=0, valid=0, result_id=0,
            left=0, right=0, clipped=0):
        self.cycle += 1
        pre = self.pending[:2] if self.pending else self.held
        raw = int(bool(rst and dispatched and self.request_window and not frame
                       and self.hold is None))
        qualified = int(bool(raw and result_id == self.current_id))
        handshake = int(bool(qualified and valid))
        commit = int(bool(rst and not frame and self.hold is not None
                          and self.request_active and self.pending is None
                          and self.hold[0] == self.current_id))
        committed = self.hold if commit else (0, 0, 0, 0)
        edge = {
            "tag": "EDGE", "cycle": self.cycle, "rst_n": rst,
            "frame_tick": frame, "adapter_dispatched": dispatched,
            "current_id": self.current_id, "result_valid": valid,
            "result_id": result_id, "result_left": left, "result_right": right,
            "result_clipped": clipped, "raw_result_credit": raw,
            "qualified_result_ready": qualified,
            "true_result_handshake": handshake, "commit_pulse": commit,
            "committed_id": committed[0], "committed_left": committed[1],
            "committed_right": committed[2], "committed_clip": committed[3],
            "pre_pending_valid": int(self.pending is not None),
            "pre_play_left": pre[0], "pre_play_right": pre[1],
            "post_pending_valid": 0, "post_play_left": 0, "post_play_right": 0,
            "frame_tx_valid": int(bool(rst and frame)),
            "frame_tx_left": pre[0] if rst and frame else 0,
            "frame_tx_right": pre[1] if rst and frame else 0,
        }
        if not rst:
            self.request_window = False
            self.hold = None
            self.request_active = False
            self.current_id = 0
            self.pending = None
            self.held = (0, 0)
            self.handshakes = self.commits = self.frames = 0
        elif frame:
            self.frames += 1
            self.request_window = True
            self.hold = None
            self.current_id = (self.current_id + 1) & 0xffff_ffff
            self.request_active = True
            if self.pending:
                self.held = self.pending[:2]
                self.pending = None
        else:
            if commit:
                self.pending = (self.hold[1], self.hold[2], self.hold[3])
                self.hold = None
                self.request_active = False
                self.commits += 1
            if handshake:
                self.request_window = False
                self.hold = (result_id, left, right, clipped)
                self.handshakes += 1
        post = self.pending[:2] if self.pending else self.held
        edge["post_pending_valid"] = int(self.pending is not None)
        edge["post_play_left"], edge["post_play_right"] = post
        self.edges.append(edge)
        return edge

    def trace(self):
        return [meta(), *self.edges,
                {"tag": "END", "cycles": len(self.edges),
                 "result_handshakes": self.handshakes, "commits": self.commits,
                 "frames": self.frames}]


def complete_trace():
    b = Builder()
    b.add(rst=0)
    b.add(rst=1)
    b.add(frame=1)
    b.add(dispatched=0)
    b.add(dispatched=1, valid=1, result_id=99, left=700, right=-700, clipped=1)
    b.add(dispatched=1, valid=1, result_id=1, left=111, right=-222)
    b.add(dispatched=1)
    b.add(dispatched=1)
    b.add(frame=1, dispatched=1)
    b.add(dispatched=0)
    b.add(dispatched=1, valid=1, result_id=2, left=333, right=-444, clipped=1)
    b.add(dispatched=1)
    b.add(dispatched=1)
    b.add(frame=1, dispatched=1, valid=1, result_id=2,
          left=999, right=999, clipped=1)
    b.add(dispatched=0)
    b.add(dispatched=1, valid=1, result_id=3, left=-555, right=666)
    b.add(dispatched=1)
    b.add(dispatched=1)
    return b.trace()


def reset_trace():
    b = Builder()
    b.add(rst=0)
    b.add(rst=1, frame=1)
    b.add(rst=1, dispatched=0)
    b.add(rst=1, dispatched=1, valid=1, result_id=1,
          left=0x7fffff, right=-0x800000, clipped=1)
    b.add(rst=1, dispatched=1)
    b.add(rst=0, dispatched=1, valid=1, result_id=1,
          left=123, right=456, clipped=1)
    b.add(rst=1)
    return b.trace()


def write_trace(path, records):
    raw = "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                  for item in records)
    path.write_text(raw, encoding="utf-8", newline="\n")


def generate(output):
    if output.exists():
        raise ValueError("VECTORS_REFUSE_OVERWRITE")
    output.mkdir(parents=True)
    positive = {"directed_projection": complete_trace(), "reset_boundary": reset_trace()}
    base = positive["directed_projection"]
    negative = {}

    wrong_index = next(index for index, item in enumerate(base)
                       if item.get("result_id") == 99)
    commit_b_index = next(index for index, item in enumerate(base)
                          if item.get("commit_pulse") == 1
                          and item.get("committed_left") == 333)
    frame_b_index = next(index for index, item in enumerate(base)
                         if item.get("frame_tick") == 1
                         and item.get("pre_play_left") == 333)

    wrong_ready = copy.deepcopy(base)
    wrong_ready[wrong_index]["qualified_result_ready"] = 1
    wrong_ready[wrong_index]["true_result_handshake"] = 1
    negative["wrong_id_credit_ready"] = (wrong_ready, "QUALIFIED_READY_ID")

    early_play = copy.deepcopy(base)
    early_play[commit_b_index]["pre_play_left"] = 333
    early_play[commit_b_index]["pre_play_right"] = -444
    negative["pending_visible_before_commit"] = (early_play, "PLAY_PRE_EDGE")

    stale_post = copy.deepcopy(base)
    stale_post[commit_b_index]["post_play_left"] = 111
    stale_post[commit_b_index]["post_play_right"] = -222
    negative["pending_hidden_after_commit"] = (stale_post, "PLAY_POST_EDGE")

    wrong_tx = copy.deepcopy(base)
    wrong_tx[frame_b_index]["frame_tx_left"] = 111
    wrong_tx[frame_b_index]["frame_tx_right"] = -222
    negative["frame_sends_old_held"] = (wrong_tx, "FRAME_TX_PRE_PLAY")

    frame_accept = copy.deepcopy(base)
    frame_accept[frame_b_index]["qualified_result_ready"] = 1
    frame_accept[frame_b_index]["true_result_handshake"] = 1
    negative["frame_accepts_old_result"] = (frame_accept, "FRAME_OLD_RESULT_REJECT")

    manifest = {"positives": {}, "negatives": {}}
    for name, records in positive.items():
        filename = "positive_" + name + ".jsonl"
        write_trace(output / filename, records)
        manifest["positives"][name] = {"file": filename}
    for name, (records, diagnostic) in negative.items():
        filename = "negative_" + name + ".jsonl"
        write_trace(output / filename, records)
        manifest["negatives"][name] = {"file": filename, "diagnostic": diagnostic}
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generate(args.output)
        return 0
    except (OSError, ValueError) as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
