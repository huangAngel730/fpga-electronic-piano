"""One bounded isolated one-hot pending update experiment. No production edits."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

ROOT=Path('E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano')
SCOPE=Path('E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/tb/common/midi_pending_mask_candidate')
CAD=Path('E:/FPGA/GAOYUNFPGA/138K_try/tools/icarus_oss_copy')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();out=args.output.resolve();out.relative_to(Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_followup_20261005/B_parallel_pending_mask'))
    if out.exists():raise ValueError('preserve old output; choose a new directory')
    out.mkdir(parents=True)
    manifest=json.loads((SCOPE/'manifest.json').read_text())
    original=Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005/C_reset_route1/sources/midi_event_parser.sv').read_bytes()
    assert hashlib.sha256(original).hexdigest()==manifest['frozen_parser_SHA']
    assert sha(SCOPE/'midi_event_parser.sv')==manifest['candidate_SHA']
    env=os.environ.copy();env['PATH']=str(CAD/'lib')+';'+str(CAD/'bin')+';'+env['PATH']
    results={}
    def run(label,cmd,positive=True,marker=None,timeout=200):
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:
            q=subprocess.run(list(map(str,cmd)),cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        text=(out/(label+'.log')).read_text(encoding='utf-8',errors='replace')
        results[label]={'exit':q.returncode,'expected_success':positive,'log_SHA':sha(out/(label+'.log'))}
        print(label,'EXIT',q.returncode,text[-650:],flush=True)
        if ((q.returncode==0)!=positive or (marker and marker not in text)):
            raise RuntimeError('unexpected result '+label)
        return text
    candidate=Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_followup_20261005/B_parallel_pending_mask/sources/midi_event_parser.sv');text=candidate.read_text(encoding='utf-8')
    ref=out/'baseline.sv';ref.write_bytes(original.replace(b'module midi_event_parser #(',b'module midi_event_parser_frozen #(',1))
    # Use the previous independent full port/state miter, changing only its
    # displayed label and fourth burst parameter to16. Both DUTs use this.
    previous=ROOT/'code/tb/common/midi_scheduler_setup_review/tb_m2_parser_miter.sv'
    tb=out/'tb_pending_miter.sv';t=previous.read_text(encoding='utf-8')
    t=t.replace('i==3?3:8','i==3?16:8')
    assert 'i==3?16:8' in t
    tb.write_text(t,encoding='utf-8',newline='\n')
    defs=Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_followup_20261005/B_parallel_pending_mask/sources/audio_defs_pkg.sv')
    run('full_miter_compile',[CAD/'bin/iverilog.exe','-B',CAD/'lib/ivl','-g2012','-s','tb_m2_parser_miter','-o',out/'miter.vvp',defs,candidate,ref,tb])
    run('full_miter',[CAD/'bin/vvp.exe',out/'miter.vvp'],marker='PASS M2 full original parser miter lane=3',timeout=240)
    # An independent linear reference decides grant and priority from inputs,
    # then executes ORIGINAL grant-clear / parsed-update register semantics.
    # Feed the actual unmodified candidate source slices in a combinational DUT.
    a=text.index('    // Precompute the first TWO');b=text.index('    integer comb_fifo_index;',a)
    tree=text[a:b]
    a=text.index('    always_comb begin\n        parsed_control_keep_pending',b)
    b=text.index('\n    // At most one locked control event;',a)
    decision=text[a:b]
    header="""`timescale 1ns/1ps
module exact_mask_selector(input logic[31:0]control_pending,
input logic[4:0]round_robin_index,parsed_control_index,locked_index,
input logic parsed_control,control_locked,
input logic[11:0]new_value,held_value,
input logic[15:0]control_cooldown,input logic[3:0]fifo_count,
input logic parsed_discrete,event_ready,burst_limit_reached,
output logic selected_valid,output logic[4:0]selected_index,
output logic[11:0]selected_value,output logic[31:0]selected_mask,
output logic grant_control,output wire[31:0]control_pending_next);
import audio_defs_pkg::*;
performance_event_t parsed_event_data,locked_event;
wire[11:0]pending_value[0:31];wire[11:0]mod_sent_value[0:15];
for(genvar i=0;i<32;i++)assign pending_value[i]=12'(256+17*i);
for(genvar j=0;j<16;j++)assign mod_sent_value[j]=0;
wire[15:0]mod_sent_valid=16'hffff;
logic parsed_control_keep_pending;
localparam FIFO_COUNT_WIDTH=4;
wire discrete_handshake=!control_locked && fifo_count!=0 && event_ready;
always_comb begin parsed_event_data='0;parsed_event_data.control_value=new_value;
locked_event='0;locked_event.control_value=held_value;end
"""
    actual=out/'actual_mask_selector.sv';actual.write_text(header+tree+decision+'\nendmodule\n',encoding='utf-8',newline='\n')
    rng=random.Random(20261003)
    rows=[];cases=0;set_and_clear=0
    for rr in range(32):
        for pat in range(130):
            mask=0 if pat==0 else 0xffffffff if pat==1 else 1<<(pat-2) if pat<34 else (1<<(pat-34))|(1<<((pat-33)%32)) if pat<66 else rng.getrandbits(32)
            for ix in range(32):
                for action in range(3):
                    cases+=1;active=int(action!=0);val=0 if action==2 else 1234
                    locked=int(cases%11==0);li=ix if cases%13==0 else rng.randrange(32);held=1234
                    cool=1 if cases%3==0 else 0;q=0 if cases%4==0 else 8
                    discrete=int(cases%7==0);ready=int(cases%5!=0);burst=int(cases%2==0)
                    keep=not ((ix&1) and val==(held if locked and li==ix else 0))
                    effective=mask
                    if active:effective=(effective|(1<<ix)) if keep else (effective&~(1<<ix))
                    win=next(((rr+offset)&31 for offset in range(32) if effective>>((rr+offset)&31)&1),None)
                    valid=int(win is not None);wi=win if valid else 0
                    wvalue=val if valid and active and win==ix else 256+17*wi if valid else 0
                    selected=1<<wi if valid else 0
                    grant=int(not locked and cool==0 and valid and ((q==0 and not discrete) or (q!=0 and ready and burst)))
                    nxt=mask
                    if grant:nxt&=~selected
                    if active:
                        if (grant and ix==wi) or not keep:nxt&=~(1<<ix)
                        else:nxt|=1<<ix
                    nxt&=0xffffffff
                    if grant and active and ix==wi:set_and_clear+=1
                    rows.append(f'{mask:08x} {rr} {ix} {li} {active} {locked} {val} {held} {cool} {q} {discrete} {ready} {burst} {valid} {wi} {wvalue} {selected:08x} {grant} {nxt:08x}\n')
    assert cases==399360 and set_and_clear>100
    vec=out/'mask_vectors.txt';vec.write_text(''.join(rows),encoding='ascii')
    unit="""`timescale 1ns/1ps
