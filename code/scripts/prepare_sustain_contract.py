#!/usr/bin/env python3
"""Prepare M2 CC64/slot contract; optionally check an M3 implementation.

Default checks mapping and port compilation only. A placeholder is never
passed off as a sustain implementation. All vector outputs stay ignored.
"""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

class ContractOracle:
    """Lifecycle events, independent of waveform math and M3 HDL structure."""
    def __init__(self):
        self.pedals = set()
        self.slots = [None] * 4
        self.pending = 0
        self.generations = [0] * 4
        self.rows = []

    def tick(self, reset=False, command=None, ack=False):
        # ready before this edge; a pending release takes precedence over
        # commands even on the edge that acknowledges it.
        was_pending = bool(self.pending)
        if reset:
            self.pedals.clear()
            self.slots = [None] * 4
            self.pending = 0
            self.generations = [0] * 4
        elif was_pending:
            if ack:
                self.pending = 0
                self.generations = [0] * 4
        elif command is not None:
            kind, index, source, channel, note, value, generation = command
            slot = self.slots[index]
            identity = (source, channel, note, generation)
            def release(indices):
                for i in indices:
                    s = self.slots[i]
                    s['key'] = False
                    s['deferred'] = False
                    s['releasing'] = True
                    self.pending |= 1 << i
                    self.generations[i] = s['identity'][3]
            if kind == 0:
                self.slots[index] = {'identity': identity, 'key': True,
                                     'deferred': False, 'releasing': False}
            elif kind == 1 and slot is not None and slot['identity'] == identity and not slot['releasing']:
                slot['key'] = False
                if (source, channel) in self.pedals:
                    slot['deferred'] = True
                else:
                    release([index])
            elif kind == 2:
                if value >= 2048:
                    self.pedals.add((source, channel))
                else:
                    self.pedals.discard((source, channel))
                    release([i for i,s in enumerate(self.slots) if s is not None
                             and s['identity'][:2] == (source, channel)
                             and s['deferred'] and not s['key'] and not s['releasing']])
            elif kind == 3 and slot is not None and slot['identity'] == identity and slot['releasing']:
                self.slots[index] = None
            elif kind == 4:
                self.pedals.clear()
                for s in self.slots:
                    if s is not None:
                        s['key'] = False
                        s['deferred'] = False
                release([i for i,s in enumerate(self.slots) if s is not None and not s['releasing']])
        masks = []
        for field in ('occupied', 'key', 'deferred', 'releasing'):
            masks.append(sum(1 << i for i,s in enumerate(self.slots)
                             if s is not None and (field == 'occupied' or s[field])))
        command = command or (7,0,0,0,0,0,0)
        self.rows.append([int(not reset), int(command[0] != 7), int(ack), *command[:6], command[6],
                          int(not reset and not self.pending), int(bool(self.pending)), self.pending,
                          *self.generations, *masks])

    def send(self, *command):
        # Finish old output before a new semantic command.
        if self.pending:
            self.tick(ack=True)
        self.tick(command=command)


def vectors():
    o = ContractOracle()
    o.tick(reset=True)
    # Ordinary release, output backpressure, invalid input held while pending.
    o.send(0,0,0,0,60,0,1)
    o.send(1,0,0,0,60,0,1)
    for _ in range(3):o.tick(command=(0,1,0,0,64,0,2))
    o.tick(command=(0,1,0,0,64,0,2),ack=True)
    o.send(3,0,0,0,60,0,1)
    # Sustain, key still held, same-note generation, steal and stale retire.
    o.send(2,0,2,3,0,4095,0)
    o.send(0,0,2,3,60,0,10)
    o.send(0,1,2,3,64,0,11)
    o.send(1,0,2,3,60,0,10)
    o.send(2,0,2,3,0,0,0)
    o.send(3,0,2,3,60,0,10)
    o.send(2,0,2,3,0,4095,0)
    o.send(1,1,2,3,64,0,11)
    o.send(0,1,2,3,64,0,12)
    o.send(3,1,2,3,64,0,11)
    o.send(2,0,2,3,0,0,0)
    o.send(2,0,2,3,0,4095,0)
    o.send(1,1,2,3,64,0,12)
    o.send(0,1,9,1,70,0,13)
    o.send(2,0,2,3,0,0,0)
    o.send(3,1,2,3,64,0,12)
    # Multiple deferred slots and global panic/reset under backpressure.
    for i in range(4):o.send(0,i,3,4,60+i,0,20+i)
    o.send(2,0,3,4,0,4095,0)
    for i in range(4):o.send(1,i,3,4,60+i,0,20+i)
    o.send(2,0,3,4,0,0,0)
    o.tick();o.tick();o.tick(reset=True)
    for i in range(4):o.send(0,i,i,i,60+i,0,100+i)
    o.send(4,0,0,0,0,0,0)
    o.tick(ack=True)
    for i in range(4):o.send(3,i,i,i,60+i,0,100+i)
    # Every source/channel pair isolated from neighbouring source/channel.
    for source in range(16):
        for channel in range(16):
            o.tick(reset=True)
            o.send(2,0,source,channel,0,2048,0)
            o.send(0,0,source,channel,60,0,1)
            o.send(0,1,source,(channel+1)%16,60,0,2)
            o.send(0,2,(source+1)%16,channel,60,0,3)
            o.send(1,0,source,channel,60,0,1)
            o.send(1,1,source,(channel+1)%16,60,0,2)
            o.send(1,2,(source+1)%16,channel,60,0,3)
            o.send(2,0,source,(channel+1)%16,0,0,0)
            o.send(2,0,source,channel,0,0,0)
            o.tick(ack=True)
    rng = random.Random(20261001)
    for _ in range(4096):
        command = None
        if rng.randrange(5):
            index = rng.randrange(4)
            slot = o.slots[index]
            kind = rng.randrange(5)
            source,channel,note,generation = slot['identity'] if slot and rng.randrange(4) else (rng.randrange(16),rng.randrange(16),rng.randrange(128),rng.randrange(1,200))
            if kind == 0:generation = rng.randrange(200,100000)
            command = (kind,index,source,channel,note,rng.choice([0,2031,2047,2048,2064,4095]),generation)
        o.tick(reset=rng.randrange(100)==0,command=command,ack=rng.randrange(3)==0)
    o.tick(reset=True)
    return o.rows


