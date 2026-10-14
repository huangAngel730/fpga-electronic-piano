"""Independent frozen-math oracle for the T061 N32-C plan.

The oracle consumes only plan operations plus the frozen Router, ADSR, DDS,
and ROM definitions.  No DUT output is used to choose a slot, advance an
envelope, derive PCM, or decide the clipped flag.

This module deliberately models a *completed public operation*: events are
clocked until the independent router returns idle and a published sample is
clocked through one audio advance.  It is therefore suitable for generating
the plan ledger, not for checking the RTL's exact cycle calendar.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Iterable

from n32c_common import (
    CONTROL_EVENT_SPECS,
    ContractError,
    pack_event,
    records_sha256,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MATH = ROOT / "code" / "software" / "audio_math_acceptance_candidate"
ROUTER = ROOT / "code" / "software" / "polyphony_scaling_candidate"
for dependency in (str(MATH), str(ROUTER)):
    if dependency not in sys.path:
        sys.path.insert(0, dependency)

from dds_model import MASK32, PianoDDS, pitch_mod, signed  # noqa: E402
from envelope_model import Envelope, voice_pcm  # noqa: E402
from b2c_router_model import Router, fields  # noqa: E402


ROM_PATHS = {
    "velocity": ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem",
    "wave": ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem",
    "oct": ROOT / "code/model/generated/pitch_mod/oct_ratio_q16.mem",
    "sub": ROOT / "code/model/generated/pitch_mod/sub_ratio_q16.mem",
    "lfo": ROOT / "code/model/generated/pitch_mod/lfo_sine_q15.mem",
}


def _read_rom(path: Path) -> tuple[int, ...]:
    try:
        return tuple(int(token, 16) for token in path.read_text(
            encoding="utf-8").split())
    except (OSError, ValueError) as exc:
        raise ContractError(f"AUDIO_ROM:{path.as_posix()}") from exc


@dataclass(frozen=True)
class SampleResult:
    """One independently calculated N32 sample publication."""

    result_id: int
    left_pcm: int
    right_pcm: int
    clipped: bool
    lane_pcm: tuple[int, ...]
    contexts: tuple[int, ...]


class FrozenAudioOracle:
    """Input-only Router/ADSR/DDS/ROM reference for N32/R1."""

    def __init__(self, n: int = 32) -> None:
        if n != 32:
            raise ContractError("AUDIO_ORACLE_REQUIRES_N32")
        self.n = n
        self.rom = {name: _read_rom(path) for name, path in ROM_PATHS.items()}
        if tuple(len(self.rom[name]) for name in
                 ("velocity", "wave", "oct", "sub", "lfo")) != (
                     1024, 1024, 50, 1024, 1024):
            raise ContractError("AUDIO_ROM_SHAPE")
        self.env = [Envelope(self.rom["velocity"]) for _ in range(n)]
        self.dds = [PianoDDS() for _ in range(n)]
        self.reset()

    def reset(self) -> None:
        self.router = Router(self.n)
        self.controls: dict[tuple[int, int], tuple[int, int, int]] = {}
        self.lfo = [0] * self.n
        self.committed_contexts = [0] * self.n
        self.sample_advances = 0
        for env, osc in zip(self.env, self.dds):
            env.reset()
            osc.reset()

    def _release_done_mask(self, on: int) -> int:
        mask = 0
        for lane, (slot, env) in enumerate(zip(self.router.slots, self.env)):
            if (slot["occupied"] and slot["releasing"]
                    and env.snapshot()["public_state"] == 0
                    and not (on & (1 << lane))):
                mask |= 1 << lane
        return mask

    def _update_controls(self, event_word: int) -> None:
        event = fields(event_word)
        identity = event["source"], event["channel"]
        bend, modulation, pitch_range = self.controls.get(identity,
                                                           (0, 0, 2))
        if event["type"] == 3 and event["control"] == 0:
            bend = event["value"]
        elif event["type"] == 4 and event["control"] == 1:
            modulation = event["value"]
        elif (event["type"] == 4 and event["control"] == 4
              and event["value"] <= 24):
            pitch_range = event["value"]
        self.controls[identity] = bend, modulation, pitch_range

    def _edge(self, *, event_word: int | None = None,
              frame_fcw: list[int] | None = None) -> None:
        router = self.router
        on, off = router.on, router.off
        tick = frame_fcw is not None
        done = self._release_done_mask(on)
        for lane, (slot, env, osc) in enumerate(zip(router.slots,
                                                    self.env, self.dds)):
            fcw = frame_fcw[lane] if tick else slot["fcw"]
            env.edge(tick=tick, on=bool(on & (1 << lane)),
                     off=bool(off & (1 << lane)),
                     velocity=slot["velocity"])
            osc.edge(fcw, slot["velocity"], tick=tick,
                     note_on=bool(on & (1 << lane)))
            if on & (1 << lane):
                self.lfo[lane] = 0
        router.edge(event=event_word, release_done=done, owner=True)
        if event_word is not None:
            self._update_controls(event_word)

    def _settle_router(self, limit: int = 512) -> None:
        """Clock non-audio edges until public routing is quiescent."""

        for _ in range(limit):
            release_done = self._release_done_mask(self.router.on)
            envelope_setup = any(env.state in (1, 2, 7, 8, 9, 10)
                                 for env in self.env)
            if (not self.router.busy() and not self.router.on
                    and not self.router.off and release_done == 0
                    and not envelope_setup):
                return
            self._edge()
        raise ContractError("AUDIO_ROUTER_SETTLE_LIMIT")

    @staticmethod
    def _event_word(operation: dict[str, Any]) -> int:
        name = operation["op"]
        common = {
            "source": operation["source"],
            "channel": operation["channel"],
        }
        if name == "note_on":
            return pack_event(event_type=0, note=operation["note"],
                              velocity=operation["velocity"],
                              expression=operation["expression"], **common)
        if name == "note_off":
            return pack_event(event_type=1, note=operation["note"], **common)
        if name == "cc64":
            return pack_event(event_type=4, control_id=6,
                              control_value=4095 if operation["down"] else 0,
                              **common)
        if name == "control_event":
            event_type, control_id = CONTROL_EVENT_SPECS[operation["control"]]
            return pack_event(event_type=event_type, control_id=control_id,
                              control_value=operation["value"], **common)
        raise ContractError(f"AUDIO_NOT_EVENT:{name}")

    def event(self, operation: dict[str, Any]) -> None:
        self._settle_router()
        if self.router.busy():
            raise ContractError("AUDIO_EVENT_ROUTER_BUSY")
        self._edge(event_word=self._event_word(operation))
        self._settle_router()

    def sample(self, result_id: int, *, publish: bool = True) -> SampleResult:
        """Advance one audio frame and independently compute N32 PCM."""

        self._settle_router()
        slots = copy.deepcopy(self.router.slots)
        frame_fcw: list[int] = []
        for lane, slot in enumerate(slots):
            control = self.controls.get((slot["source"], slot["channel"]),
                                        (0, 0, 2))
            if slot["occupied"]:
                frame_fcw.append(pitch_mod(
                    slot["fcw"], signed(control[0], 12), control[1],
                    control[2], self.lfo[lane], self.rom["oct"],
                    self.rom["sub"], self.rom["lfo"]))
                self.lfo[lane] = (self.lfo[lane] + 447392) & MASK32
            else:
                frame_fcw.append(slot["fcw"])
        self._edge(frame_fcw=frame_fcw)
        lane_pcm: list[int] = []
        contexts: list[int] = []
        for lane, slot in enumerate(slots):
            osc, env = self.dds[lane], self.env[lane]
            wave = signed(self.rom["wave"][(osc.active_table << 8)
                                           | (osc.phase >> 24)], 16)
            pcm = (voice_pcm(wave, env.snapshot()["envelope"])
                   if slot["occupied"] else 0)
            lane_pcm.append(pcm)
            contexts.append(((pcm & ((1 << 24) - 1)) << 50)
                            | (slot["note"] << 42)
                            | (slot["velocity"] << 32)
                            | slot["fcw"])
        total = sum(lane_pcm)
        mixed = max(-(1 << 23), min((1 << 23) - 1, total))
        result = SampleResult(
            result_id=result_id,
            left_pcm=mixed,
            right_pcm=mixed,
            clipped=mixed != total,
            lane_pcm=tuple(lane_pcm),
            contexts=tuple(contexts),
        )
        self.sample_advances += 1
        if publish:
            self.committed_contexts = contexts
        # A newly-idle releasing envelope becomes visible to the router only
        # after the audio edge.  Settle those public retirements now.
        self._settle_router()
        return result

    def read_context(self, slot: int) -> int:
        if type(slot) is not int or not 0 <= slot < self.n:
            raise ContractError("AUDIO_READ_SLOT")
        return self.committed_contexts[slot]

    def await_release_done(self, slot: int) -> None:
        """Require an already-earned release handshake; never invent ticks."""

        if type(slot) is not int or not 0 <= slot < self.n:
            raise ContractError("AUDIO_RELEASE_SLOT")
        self._settle_router()
        state = self.router.slots[slot]
        if state["occupied"] or state["releasing"]:
            raise ContractError(
                f"RELEASE_AWAIT_WITHOUT_ENOUGH_SAMPLE_TICKS:{slot}:"
                f"{self.env[slot].snapshot()['public_state']}:")

    def apply(self, operation: dict[str, Any]) -> SampleResult | int | None:
        """Apply one high-level plan operation without observing DUT data."""

        name = operation["op"]
        if name in {"note_on", "note_off", "cc64", "control_event"}:
            self.event(operation)
            return None
        if name == "sample":
            if operation["disposition"] == "CANCEL":
                # The plan drives cancel/reset on the following edge before
                # the backend advance.  It must not update audio or statebank.
                return None
            return self.sample(operation["result_id"], publish=True)
        if name == "read":
            return self.read_context(operation["slot"])
        if name == "await_release_done":
            self.await_release_done(operation["slot"])
            return None
        if name == "reset":
            self.reset()
            return None
        if name in {"cancel", "set_result_ready", "tick", "wait_idle"}:
            return None
        raise ContractError(f"AUDIO_UNKNOWN_OP:{name}")


def replay_operations(operations: Iterable[dict[str, Any]]) -> list[Any]:
    """Return independent per-operation results or fail at the first gap."""

    oracle = FrozenAudioOracle()
    return [oracle.apply(operation) for operation in operations]


def bind_expected_records(
        operations: list[dict[str, Any]],
        skeleton: list[dict[str, Any]], *,
        b_review_key: str,
        b_fingerprint: str) -> list[dict[str, Any]]:
    """Fill READ/PCM fields from frozen input-only math.

    The caller remains responsible for binding the exact plan SHA and B source
    manifest.  A plan with an unearned ``await_release_done`` is rejected
    rather than silently inventing sample ticks or using DUT completion data.
    """

    if (not b_review_key or len(b_fingerprint) != 64
            or any(character not in "0123456789abcdef"
                   for character in b_fingerprint)):
        raise ContractError("AUDIO_BINDING_IDENTITY")
    bound = copy.deepcopy(skeleton)
    txns = {row["plan_index"]: row for row in bound[1:-1]
            if row.get("record") == "TXN"}
    reads = {row["plan_index"]: row for row in bound[1:-1]
             if row.get("record") == "READ"}
    oracle = FrozenAudioOracle()
    for index, operation in enumerate(operations):
        value = oracle.apply(operation)
        if operation["op"] == "sample" and operation["disposition"] == "PUBLISH":
            if not isinstance(value, SampleResult) or index not in txns:
                raise ContractError(f"AUDIO_TXN_LEDGER:{index}")
            txns[index].update(
                left_pcm=value.left_pcm,
                right_pcm=value.right_pcm,
                clipped=value.clipped,
                pcm_provenance="INDEPENDENT_FROZEN_MATH",
            )
        elif operation["op"] == "read":
            if type(value) is not int or index not in reads:
                raise ContractError(f"AUDIO_READ_LEDGER:{index}")
            reads[index].update(
                context=value,
                context_provenance="INDEPENDENT_FROZEN_MATH",
            )
    bound[0].update(
        audio_math_status="BOUND_INDEPENDENT_FROZEN_MATH",
        executable_for_rtl_acceptance=True,
        b_review_key=b_review_key,
        b_fingerprint=b_fingerprint,
    )
    bound[-1]["body_sha256"] = records_sha256(bound[:-1])
    return bound
