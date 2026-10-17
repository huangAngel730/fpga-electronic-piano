"""Fixed PinDecoder adapter; protocol is PT8211 LSBJ16, not I2S delay."""
import importlib.util
from pathlib import Path
from types import ModuleType

DECODER_SHA = 'da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb'
PROTOCOL = 'PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT'


def shared():
    p = Path(__file__).with_name('r08c_common.py')
    s = importlib.util.spec_from_file_location('r08c13_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def load_pin_decoder(source_path, c):
    """Compile only the fixed source bytes; never consult a .pyc loader."""
    raw = source_path.read_bytes()
    c.need(c.sha(raw) == DECODER_SHA, 'DEPENDENCY_SHA', path=str(source_path))
    module = ModuleType('r08c13_frozen_pin_decoder')
    module.__file__ = str(source_path)
    module.__package__ = ''
    module.__cached__ = None
    code = compile(raw, str(source_path), 'exec', dont_inherit=True, optimize=0)
    exec(code, module.__dict__)
    c.need(c.sha(source_path.read_bytes()) == DECODER_SHA, 'DEPENDENCY_CHANGED', path=str(source_path))
    return module


def analyze(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_SERIAL_ALIGNMENT_INPUT_V1', 'SERIAL_SCHEMA')
    if data.get('protocol') != PROTOCOL:
        return c.report('PENDING_UNSUPPORTED_SERIAL_PROTOCOL', requested=data.get('protocol'))
    if data.get('sample_phase') != 'SYS_POSEDGE_PRE_NBA' or data.get('first_phase_known') is not True:
        return c.report('UNKNOWN_SERIAL_FIRST_PHASE')
    c.need(data.get('clock_hz') == 40000000, 'SERIAL_CLOCK')
    c.need(data.get('quantization') == 'SATURATE((PCM24+128)//256)', 'SERIAL_QUANTIZATION')
    root = Path(__file__).resolve().parents[5]
    decoder_path = root / 'code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py'
    decoder = load_pin_decoder(decoder_path, c)
    ledger = {}
    for request in data.get('accepted_requests', []):
        key = request['epoch'], request['req_id']
        c.need(key not in ledger, 'DUPLICATE_REQUEST')
        ledger[key] = {'request_cycle': request['A_cycle']}
    pins = decoder.PinDecoder(ledger)
    source_index, prior = {}, None
    unknown = []
    for input_line, row in enumerate(data['rows'], 1):
        row = c.public_view(row)
        fields = ('cycle', 'epoch', 'source_line', 'time_ps', 'rst_n', 'frame_tick', 'bclk', 'ws', 'din')
        if any(type(row.get(k)) is not int for k in fields):
            return c.report('UNKNOWN_SERIAL_PIN_OR_TIME', input_line=input_line, original=row)
        if prior is not None:
            c.need(row['cycle'] == prior['cycle'] + 1 and row['time_ps'] - prior['time_ps'] == 25000, 'SERIAL_TIME_GAP')
        c.need(all(row[k] in (0, 1) for k in ('rst_n', 'frame_tick', 'bclk', 'ws', 'din')), 'SERIAL_PIN_RANGE')
        tx_valid = row.get('tx_sample_valid')
        if tx_valid is None or (isinstance(tx_valid, str) and any(k in tx_valid.lower() for k in ('x', 'z'))):
            return c.report('PENDING_TX_SAMPLE', original=row)
        c.need(type(tx_valid) is int and tx_valid in (0, 1), 'TX_SAMPLE_VALID_RANGE', original=row)
        if row['rst_n'] and row['frame_tick'] and tx_valid != 1:
            return c.report('PENDING_TX_SAMPLE', original=row)
        source_index[row['cycle']] = {'input_line': input_line, 'source_line': row['source_line'], 'epoch': row['epoch']}
        try:
            pins.observe(row)
        except (ValueError, KeyError) as error:
            return c.report('REJECT', reason='PIN_' + str(error),
                            first_difference={'boundary': source_index[row['cycle']],
                                              'first_bit_cycle': pins.bits[0][0] if pins.bits else None,
                                              'channel': 'left' if pins.word_ws else 'right'},
                            complete_frames=pins.frames, decoder_sha256=DECODER_SHA)
        if row.get('tx_sample_valid') == 1:
            required = ('tx_metadata_valid', 'tx_req_id_valid', 'tx_startup_zero', 'tx_hold', 'tx_left', 'tx_right')
            if any(row.get(k) is None or isinstance(row.get(k), str) for k in required):
                return c.report('PENDING_TX_METADATA', source=source_index[row['cycle']])
            c.need(all(type(row[k]) is int and row[k] in (0, 1) for k in required[:4]), 'TX_METADATA_FLAG_RANGE')
            if row['tx_metadata_valid'] != 1:
                return c.report('PENDING_TX_METADATA', source=source_index[row['cycle']])
            c.need(row['rst_n'] == row['frame_tick'] == 1, 'TX_NOT_ACTIVE_FRAME')
            rid = row.get('tx_req_id')
            if row['tx_startup_zero']:
                c.need(rid is None and row['tx_req_id_valid'] == 0 and not row['tx_hold']
                       and row['tx_left'] == row['tx_right'] == 0, 'STARTUP_ID_OR_PCM')
            else:
                c.need(type(rid) is int and row['tx_req_id_valid'] == 1, 'TX_ID_VALIDITY')
                if (row['epoch'], rid) not in ledger:
                    return c.report('PENDING_ACCEPTED_REQUEST_SOURCE', source=source_index[row['cycle']])
            pins.current_sample = {'cycle': row['cycle'], 'epoch': row['epoch'], 'id': rid,
                                   'left': row['tx_left'], 'right': row['tx_right'], 'frame': row['tx_frame_id']}
        prior = row
    if pins.partial_resets:
        unknown.append('RESET_TRUNCATED_HALF_OR_FRAME')
    if pins.bits or pins.right_half:
        unknown.append('SERIAL_TAIL_INCOMPLETE')
    if not pins.frames:
        unknown.append('NO_COMPLETE_SERIAL_FRAME')
    status = 'UNKNOWN_SERIAL_PARTIAL' if unknown else 'SERIAL_COMPLETE_FRAMES_MATCH_SYNTHETIC_ONLY'
    if data.get('origin') != 'SYNTHETIC' and not unknown:
        status = 'PENDING_REAL_SERIAL_ADMISSION'
    return c.report(status, unknown=unknown, complete_frames=pins.frames, half_frames=pins.halves,
                    source_index=source_index, request_ledger=[{'epoch': k[0], 'req_id': k[1], **v} for k, v in ledger.items()],
                    decoder=c.identity(decoder_path), serial_channel_order='WS_LOW_RIGHT_HIGH_LEFT',
                    identity_source='EXPLICIT_TX_SIDECAR_AND_ACCEPT_LEDGER_NOT_SEMANTIC_AUTHENTICATION',
                    sample_rate_source='OBSERVED_PIN_TIMESTAMPS_ONLY_NO_WAV_RATE', original_rows=data['rows'])


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