def format_row(row):
    # The TB consumes generation values in hex, all other fields decimal.
    return ' '.join(f'{value:08x}' if index in (9,13,14,15,16) else str(value)
                    for index,value in enumerate(row)) + '\n'


def execute(stage, commands, label):
    cad = Path(os.environ.get('YOSYSHQ_ROOT','D:/Gowin/oss-cad-suite'))
    quote = lambda value: '"' + str(value) + '"'
    bat = stage / (label + '.bat')
    bat.write_bytes(('@echo off\r\ncall ' + quote(cad/'environment.bat') + ' >nul\r\n' +
                     '\r\nif errorlevel 1 exit /b 1\r\n'.join(commands) + '\r\nexit /b %errorlevel%\r\n').encode('ascii'))
    result = subprocess.run(['cmd.exe','/c',str(bat)],cwd=stage,capture_output=True,text=True,
                            encoding='utf-8',errors='replace',timeout=60)
    (stage/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--controller',type=Path)
    args = cli.parse_args()
    stage = ROOT/'code/output/sustain_contract'
    stage.mkdir(parents=True,exist_ok=True)
    rows = vectors()
    vector_path = stage/'vectors.txt'
    vector_path.write_text(''.join(map(format_row,rows)),encoding='ascii',newline='\n')
    mapping_tb = stage/'mapping_tb.sv'
    mapping_tb.write_text('''module tb_sustain_mapping;
        import sustain_control_contract_pkg::*;
        integer i,value;
        initial begin
            for(i=0;i<128;i++)begin
                value=sustain_value_from_midi(i[6:0]);
                if((value>=SUSTAIN_DOWN_THRESHOLD)!=(i>=64))$fatal(1,"Threshold mismatch %0d",i);
            end
            if(sustain_value_from_midi(0)!=0 || sustain_value_from_midi(127)!=4095)$fatal(1,"Endpoint");
            $display("PASS sustain mapping128 boundary64");$finish;
        end
    endmodule\n''',encoding='ascii')
    # Compile-only placeholder; no RTL sustain behavior is implemented by M2.
    stub = stage/'ports_only.sv'
    stub.write_text('''`include "sustain_controller_ports.svh"
        module sustain_controller (`SUSTAIN_CONTROLLER_PORTS);
        assign cmd_ready=0;assign release_valid=0;assign release_mask=0;assign release_generations=0;
        assign occupied_mask=0;assign key_down_mask=0;assign deferred_mask=0;assign releasing_mask=0;
        endmodule\n''',encoding='ascii')
    cad = Path(os.environ.get('YOSYSHQ_ROOT','D:/Gowin/oss-cad-suite'))
    quote = lambda value: '"' + str(value) + '"'
    public_pkg = ROOT/'code/rtl/common/audio_defs_pkg.sv'
    pkg = ROOT/'code/rtl/board/sustain_control_contract_pkg.sv'
    inc = ROOT/'code/rtl/board'
    tb = ROOT/'code/tb/board/tb_sustain_contract.sv'
    mapping = stage/'mapping.vvp'
    compiled = stage/'ports.vvp'
    commands = [
        ' '.join(map(quote,[cad/'bin/iverilog.exe','-g2012','-s','tb_sustain_mapping','-o',mapping,public_pkg,pkg,mapping_tb])),
        ' '.join(map(quote,[cad/'bin/vvp.exe',mapping])),
        ' '.join(map(quote,[cad/'bin/iverilog.exe','-g2012','-I',inc,'-s','tb_sustain_contract','-o',compiled,public_pkg,pkg,stub,tb])),
    ]
    result = execute(stage,commands,'prepare')
    if result.returncode or 'PASS sustain mapping128' not in result.stdout:
        print(result.stdout,result.stderr,file=sys.stderr)
        return result.returncode or 1
    print(result.stdout.strip())
    print(f'PASS port/TB compilation; prepared {len(rows)} independent cycle vectors')
    summary = {'interface_mapping_checks':128,'vectors':len(rows),'port_compile':'PASS',
               'actual_sustain_implementation':False,'reference':'M2 documented state contract, not M3 source'}
    if args.controller:
        source = args.controller.resolve()
        if not source.is_file():raise ValueError('Missing controller ' + str(source))
        binary = stage/'controller.vvp'
        cmds = [' '.join(map(quote,[cad/'bin/iverilog.exe','-g2012','-I',inc,'-I',source.parent,
                 '-s','tb_sustain_contract','-o',binary,public_pkg,pkg,source,tb])),
                ' '.join(map(quote,[cad/'bin/vvp.exe',binary,'+VECTORS='+str(vector_path)]))]
        result = execute(stage,cmds,'controller')
        print(result.stdout.strip())
        if result.returncode or f'PASS sustain contract vectors={len(rows)}' not in result.stdout:
            print(result.stderr,file=sys.stderr)
            return result.returncode or 1
        summary['actual_sustain_implementation']=True
        summary['controller']='PASS'
    else:
        print('No implementation tested: M3 must supply sustain_controller.sv before behavior validation')
    (stage/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print('FAIL sustain contract preparation:',error,file=sys.stderr)
        raise SystemExit(1)