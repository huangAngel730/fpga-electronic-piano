`timescale 1ns/1ps
module tb_panel_uart;
import audio_defs_pkg::*;
logic clk=0;always #10 clk=~clk;
logic rst_n=0,rx=1,ready=1;wire valid;performance_event_t data;
wire[15:0]level,peak;wire[31:0]frame_errors,parse_errors,overflow;wire busy;
midi_input_panel_candidate dut(clk,rst_n,rx,ready,valid,data,level,peak,frame_errors,parse_errors,overflow,busy);
integer checks=0,actions=0,notes=0,volumes=0,last_volume=-1;integer expected_ids[0:3];
task automatic ck(input logic ok,input string msg);checks++;if(ok!==1'b1)$fatal(1,"panel realUART %s actions%0d notes%0d",msg,actions,notes);endtask
always @(posedge clk)if(rst_n&&valid&&ready)begin
 if(data.event_type==EVENT_CONTROL_CHANGE&&data.control_id>=7&&data.control_id<=9)begin
 ck(actions<4&&data.control_id==expected_ids[actions],"discrete press order");actions++;
 end
 if(data.event_type==EVENT_NOTE_ON||data.event_type==EVENT_NOTE_OFF)notes++;
 if(data.event_type==EVENT_CONTROL_CHANGE&&data.control_id==CTRL_VOLUME)begin volumes++;last_volume=data.control_value;end
end
task automatic octet(input logic[7:0]value);@(negedge clk);rx=0;repeat(1600)@(negedge clk);for(integer n=0;n<8;n++)begin rx=value[n];repeat(1600)@(negedge clk);end rx=1;repeat(1600)@(negedge clk);endtask
task automatic cc(input integer id,value);octet(8'hb0);octet(8'(id));octet(8'(value));endtask
initial begin
expected_ids[0]=7;expected_ids[1]=8;expected_ids[2]=9;expected_ids[3]=8;
repeat(6)@(negedge clk);rst_n=1;repeat(10)@(negedge clk);
cc(7,0);cc(7,127);cc(25,127);cc(25,127);cc(25,0);
cc(26,127);cc(26,0);cc(27,127);cc(27,0);
//2ms between complete release and next high (not USB timing claim).
repeat(100000)@(negedge clk);cc(26,127);cc(26,0);
cc(28,127);cc(29,127);cc(30,127);
octet(8'h90);octet(69);octet(100);octet(8'h80);octet(69);octet(0);
repeat(100010)@(negedge clk);
ck(actions==4&&notes==2&&volumes==2&&last_volume==4095,"nonempty normal output");
ck(frame_errors==0&&parse_errors==0&&overflow==0,"no UART/parser/FIFO error");
$display("PASS realUART panel checks=%0d actions=%0d notes=%0d volumes=%0d 50MHz/31250/8N1",checks,actions,notes,volumes);$finish;
end
initial begin #100000000;$fatal(1,"real UART timeout");end
endmodule
