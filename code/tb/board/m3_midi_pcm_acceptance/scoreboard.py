"""F capture checker: accepted events, M1 FCW, DDS phase/ROM and PCM integers.

ADSR envelopes and timbre selection are observed from the real bank, not a new
ADSR algorithm. Allocation is asserted by the RTL scenarios, never generated
by this checker as a replacement DUT. Wave addresses use independently summed
adjusted FCWs; gain/mixing/tag checks use the actual bank's result transport.
"""
from __future__ import annotations

from collections import defaultdict, deque
import importlib.util
import math
from pathlib import Path

SCENARIOS = {
    "four_voices", "center512", "held_controls", "steal_old_off", "velocity_zero",
    "release_retrigger", "pedal_tail_controls", "release_controls", "pedal_steal", "program_transport",
    "sample_edge", "fifo_pressure", "accepted_only", "reset_partial", "reset_compute",
    "reset_pending", "recovered",
}


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def check_capture(path: Path, root: Path):
    midi = load_module("existing_midi_mapping", root / "code/tb/board/m3_control_chain_acceptance/scoreboard.py")
    model = load_module("m1_fcw_model", root / "code/model/pitch_mod_model.py")
    voices = [model.PitchModVoice() for _ in range(4)]
    wave = [signed(int(word, 16), 16) for word in
            (root / "code/model/generated/wavetables/piano_band_4x256_8191.mem").read_text(encoding="ascii").split()]
    assert len(wave) == 1024, "wave ROM count"
    states, decode, discrete = {}, {}, defaultdict(deque)
    controls = defaultdict(set)
    fifo, requests, results = deque(), {}, {}
    phases = [0] * 4
    stats = defaultdict(int)
    scenarios, event_types, identities = set(), set(), set()
    last_rate = {}
    latest = {}
    frame_cycle = 0
    last_uart_cycle = -100
    finish = False
    lengths = {"R": 3, "U": 4, "P": 4, "E": 3, "K": 3, "J": 3,
               "N": 3, "Q": 9, "S": 6, "C": 3, "F": 8, "D": 4,
               "H": 7, "M": 6, "T": 3, "END": 10}
    for line_number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        fields = line.split()
        try:
            assert fields and fields[0] in lengths and len(fields) == lengths[fields[0]], "malformed capture record"
            assert not finish, "record after END"
            tag = fields[0]
            cycle = int(fields[1]) if tag != "END" else 0
            if tag == "R":
                # Reset intentionally cancels queued and in-flight work. Global
                # coverage is retained; no claim cancelled frames were committed.
                stats["reset_cancelled_requests"] += len(requests)
                states.clear(); decode.clear(); discrete.clear(); controls.clear()
                fifo.clear(); requests.clear(); results.clear(); latest.clear()
                last_rate.clear(); phases = [0] * 4; frame_cycle = 0; last_uart_cycle = -100
                for voice in voices:
                    voice.reset()
                stats["reset_epochs"] += 1
            elif tag == "U":
                source, byte = int(fields[2]), int(fields[3], 16)
                last_uart_cycle = cycle
                stats["uart_bytes"] += 1
                if frame_cycle and 0 <= cycle - frame_cycle <= 8:
                    stats["uart_completions_at_frame_edge"] += 1
                if byte >= 248:
                    continue
                status, data = decode.get(source, (0, []))
                if byte & 128:
                    decode[source] = (byte, [])
                    continue
                assert status, "data without running status"
                data.append(byte)
                if len(data) == (1 if status >> 4 == 12 else 2):
                    value = midi.expected_midi(source, status, data)
                    kind, _, channel, control, _ = midi.unpack(value)
                    if kind == 3 or kind == 4 and control == 1:
                        controls[source, channel, control].add(value)
                    else:
                        discrete[source].append(value)
                    decode[source] = (status, [])
            elif tag == "P":
                value, synthetic = int(fields[2], 16), int(fields[3])
                kind, source, channel, control, raw = midi.unpack(value)
                if not synthetic:
                    if kind == 3 or kind == 4 and control == 1:
                        assert value in controls[source, channel, control], "pin MIDI continuous mapping"
                        if source in last_rate:
                            assert cycle - last_rate[source] >= 50000, "1kHz aggregate source limit"
                        last_rate[source] = cycle
                    else:
                        assert discrete[source] and discrete[source].popleft() == value, "pin MIDI discrete mapping/order"
                    stats["normal_input_events"] += 1
                else:
                    assert kind == 3 or kind == 4 and control == 5, "unmarked synthetic input"
                    stats["fixture_input_events"] += 1
                if kind == 3 or kind == 4 and control == 1:
                    latest[source, channel, control] = raw
                fifo.append(value)
            elif tag == "E":
                value = int(fields[2], 16)
                assert fifo and fifo.popleft() == value, "public FIFO exact order/payload"
                kind, source, channel, control, raw = midi.unpack(value)
                event_types.add((kind, control))
                state = states.setdefault(source * 16 + channel, [0, 0, 2])
                if kind == 3 and control == 0:
                    state[0] = signed(raw, 12)
                elif kind == 4 and control == 1:
                    state[1] = raw
                stats["accepted_events"] += 1
            elif tag == "K":
                if 0 <= cycle - last_uart_cycle <= 8:
                    stats["uart_completions_at_frame_edge"] += 1
                if frame_cycle:
                    assert cycle - frame_cycle in (1041, 1042), "frame cadence"
                frame_cycle = cycle
                stats["frame_edges"] += 1
            elif tag == "J":
                stats["frame_requests"] += 1
            elif tag == "N":
                mask = int(fields[2], 16)
                for lane in range(4):
                    if mask >> lane & 1:
                        voices[lane].reset()
                stats["note_on_pulses"] += mask.bit_count()
            elif tag == "Q":
                request_id = int(fields[2])
                mask, source_bus, channel_bus, generation, base, notes = map(lambda x: int(x, 16), fields[3:])
                assert request_id not in requests, "unique frame capture id"
                params = []
                for lane in range(4):
                    identity = (source_bus >> (4 * lane) & 15) * 16 + (channel_bus >> (4 * lane) & 15)
                    params.append(states.get(identity, [0, 0, 2]).copy() if mask >> lane & 1 else [0, 0, 2])
                    if mask >> lane & 1:
                        identities.add(identity)
                        # Independently regenerate the semitone constant then
                        # apply the existing integer octave shift convention.
                        note = notes >> (8 * lane) & 255
                        semi = note % 12
                        octave = (note - 60 - semi) // 12
                        semitone = round((1 << 32) * 261.6255653 * math.pow(2, semi / 12) / 48000)
                        expected_base = semitone << octave if octave >= 0 else semitone >> -octave
                        assert base >> (32 * lane) & 0xffffffff == expected_base, "real note to frozen base FCW"
                requests[request_id] = {"cycle": cycle, "mask": mask, "source": source_bus,
                                        "channel": channel_bus, "generation": generation,
                                        "base": base, "params": params}
                stats["bank_captures"] += 1
            elif tag == "S":
                request = requests[int(fields[2])]
                # Capture samples valid before NBA: the E+4 NBA publication is
                # consumed/recorded at the E+5 rising edge, not one cycle late.
                assert cycle == request["cycle"] + 5, "control snapshot E+4 NBA / E+5 acceptance"
                bend, modulation, pitch_range = [int(x, 16) for x in fields[3:]]
                for lane, params in enumerate(request["params"]):
                    assert (bend >> (12 * lane) & 4095) == params[0] & 4095, "accepted-only bend snapshot"
                    assert modulation >> (12 * lane) & 4095 == params[1], "accepted-only modulation snapshot"
                    assert pitch_range >> (5 * lane) & 31 == params[2], "source channel range snapshot"
                stats["control_snapshots"] += 1
            elif tag == "C":
                request = requests[int(fields[2])]
                assert "computed" not in request, "one FCW computation per frame"
                values = []
                for lane, params in enumerate(request["params"]):
                    occupied = request["mask"] >> lane & 1
                    values.append(voices[lane].step(request["base"] >> (32 * lane) & 0xffffffff,
                                                  params[0], params[2], params[1]) if occupied else 0)
                    if occupied and (params[0] or params[1]):
                        stats["nonzero_control_lane_results"] += 1
                request["computed"] = sum(value << (32 * lane) for lane, value in enumerate(values))
            elif tag == "F":
                request = requests[int(fields[2])]
                mask, source_bus, channel_bus, generation, fcw = [int(x, 16) for x in fields[3:]]
                assert (mask, source_bus, channel_bus, generation) == tuple(
                    request[key] for key in ("mask", "source", "channel", "generation")), "FCW generation identity"
                assert fcw == request["computed"], "independent FCW reference"
                stats["fcw_results"] += 1
            elif tag == "D":
                request = requests[int(fields[2])]
                expected = sum(((request["computed"] if request["mask"] >> lane & 1 else request["base"])
                                >> (32 * lane) & 0xffffffff) << (32 * lane) for lane in range(4))
                actual = int(fields[3], 16)
                assert actual == expected, "DDS adjusted FCW bypass"
                for lane in range(4):
                    phases[lane] = (phases[lane] + (expected >> (32 * lane) & 0xffffffff)) & 0xffffffff
                stats["dds_advances"] += 1
            elif tag == "H":
                request_id = int(fields[2])
                mask, waves, envelopes, tables = [int(x, 16) for x in fields[3:]]
                assert mask == requests[request_id]["mask"], "bank result occupancy identity"
                total = 0
                for lane in range(4):
                    value = signed(waves >> (16 * lane) & 65535, 16)
                    gain = envelopes >> (16 * lane) & 65535
                    assert gain <= 32767, "envelope amplitude contract"
                    address = (tables >> (2 * lane) & 3) * 256 + (phases[lane] >> 24)
                    assert value == wave[address], "DDS phase and original V1 ROM sample"
                    if mask >> lane & 1:
                        total += ((value * gain) >> 15) * 256
                total = min(8388607, max(-8388608, total))
                assert request_id not in results, "duplicate bank result"
                results[request_id] = total
            elif tag == "M":
                request_id = int(fields[2])
                left, right = [signed(int(x, 16), 24) for x in fields[3:5]]
                synthetic_phase = int(fields[5])
                assert request_id in results, "PCM committed wrong frame tag"
                assert left == right == results.pop(request_id), "independent Q15 floor PCM mix"
                requests.pop(request_id)
                stats["pcm_commits"] += 1
                stats["fixture_phase_pcm" if synthetic_phase else "normal_pcm"] += 1
                if left:
                    stats["nonzero_pcm"] += 1
            elif tag == "T":
                assert fields[2] in SCENARIOS, "unknown scenario"
                scenarios.add(fields[2])
            elif tag == "END":
                totals = [int(x) for x in fields[1:]]
                assert stats["pcm_commits"] == totals[0] and stats["nonzero_pcm"] == totals[1], "PCM coverage totals"
                assert stats["normal_input_events"] == totals[6] and stats["fixture_input_events"] == totals[7], "input coverage totals"
                assert not fifo and not requests and not results and not any(discrete.values()), "final transport drain"
                for (source, channel, control), raw in latest.items():
                    assert states[source * 16 + channel][int(control == 1)] & 4095 == raw, "final control delivery"
                assert stats["normal_pcm"] >= 512 and stats["nonzero_control_lane_results"] >= 128, "minimum actual PCM/control coverage"
                assert set(SCENARIOS) == scenarios and len(identities) >= 4, "missing required scenario/source/channel"
                assert {(0, 0), (1, 0), (3, 0), (4, 1), (4, 5), (4, 6)} <= event_types, "missing note/pedal/control/program types"
                assert all(value > 0 for value in totals[2:6]), "FIFO/stall/edge/center coverage missing"
                assert stats["uart_completions_at_frame_edge"] > 0, "no actual UART byte near frame edge"
                stats.update(full_pop_push=totals[2], control_stall_cycles=totals[3], sample_edge_events=totals[4],
                             center_bank_comparisons=totals[5], rtl_assertions=totals[8], identities=len(identities))
                finish = True
        except (AssertionError, IndexError, KeyError, ValueError) as error:
            raise AssertionError(f"line {line_number}: {line}: {error}") from error
    assert finish, "missing END capture"
    stats["scenarios"] = sorted(scenarios)
    return dict(stats)
