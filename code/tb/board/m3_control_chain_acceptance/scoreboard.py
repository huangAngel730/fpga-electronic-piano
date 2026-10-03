"""Independent accepted-FIFO state and transaction binding; M1 integer FCW oracle."""
from collections import defaultdict, deque
import importlib.util
from pathlib import Path


def unpack(value):
    return ((value >> 61) & 7, (value >> 57) & 15, (value >> 53) & 15,
            (value >> 18) & 255, (value >> 6) & 4095)


def expected_midi(src, status, data):
    channel, kind = status & 15, status >> 4
    value = src << 57 | channel << 53
    if kind in (8, 9):
        velocity = data[1] * 8 + (data[1] >> 4)
        value |= (int(kind == 8 or velocity == 0) << 61)
        return value | data[0] << 46 | velocity << 36
    if kind == 12:
        return value | 4 << 61 | 5 << 18 | data[0] << 6
    if kind == 14:
        bend = ((data[1] * 128 + data[0] - 8192) >> 2) & 4095
        return value | 3 << 61 | bend << 6
    if kind == 11 and data[0] in (1, 64):
        ctrl = 1 if data[0] == 1 else 6
        return value | 4 << 61 | ctrl << 18 | (data[1] * 32 + (data[1] >> 2)) << 6
    raise ValueError(f"unsupported stimulus {src=} {status=} {data=}")


