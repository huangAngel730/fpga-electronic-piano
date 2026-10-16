"""Generate a small new R06-profile SOFTWARE reference; never a DUT capture."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from oracle import Reference, DEPENDENCIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    ref = Reference()
    events, samples, stimuli = [], [], []
    ref.config_accept(16, True, 1, 32767, 16384, 0)
    stimuli.append(dict(kind='config', cycle=16, enable=True, delay=1,
                        dry=32767, wet=16384, feedback=0))
    # This calendar is an explicit arithmetic profile, not the R06 MIDI TB's
    # accepted-event or router pipeline calendar. Requests start fully settled.
    schedule = {
        0: [('note_on', 60, 1023, 0)],
        16: [('program', 0, 0, 1), ('note_on', 63, 896, 0)],
        32: [('note_on', 67, 768, 0), ('note_on', 70, 640, 0)],
        128: [('note_on', 72, 900, 0)],
        160: [('note_on', 63, 400, 0)],
        176: [('program', 0, 0, 0)],
        192: [('note_off', 67, 0, 0)],
        208: [('note_on', 67, 800, 0)],
        224: [('note_on', 70, 0, 0)],
    }
    tick = 128
    for sample in range(256):
        for index, (kind, note, velocity, program) in enumerate(schedule.get(sample, [])):
            cycle = tick - 64 + index * 16
            event = dict(kind=kind, cycle=cycle, source=1, channel=0, note=note,
                         velocity=velocity, program=program)
            stimuli.append(event)
            events.append(ref.event(**event))
        accepted = sample != 99
        publish = sample not in (99, 100)
        stimuli.append(dict(kind='sample', advance_cycle=tick, request_id=sample,
                            effect_accepted=accepted, publish=publish))
        samples.append(ref.sample(tick, sample, accepted, publish))
        tick += (833, 833, 834)[sample % 3]
    # A separate reset epoch proves phase/program/history are cleared without
    # pretending that this software calendar is a board reset measurement.
    ref.reset(tick)
    stimuli.append(dict(kind='reset', cycle=tick))
    ref.config_accept(tick + 16, True, 1, 32767, 16384, 0)
    stimuli.append(dict(kind='config', cycle=tick + 16, enable=True, delay=1,
                        dry=32767, wet=16384, feedback=0))
    for rid in range(8):
        cycle = tick + 128 + rid * 834
        stimuli.append(dict(kind='sample', advance_cycle=cycle, request_id=rid,
                            effect_accepted=True, publish=True))
        samples.append(ref.sample(cycle, rid))
    stimulus = dict(schema='M1_SETTLED_DSP_STIMULUS_V1', source_kind='SYNTHETIC_ONLY',
                    clock_hz=40000000, sample_rate_hz=48000,
                    profile='independent applied-event, lane-tick and effect-accept calendar',
                    rows=stimuli)
    for name, value in [('STIMULUS.json', stimulus), ('EXPECTED_PCM.json', samples),
                        ('EVENT_DECISIONS.json', events)]:
        with (out / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    columns = ['epoch', 'request_id', 'advance_cycle', 'snapshot_cycle',
               'postprocess_accept_cycle', 'effect_accepted', 'expected_publish',
               'mixed_left', 'mixed_right', 'left', 'right', 'upstream_clip']
    for lane in range(4):
        columns += [f'lane{lane}_{field}' for field in ('fcw', 'phase_before', 'phase_after',
                    'timbre', 'generation', 'wave16', 'env_q15', 'voice_pcm24')]
    with (out / 'EXPECTED_PCM.csv').open('x', encoding='ascii', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        for row in samples:
            flat = {name: row[name] for name in columns if name in row}
            for lane in row['lanes']:
                flat.update({f'lane{lane["lane"]}_{name}': lane[name]
                             for name in ('fcw', 'phase_before', 'phase_after', 'timbre',
                                          'generation', 'wave16', 'env_q15', 'voice_pcm24')})
            writer.writerow(flat)
    report = dict(schema='M1_R06_SYNTHETIC_PCM_VECTOR_RECEIPT_V1',
                  result='SOFTWARE_REFERENCE_GENERATED', actual_dut_result='PENDING_REAL_CAPTURE',
                  samples=len(samples), epochs=2, events=len(events),
                  four_occupied_rows=sum(all(l['identity'] is not None for l in r['lanes']) for r in samples),
                  four_nonzero_contribution_rows=sum(all(l['voice_pcm24'] != 0 for l in r['lanes']) for r in samples),
                  effect_inputs_not_published=[100], dsp_advance_without_effect_accept=[99],
                  post_reset_rows_silent=all(r['left'] == r['right'] == 0 for r in samples[-8:]),
                  request_id_may_repeat_only_in_new_epoch=True,
                  dependencies=DEPENDENCIES,
                  files={p.name: dict(bytes=p.stat().st_size,
                         sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in out.iterdir() if p.is_file()})
    with (out / 'VECTOR_RECEIPT.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('result', 'actual_dut_result', 'samples',
                     'four_occupied_rows', 'four_nonzero_contribution_rows', 'post_reset_rows_silent')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
