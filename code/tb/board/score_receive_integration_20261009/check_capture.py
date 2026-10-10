"""Only committed original protocol responses/public boundary facts, no RAM taps."""
from pathlib import Path
import json,re,struct
from vectors import crc

def check(path,oracle,negative=False):
    lines=Path(path).read_text(encoding='utf-8').splitlines()
    if not lines or lines[0]!='META exact_score_uart_fulltop nominalPLL DVIstub':raise ValueError('META')
    expected=oracle['cases'];cases=[];rx={};tx={};pub={};end=None;stop=False
    for i,line in enumerate(lines[1:]):
        if end is not None or stop:raise ValueError('record after terminal')
        bits=line.split();tag=bits[0]
        if tag=='CASE':
            if len(bits)!=3:raise ValueError('CASEshape')
            cases.append((int(bits[1]),bits[2]))
        elif tag in ('RX','TX'):
            if len(bits)!=3 or not re.fullmatch(r'(?:[0-9a-f]{2})+',bits[2]):raise ValueError('wire hex')
            idx=int(bits[1]);mapping=rx if tag=='RX' else tx
            if idx in mapping:raise ValueError('duplicate wire record')
            mapping[idx]=bytes.fromhex(bits[2])
        elif tag=='PUBLIC':
            if len(bits)!=6:raise ValueError('PUBLICshape')
            idx=int(bits[1])
            if idx in pub:raise ValueError('duplicatePUBLIC')
            pub[idx]=list(map(int,bits[2:]))
        elif tag=='END':
            if len(bits)!=8:raise ValueError('ENDshape')
            end=list(map(int,bits[1:]))
        elif tag=='NEGATIVE_STOP':
            if not negative or bits!=['NEGATIVE_STOP','first_serial_reply']:raise ValueError('unexpectedboundednegative')
            stop=True
        else:raise ValueError('unknownrecord '+tag)
    indices=[c['id'] for c in expected if c['op']=='S']
    wanted=indices[:1] if negative else indices
    if set(tx)!=set(wanted):raise ValueError('exactTXcoverage')
    for idx in wanted:
        raw=tx[idx]
        if len(raw)<14 or raw[:2]!=b'\xa5\x5a' or int.from_bytes(raw[-2:],'little')!=crc(raw[2:-2]):raise ValueError('wireCRC/frame')
        target=bytes.fromhex(expected[idx]['response'])
        if raw!=target:
            observed_command=raw[12] if len(raw)>12 else None
            raise ValueError(f'RESPONSE_BYTES_COMMAND_METADATA_OR_EVENT case{idx} echoedcmd{observed_command}')
    if negative:raise ValueError('negative unexpectedly equals golden')
    if end is None or stop or cases!=[(c['id'],c['op']) for c in expected]:raise ValueError('incompletepositive')
    if set(rx)!=set(indices) or set(pub)!=set(indices):raise ValueError('RX/PUBLICcoverage')
    for idx in indices:
        c=expected[idx]
        if rx[idx]!=bytes.fromhex(c['request']):raise ValueError('actualrequest differs')
        pulses=0 if idx==12 else 1 if idx>=4 else 0
        if pub[idx]!=[c['committed_valid'],c['committed_count'],c['score_id'],pulses]:raise ValueError('PUBLIC_IDENTITY_COMMIT_COUNT')
    if end[4]!=12 or end[5]!=sum(len(v) for v in rx.values()) or end[6]!=sum(len(v) for v in tx.values()):raise ValueError('END wire counts')
    if end[0]<600000 or end[1]<200000 or end[2]<800 or end[3]<100:raise ValueError('END audio/video coverage')
    return {'passed':True,'short_scope':'actual13case/fulltop2MIDI_note serialupload + read, nominalPLL/DVIstub; no full512orhardware','cases':len(cases),'responses':len(tx),'read_events':3,'END_audio_pixel_frame_nonzero_packets_RX_TX':end,'atomic_commit_one_before_reset':True}
