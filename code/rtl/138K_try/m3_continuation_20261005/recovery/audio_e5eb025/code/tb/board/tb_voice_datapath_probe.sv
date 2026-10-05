`timescale 1ns/1ps
module tb_voice_datapath_probe;
    logic sys_clk=0,sys_rst_n=1,sample_tick=0;
    logic [3:0] note_on=0,note_off=0;
    logic [39:0] velocity=0;
    logic [127:0] fcw=0;
    wire signed [23:0] left_1,right_1,left_4,right_4;
    wire clip_1,clip_4;
    wire [3:0] states_1,states_4;
    integer checks=0,nonzero_4=0,differing=0;
    always #10 sys_clk=~sys_clk;
    voice_datapath_probe_1 single (
        .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.sample_tick(sample_tick),
        .note_on(note_on),.note_off(note_off),.velocity(velocity),.fcw(fcw),
        .pcm_left(left_1),.pcm_right(right_1),.clip_any(clip_1),
        .lane_state_nonzero(states_1)
    );
    voice_datapath_probe_4 quad (
        .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.sample_tick(sample_tick),
        .note_on(note_on),.note_off(note_off),.velocity(velocity),.fcw(fcw),
        .pcm_left(left_4),.pcm_right(right_4),.clip_any(clip_4),
        .lane_state_nonzero(states_4)
    );
    task automatic check(input logic ok,input string label_text);
        checks++;
        if(ok!==1'b1)$fatal(1,"T024 probe FAIL: %s",label_text);
    endtask
    task automatic tick;
        @(negedge sys_clk);sample_tick=1;
        @(negedge sys_clk);sample_tick=0;
        repeat(3)@(negedge sys_clk);
    endtask
    task automatic on(input integer mask);
        @(negedge sys_clk);note_on=mask[3:0];
        @(negedge sys_clk);note_on=0;
    endtask
    initial begin
        // Distinct phase steps and velocities; each four-lane input is used.
        velocity={10'd512,10'd640,10'd768,10'd1023};
        fcw={32'd78500000,32'd58800000,32'd49400000,32'd39370534};
        #1;sys_rst_n=0;
        repeat(3)@(negedge sys_clk);
        check(states_1==0 && states_4==0,"async reset clears all ADSR states");
        sys_rst_n=1;
        on(4'b0001);
        repeat(6)tick();
        check(states_1==4'b0001 && states_4==4'b0001,
              "lane0 active in both variants");
        check(left_1===left_4,"one/four identical while only lane0 active");
        on(4'b1110);
        repeat(270)begin
            tick();
            check(^left_4!==1'bx && ^right_4!==1'bx && ^left_1!==1'bx,
                  "no unknown PCM after synchronous ROM init");
            if(left_4!==0)nonzero_4++;
            if(left_1!==left_4)differing++;
            if(!clip_4)check(right_4===-left_4,
                             "provisional stereo opposite polarity when unclipped");
        end
        check(states_4==4'b1111 && states_1==4'b0001,
              "four independent envelopes remain active");
        check(nonzero_4>200 && differing>200,
              "four DDS/ADSR lanes affect observable mix");
        @(negedge sys_clk);sys_rst_n=0;
        repeat(3)@(negedge sys_clk);
        check(states_1==0 && states_4==0,"mid-run reset clears states");
        $display("PASS tb_voice_datapath_probe checks=%0d nonzero=%0d differing=%0d",
                 checks,nonzero_4,differing);
        $finish;
    end
    initial begin #5_000_000;$fatal(1,"T024 probe timeout");end
endmodule
