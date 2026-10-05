from pathlib import Path
import os,subprocess,json,hashlib
import argparse
root=Path(__file__).resolve().parents[4]; scope=root/'code/tb/common/midi_prepared_candidate'
cli=argparse.ArgumentParser();cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();out=args.output.resolve();out.relative_to(root/'code/output');out.mkdir(parents=True,exist_ok=False)
s=(scope/'midi_event_parser.sv').read_text(encoding='utf-8');a=s.index('    // ISOLATED M2 candidate');b=s.index('    integer comb_fifo_index;',a);pre=s[a:b];a=s.index('    always_comb begin\n        parsed_control_keep_pending');b=s.index('    // At most one locked control event;',a);arb=s[a:b]
header='''`timescale 1ns/1ps
module prepared_selector_probe(input logic clk,rst_n,input logic[31:0]control_pending,input logic[4:0]round_robin_index,input logic parsed_control,input logic[4:0]parsed_control_index,input logic[11:0]value_in,output logic selected_valid,output logic[4:0]selected_index,output logic[11:0]selected_value);
import audio_defs_pkg::*;
performance_event_t parsed_event_data;
wire performance_event_t locked_event='0;
wire control_locked=1'b0;wire[4:0]locked_index=0;
wire[15:0]mod_sent_valid=16'hffff;
wire[11:0]mod_sent_value[0:15];
wire[11:0]pending_value[0:31];
for(genvar k=0;k<16;k++)assign mod_sent_value[k]=0;
for(genvar k=0;k<32;k++)assign pending_value[k]=12'(k+1);
always_comb begin parsed_event_data='0;parsed_event_data.control_value=value_in;end
logic parsed_control_keep_pending,grant_control;
wire[15:0]control_cooldown=16'd1;
wire[3:0]fifo_count=0;
wire parsed_discrete=0,discrete_handshake=0,burst_limit_reached=0;
'''
source=header+pre+arb+'endmodule\n';(out/'probe.sv').write_text(source,encoding='utf-8',newline='\n')
bt='''`timescale 1ns/1ps
module tb_prepared_corner;
logic clk=0,rst_n=0;always #10 clk=~clk;
logic[31:0]p=0;logic[4:0]rr=0,ix=0;logic parsed=0;logic[11:0]val=0;
wire v;wire[4:0]idx;wire[11:0]value;
prepared_selector_probe dut(clk,rst_n,p,rr,parsed,ix,val,v,idx,value);
integer checks=0;
initial begin
repeat(2)@(negedge clk);rst_n=1;
for(integer n=0;n<32;n++) begin
 @(negedge clk);rr=5'(n);p=(32'd1<<5'(n+1))|(32'd1<<5'(n+3))|(32'd1<<5'(n+5));
 // This corner uses CC1 cancellation (odd absolute slot). For even RR, all three are CC1.
 if(n%2==0)begin
 parsed=1;ix=5'(n+1);val=0;
 @(posedge clk);#1;p=p&~(32'd1<<ix);ix=5'(n+3);#1;
 if(!v || idx!==5'(n+5))$fatal(1,"two consecutive cancellations mismatch rr=%0d got=%0d",n,idx);
 checks++;
 end else begin
 parsed=0;@(posedge clk);#1;
 parsed=1;ix=5'(n);val=12'd371;
 #1;if(!v || idx!==5'(n) || value!=371)$fatal(1,"current insertion priority mismatch rr=%0d",n);
 checks++;
 end
end
@(negedge clk);rst_n=0;parsed=0;p=0;@(posedge clk);#1;if(v)$fatal(1,"reset stale candidate");checks++;
if(checks!=33)$fatal(1,"empty corner check");
$display("PASS prepared corner checks=%0d",checks);$finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
''';(out/'tb.sv').write_text(bt,encoding='ascii')
env=os.environ.copy();cad=Path('D:/Gowin/oss-cad-suite');env['PATH']=str(cad/'lib')+';'+str(cad/'bin')+';'+env['PATH']; results={}
for name,body,expected in [('positive',source,True),('third_fallback_wrong',source.replace('old_second_index=prepared_index2;','old_second_index=prepared_index0;',1),False)]:
    src=out/(name+'.sv');src.write_text(body,encoding='utf-8',newline='\n');image=out/(name+'.vvp')
    comp=subprocess.run([str(cad/'bin/iverilog.exe'),'-g2012','-s','tb_prepared_corner','-o',str(image),str(root/'code/rtl/common/audio_defs_pkg.sv'),str(src),str(out/'tb.sv')],capture_output=True,env=env,timeout=30)
    (out/(name+'_compile.log')).write_bytes(comp.stdout+comp.stderr)
    if comp.returncode:raise RuntimeError(name+' compile failed')
    run=subprocess.run([str(cad/'bin/vvp.exe'),str(image)],capture_output=True,env=env,timeout=30); (out/(name+'.log')).write_bytes(run.stdout+run.stderr)
    print(name,'compile',comp.returncode,'run',run.returncode,(run.stdout+run.stderr).decode(errors='replace'))
    assert (run.returncode==0)==expected
    assert (b'PASS prepared corner checks=33' if expected else b'two consecutive cancellations mismatch') in run.stdout+run.stderr
    results[name]={'compile':comp.returncode,'run':run.returncode,'expected_success':expected}
(out/'result.json').write_text(json.dumps({'cases':33,'runs':results,'candidate_SHA':hashlib.sha256((scope/'midi_event_parser.sv').read_bytes()).hexdigest()},indent=2)+'\n',encoding='utf-8')