module tb_mask_selector;
logic[31:0]pending;logic[4:0]rr,ix,li;logic active,locked;
logic[11:0]val,held;logic[15:0]cool;logic[3:0]q;
logic discrete,ready,burst;wire valid;wire[4:0]idx;wire[11:0]value;
wire[31:0]mask,nxt;wire grant;
exact_mask_selector dut(pending,rr,ix,li,active,locked,val,held,cool,q,discrete,ready,burst,valid,idx,value,mask,grant,nxt);
integer fd,r,n=0,processed=0,a,b,c,d,e,f,g,h,i,j,k,l,m,o,pg;
reg[31:0]pp,sm,pn;
string vector_path="mask_vectors.txt";
initial begin
if($value$plusargs("VECTORS=%s",vector_path))begin end
fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"missing vectors");
while(!$feof(fd))begin
r=$fscanf(fd,"%h %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %h %d %h\\n",pp,a,b,c,d,e,f,g,h,i,j,k,l,m,o,pg,sm,n,pn);
if(r==19)begin
pending=pp;rr=5'(a);ix=5'(b);li=5'(c);active=1'(d);locked=1'(e);
val=12'(f);held=12'(g);cool=16'(h);q=4'(i);discrete=1'(j);ready=1'(k);burst=1'(l);
#2;processed++;
if({valid,idx,value,mask,grant,nxt}!=={1'(m),5'(o),12'(pg),sm,1'(n),pn})$fatal(1,"mask+pending independent oracle mismatch RR=%0d ix=%0d got mask=%h pending=%h expected mask=%h pending=%h",a,b,mask,nxt,sm,pn);
end else if(r!=-1)$fatal(1,"malformed vector");
end
if(processed!=399360)$fatal(1,"mask oracle empty/truncated case count=%0d",processed);
$display("PASS mask/next-pending independent cases=%0d",processed);$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule
"""
    utb=out/'tb_mask_selector.sv';utb.write_text(unit,encoding='ascii')
    run('mask_compile',[CAD/'bin/iverilog.exe','-B',CAD/'lib/ivl','-g2012','-s','tb_mask_selector','-o',out/'mask.vvp',defs,actual,utb])
    run('mask_oracle',[CAD/'bin/vvp.exe',out/'mask.vvp'],marker='PASS mask/next-pending independent cases=399360')
    # One-bit pending precedence fault must be detected behaviorally after compile.
    bad=out/'wrong_clear.sv';s=actual.read_text()
    anchor='(parsed_control_keep_pending && !(grant_control && selected_mask[update_slot]))'
    assert s.count(anchor)==1
    bad.write_text(s.replace(anchor,'parsed_control_keep_pending',1),encoding='utf-8',newline='\n')
    run('wrong_clear_compile',[CAD/'bin/iverilog.exe','-B',CAD/'lib/ivl','-g2012','-s','tb_mask_selector','-o',out/'wrong_clear.vvp',defs,bad,utb])
    run('wrong_clear',[CAD/'bin/vvp.exe',out/'wrong_clear.vvp'],positive=False,marker='mask+pending independent oracle mismatch')
    rotate_bad=out/'wrong_rotation.sv'
    anchor="6'd32 - {1'b0, round_robin_index};"
    source=actual.read_text()
    if source.count(anchor)!=1:raise ValueError('rotation mutant anchor')
    rotate_bad.write_text(source.replace(anchor,"6'd32 + {1'b0, round_robin_index};",1),encoding='utf-8',newline='\n')
    run('wrong_rotation_compile',[CAD/'bin/iverilog.exe','-B',CAD/'lib/ivl','-g2012','-s','tb_mask_selector','-o',out/'wrong_rotation.vvp',defs,rotate_bad,utb])
    run('wrong_rotation',[CAD/'bin/vvp.exe',out/'wrong_rotation.vvp'],positive=False,marker='mask+pending independent oracle mismatch')
    for label,content in [('empty',''),('truncated',rows[0])]:
        bad_vector=out/(label+'.txt');bad_vector.write_text(content,encoding='ascii')
        run('guard_'+label,[CAD/'bin/vvp.exe',out/'mask.vvp','+VECTORS='+str(bad_vector)],positive=False,marker='mask oracle empty/truncated case count')
    record={'scope':'isolated candidate functional equivalence, not physical STA','formal_parser_modified':False,'manifest':manifest,
            'current_formal_SHA':sha(Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005/C_reset_route1/sources/midi_event_parser.sv')),
            'exact_extracted_selector_SHA':sha(actual),'vectors_SHA':sha(vec),'cases':cases,'same_slot_grant_updates':set_and_clear,
            'miter_cycles_per_config':256193,'configurations':4,'fourth_burst':16,'runs':results}
    (out/'functional_review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print('PASS functional candidate; physical adoption evaluated separately')
    return 0

if __name__=='__main__':raise SystemExit(main())
