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
from adsr_piano import velocity_to_gain

class PianoV1Lane:
    """Independent algorithm-state oracle; actual lifecycle uses M1 ADSR/ROM."""
    def __init__(self):
        self.phase=0;self.fcw=0;self.active=3;self.left=0
        self.pending=3;self.wait_wrap=False
    def body_attack(self):
        if self.fcw <= 134217728:return 1,0
        if self.fcw <= 268435456:return 2,1
        if self.fcw <= 536870912:return 3,2
        return 3,3
    def note_on(self,velocity,fcw):
        self.fcw=fcw
        body,bright=self.body_attack()
        self.left=1440 if velocity>=768 else 960 if velocity>=512 else 480 if velocity>=256 else 0
        self.active=bright if self.left else body
        self.wait_wrap=False
    def step(self,table):
        previous=self.phase
        self.phase=(self.phase+self.fcw)&0xffffffff
        wraps=self.phase<previous
        body,_=self.body_attack()
        if self.wait_wrap and wraps:
            self.active=self.pending;self.wait_wrap=False
        elif self.left:
            self.left-=1
            if self.left==0:
                if wraps:self.active=body
                else:self.pending=body;self.wait_wrap=True
        # Frame snapshots happen after ROM has settled to the advanced phase.
        return table[self.active*256+(self.phase>>24)]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('trace',type=Path);parser.add_argument('--piano-v1',action='store_true');args=parser.parse_args()
    envs=[PianoADSREnvelope() for _ in range(4)];phases=[0]*4;fcws=[0]*4
    table=make_wavetable('sine',1024,8192);samples=0;max_env_error=0;max_pcm_error=0
    piano_lanes=[PianoV1Lane() for _ in range(4)]
    if args.piano_v1:
        table=[int(line,16) for line in (ROOT/'code/model/generated/wavetables/piano_band_4x256_8191.mem').read_text().splitlines() if line.strip()]
        table=[value-65536 if value>=32768 else value for value in table]
        gain_rom=[int(line,16) for line in (ROOT/'code/model/generated/wavetables/velocity_gain_rom.mem').read_text().splitlines() if line.strip()]
        if len(gain_rom)!=1024 or len(table)!=1024:raise ValueError('Incomplete formal ROM')
        if any(velocity_to_gain(i)!=gain_rom[i] for i in range(1024)):
            raise ValueError('ADSR model gain differs from formal velocity ROM')
    for number,line in enumerate(args.trace.read_text(encoding='utf-8').splitlines(),1):
        fields=line.split()
        if fields[0]=='N' and len(fields)==4:
            lane,velocity,fcw=map(int,fields[1:]);envs[lane].note_on(velocity);fcws[lane]=fcw
            piano_lanes[lane].note_on(velocity,fcw)
        elif fields[0]=='F' and len(fields)==2:envs[int(fields[1])].note_off()
        elif fields[0]=='S' and len(fields)==11:
            values=list(map(int,fields[1:]));expected_pcm=0
            for i in range(4):
                envelope=envs[i].step();phases[i]=(phases[i]+fcws[i])&0xffffffff
                wave=piano_lanes[i].step(table) if args.piano_v1 else table[phases[i]>>22]
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
    print(f'PASS polyphonic Python trace timbre={"pianoV1" if args.piano_v1 else "sine"} samples={samples} envelope_max_delta={max_env_error} PCM24_max_delta={max_pcm_error} (limit1024 derived from four-lane envelope tolerance)')
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError) as exc:print('FAIL polyphonic Python trace:',exc,file=sys.stderr);raise SystemExit(1)