"""Replay registered lane events against unchanged M1 ADSR and DDS ROM.

Allocator identity/LRU is tested separately. This verifies independent sample
progression from the observed dispatches, not just gain of RTL snapshots.
"""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'code/model'))
from adsr_piano import PianoADSREnvelope
from dds_model import make_wavetable

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('trace',type=Path);args=parser.parse_args()
    envs=[PianoADSREnvelope() for _ in range(4)];phases=[0]*4;fcws=[0]*4
    table=make_wavetable('sine',1024,8192);samples=0;max_env_error=0;max_pcm_error=0
    for number,line in enumerate(args.trace.read_text(encoding='utf-8').splitlines(),1):
        fields=line.split()
        if fields[0]=='N' and len(fields)==4:
            lane,velocity,fcw=map(int,fields[1:]);envs[lane].note_on(velocity);fcws[lane]=fcw
        elif fields[0]=='F' and len(fields)==2:envs[int(fields[1])].note_off()
        elif fields[0]=='S' and len(fields)==11:
            values=list(map(int,fields[1:]));expected_pcm=0
            for i in range(4):
                envelope=envs[i].step();phases[i]=(phases[i]+fcws[i])&0xffffffff
                wave=table[phases[i]>>22]
                error=abs(envelope-values[i]);max_env_error=max(max_env_error,error)
                if error>2:raise ValueError(f'line{number} lane{i}: envelope delta{error}, model{envelope}, RTL{values[i]}')
                if wave!=values[4+i]:raise ValueError(f'line{number} lane{i}: DDS wave mismatch')
                expected_pcm+=((wave*envelope)//32768)*256
            expected_pcm=max(-8388608,min(8388607,expected_pcm))
            pcm_error=max(abs(expected_pcm-values[8]),abs(expected_pcm-values[9]));max_pcm_error=max(max_pcm_error,pcm_error)
            # <=2 envelope LSB each lane -> <=1 integer wave output LSB each
            # at |wave|<=8192; four lane errors -> <=4*256 PCM24 LSB.
            if pcm_error>1024:raise ValueError(f'line{number}: combined PCM delta{pcm_error}')
            samples+=1
        else:raise ValueError(f'Malformed row{number}')
    if samples!=10140:raise ValueError(f'Unexpected complete trace length{samples}')
    print(f'PASS polyphonic Python trace samples={samples} envelope_max_delta={max_env_error} PCM24_max_delta={max_pcm_error} (limit1024 derived from four-lane envelope tolerance)')
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as exc:print('FAIL polyphonic Python trace:',exc,file=sys.stderr);raise SystemExit(1)