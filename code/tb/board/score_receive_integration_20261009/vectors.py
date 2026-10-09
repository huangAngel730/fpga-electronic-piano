"""Short real-UART integration plan with independent exact response oracle."""
from pathlib import Path
import json,struct,hashlib

def crc(data):
    c=0xffff
    for b in data:
        c^=b<<8
        for _ in range(8):c=((c<<1)^0x1021)&0xffff if c&0x8000 else (c<<1)&0xffff
    return c

def frame(cmd,sess,seq,offset=0,payload=b''):
    body=struct.pack('<BBHHHH',1,cmd,sess,seq,offset,len(payload))+payload
    return b'\xa5\x5a'+body+struct.pack('<H',crc(body))

def build(folder):
    assert crc(b'123456789')==0x29b1
    records=struct.pack('<IBBBB',0,0,0,60,100)+struct.pack('<IBBBB',48000,1,0,60,0)
    events=[int.from_bytes(records[n:n+8],'little') for n in range(0,16,8)]
    valid=0;count=0;sid=0;active=0;received=0;cases=[];lines=[]
    def add(label,raw,error=0,event=None,publish=None,a=None,got=None,reset=False):
        nonlocal valid,count,sid,active,received
        idx=len(cases)
        if reset:valid=count=sid=active=received=0;cases.append({'id':idx,'label':label,'op':'R','response':None,'commit_pulses':0});lines.append(f'R {idx} 0\n');return
        version,cmd,sess,seq,offset,length=struct.unpack('<BBHHHH',raw[2:12])
        if publish:valid=1;count=2;sid=101
        if a is not None:active=a
        if got is not None:received=got
        pay=struct.pack('<BBBBHIH',cmd,error,valid,active,count,sid,received)
        if event is not None:pay+=records[event*8:event*8+8]
        response=frame(0x80 if not error else 0x81,sess,seq,offset,pay)
        cases.append({'id':idx,'label':label,'op':'S','request':raw.hex(),'response':response.hex(),'committed_valid':valid,'committed_count':count,'score_id':sid,'active':active,'received':received,'event_index':event,'expected_event':None if event is None else events[event]})
        lines.append(f'S {idx} {len(raw)}\n'+' '.join(f'{b:02x}' for b in raw)+'\n')
    add('READ_empty',frame(6,7,0),13)
    add('BEGIN_score101',frame(1,7,0,payload=struct.pack('<IHHHI',101,2,16,crc(records),48000)),a=1,got=0)
    add('DATA_complete',frame(2,7,1,payload=records),got=16)
    add('wrong_sequence_preserves_stage',frame(2,7,5,payload=records[:8]),6)
    commit=frame(3,7,2)
    add('COMMIT_atomic',commit,publish=True,a=0)
    add('COMMIT_lost_ACK_duplicate',commit)
    add('READ_all_event0',frame(6,7,3,0),event=0)
    add('READ_all_event1',frame(6,7,4,1),event=1)
    raw=frame(5,7,5);bad=raw[:-1]+bytes([raw[-1]^1]);add('bad_frame_CRC',bad,1)
    add('ABORT_keeps_publication',frame(4,7,6),a=0,got=0)
    add('READ_old_after_abort',frame(6,7,7,1),event=1)
    add('shared_reset_clears_valid',b'',reset=True)
    add('STATUS_after_reset',frame(5,7,8))
    folder.mkdir(parents=True,exist_ok=False);(folder/'plan.txt').write_text(''.join(lines),encoding='ascii');oracle={'schema':1,'scope':'short exact fulltop upload withtwoevents; not all512/broad protocol qualification','cases':cases,'count':len(cases),'expected_serial_responses':12,'expected_commits_before_reset':1,'published_records_bytes':records.hex(),'source_input_sha':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(folder/'oracle.json').write_text(json.dumps(oracle,indent=2)+'\n',encoding='utf-8');return oracle