def check_capture(path: Path, model_path: Path):
    spec = importlib.util.spec_from_file_location("accepted_m1_model", model_path)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    voices = [model.PitchModVoice() for _ in range(4)]
    state = [[0, 0, 2] for _ in range(256)]
    fifo, requests, pending = deque(), {}, {}
    discrete = defaultdict(deque)
    controls = defaultdict(set)
    latest_controls = {}
    decode = {}
    identities, programs, types = set(), set(), set()
    counts = defaultdict(int)
    observed = set()
    last_rate = {}
    cadence = []
    finished = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        f = line.split()
        if not f:
            raise ValueError(f"empty record at {lineno}")
        tag = f[0]
        try:
            if tag == "R":
                # Reset can flush in-flight transactions, but not hide missing input.
                if any(discrete.values()):
                    raise AssertionError("reset with unconsumed discrete stimulus")
                fifo.clear(); requests.clear(); pending.clear(); observed.clear()
                state = [[0, 0, 2] for _ in range(256)]
                decode.clear(); last_rate.clear()
                latest_controls.clear()
                for voice in voices:
                    voice.reset()
                counts["reset_cycles"] += 1
            elif tag == "B":
                src, byte = int(f[2]), int(f[3], 16)
                status, data = decode.get(src, (0, []))
                if byte >= 248:
                    continue
                if byte & 128:
                    decode[src] = (byte, [])
                    continue
                data.append(byte)
                length = 1 if status >> 4 == 12 else 2
                if len(data) == length:
                    event = expected_midi(src, status, data)
                    kind, _, ch, ctrl, _ = unpack(event)
                    if kind == 3 or (kind == 4 and ctrl == 1):
                        controls[(src, ch, ctrl)].add(event)
                        latest_controls[(src, ch, ctrl)] = unpack(event)[4]
                    else:
                        discrete[src].append(event)
                    decode[src] = (status, [])
            elif tag == "P":
                cycle, event = int(f[1]), int(f[2], 16)
                kind, src, ch, ctrl, _ = unpack(event)
                # Fixture producer also supplies range controls for all identities.
                is_fixture = bool(int(f[3]))
                if kind in (0, 1) or (kind == 4 and ctrl in (5, 6)):
                    assert discrete[src] and discrete[src].popleft() == event, "per-source discrete order/raw payload"
                    counts["discrete"] += 1
                elif not is_fixture:
                    assert event in controls[(src, ch, ctrl)], "raw MIDI continuous mapping"
                    if src in last_rate:
                        assert cycle - last_rate[src] >= 50000, "real 50MHz/1kHz source limit"
                    last_rate[src] = cycle
                if kind == 4 and ctrl == 5:
                    programs.add((event >> 6) & 4095)
                types.add((kind, ctrl))
                fifo.append(event)
                counts["push"] += 1
            elif tag == "F":
                event = int(f[2], 16)
                assert fifo and fifo.popleft() == event, "public FIFO ordering/data"
                kind, src, ch, ctrl, value = unpack(event)
                identity = src * 16 + ch
                if kind == 3 and ctrl == 0:
                    state[identity][0] = value - 4096 if value & 2048 else value
                elif kind == 4 and ctrl == 1:
                    state[identity][1] = value
                elif kind == 4 and ctrl == 4 and value <= 24:
                    state[identity][2] = value
                # Program/Note/CC64 intentionally never modify this state.
                counts["accepted_events"] += 1
            elif tag == "D":
                for (src, ch, ctrl), value in latest_controls.items():
                    actual = state[src*16+ch][int(ctrl == 1)]
                    assert actual & 4095 == value, "coalesced final MIDI value delivered"
                counts["final_midi_controls"] = len(latest_controls)
            elif tag == "N":
                for i, voice in enumerate(voices):
                    if int(f[2], 16) >> i & 1:
                        voice.reset()
                counts["note_on_pulses"] += 1
            elif tag == "Q":
                cycle, rid = int(f[1]), int(f[2])
                meta = [int(s, 16) for s in f[3:7]]
                bases = int(f[7], 16)
                mask, sources, channels, _ = meta
                params = []
                for i in range(4):
                    identity = ((sources >> (4*i)) & 15)*16 + ((channels >> (4*i)) & 15)
                    params.append(state[identity].copy() if mask >> i & 1 else [0, 0, 2])
                    if mask >> i & 1:
                        identities.add(identity)
                assert rid not in requests, "unique request id"
                requests[rid] = (cycle, meta, bases, params)
                cadence.append((cycle, rid))
                counts["requests"] += 1
            elif tag == "S":
                cycle, rid = int(f[1]), int(f[2])
                qcycle, meta, bases, params = requests[rid]
                assert cycle == qcycle + 4 and [int(s, 16) for s in f[3:7]] == meta, "snapshot metadata/E+4"
                bends, mods, ranges = [int(s, 16) for s in f[7:10]]
                for i, (bend, mod, rng) in enumerate(params):
                    assert bends >> (12*i) & 4095 == bend & 4095, "accepted-only/write-through pitch"
                    assert mods >> (12*i) & 4095 == mod, "accepted-only modulation"
                    assert ranges >> (5*i) & 31 == rng, "range isolation/default"
                counts["snapshots"] += 1
            elif tag == "C":
                cycle, rid, bases = int(f[1]), int(f[2]), int(f[3], 16)
                _, meta, frozen, params = requests.pop(rid)
                assert bases == frozen, "FCW base frozen at Q not live"
                result = 0
                for i, (bend, mod, rng) in enumerate(params):
                    if meta[0] >> i & 1:
                        result |= voices[i].step(bases >> (32*i) & 0xffffffff, bend, rng, mod) << (32*i)
                        if bend or mod:
                            counts["nonzero_control_lanes"] += 1
                pending[rid] = (cycle + 7, meta, result)
                counts["computations"] += 1
            elif tag == "X":
                counts["cancelled"] += len(pending)
                pending.clear(); observed.clear()
            elif tag in ("O", "T"):
                cycle, rid = int(f[1]), int(f[2])
                assert rid in pending, "result tag does not belong to an accepted, uncancelled request"
                due, meta, result = pending[rid]
                assert [int(s, 16) for s in f[3:7]] == meta, "result id/source/channel/generation/occupied"
                assert int(f[7], 16) == result, "per-sample independent FCW oracle"
                if tag == "O":
                    assert cycle == due and rid not in observed, "exact result time/once-only"
                    observed.add(rid)
                else:
                    assert cycle > due and rid in observed, "consume only published result"
                    pending.pop(rid); observed.remove(rid)
                    counts["consumed"] += 1
            elif tag == "K":
                start, end = int(f[1]), int(f[2])
                group = [c for c, _ in cadence if start < c <= end]
                gaps = [b-a for a, b in zip(group, group[1:])]
                assert len(gaps) >= 575 and set(gaps) == {1041, 1042}, "48k request cadence"
                counts["cadenced_requests"] = len(group)
            elif tag == "END":
                totals = list(map(int, f[1:]))
                assert counts["consumed"] == totals[0] and totals[1] >= 32 and all(x > 0 for x in totals[2:]), "RTL boundary coverage"
                assert not fifo and not pending and not requests and not any(discrete.values()), "nonempty final drain"
                finished = True
                counts.update(result_stall_cycles=totals[1], full_pop_push=totals[2], read_stall_cycles=totals[3], write_through=totals[4])
            else:
                raise ValueError(f"unknown record {tag}")
        except (AssertionError, KeyError, ValueError, IndexError) as exc:
            raise AssertionError(f"capture line {lineno}: {line}: {exc}") from exc
    assert finished and counts["consumed"] >= 512 and len(identities) == 256 and counts["nonzero_control_lanes"] >= 128
    assert programs == set(range(128)), "all raw program ids"
    assert {(0, 0), (1, 0), (3, 0), (4, 1), (4, 5), (4, 6)} <= types
    counts["identities"] = len(identities)
    counts["raw_program_ids"] = len(programs)
    return dict(counts)
