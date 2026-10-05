// M2 independent real RTL check for M1 revised T027 receipt.
// Scoreboard models pre-increment phase, per-slot latch and actual 4-register
// data/valid path (accepted edge E -> output E+3). No production force/bypass.
`timescale 1ns/1ps
module tb_t027_revised_delivery;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0;
    logic [3:0] sample_tick=0,note_on=0,note_off=0,timbre_select=0;
    logic [31:0] fcw [0:3];
    wire signed [15:0] sample_out [0:3];
    wire [3:0] sample_valid;
    logic signed [15:0] sine [0:1023],triangle [0:1023];
    logic [31:0] phase_ref [0:3];
    logic latched_ref [0:3];
    logic [9:0] address_ref [0:3][0:3];
    logic timbre_ref [0:3][0:3],valid_ref [0:3][0:3];
    integer checks=0,valid_outputs=0,cycles=0,transitions=0;
    integer fd=0,record_samples=0,position=0;
    logic recording=0;
    string capture;
    bit corrupt_expected;
    logic signed [15:0] expected_value;
    for(genvar i=0;i<4;i++)begin:g_lane
        timbre_oscillator dut(.clk(clk),.rst_n(rst_n),.sample_tick(sample_tick[i]),
            .fcw(fcw[i]),.timbre_select(timbre_select[i]),.note_on(note_on[i]),
            .note_off(note_off[i]),.sample_out(sample_out[i]),.sample_valid(sample_valid[i]));
    end
    task automatic check(input logic ok,input string message);
        checks++;if(ok!==1'b1)$fatal(1,"T027 revised %s cycle=%0d",message,cycles);
    endtask
    always @(posedge clk)begin
        cycles++;
        if(!rst_n)begin
            for(integer i=0;i<4;i++)begin
                phase_ref[i]=0;latched_ref[i]=0;
                for(integer j=0;j<4;j++)begin
                    address_ref[i][j]=0;timbre_ref[i][j]=0;valid_ref[i][j]=0;
                end
            end
        end else begin
            for(integer i=0;i<4;i++)begin
                for(integer j=3;j>0;j--)begin
                    address_ref[i][j]=address_ref[i][j-1];
                    timbre_ref[i][j]=timbre_ref[i][j-1];
                    valid_ref[i][j]=valid_ref[i][j-1];
                end
                address_ref[i][0]=phase_ref[i][31:22];
                timbre_ref[i][0]=latched_ref[i];
                valid_ref[i][0]=sample_tick[i];
                if(sample_tick[i])phase_ref[i]=phase_ref[i]+fcw[i];
                if(note_on[i])begin
                    latched_ref[i]=timbre_select[i];transitions++;
                end
            end
        end
        #1;
        for(integer i=0;i<4;i++)begin
            check(sample_valid[i]===valid_ref[i][3],"valid edge and reset match");
            if(!rst_n)check(sample_out[i]===0,"reset clears output");
            else if(sample_valid[i])begin
                expected_value=timbre_ref[i][3] ? triangle[address_ref[i][3]] : sine[address_ref[i][3]];
                if(corrupt_expected)expected_value=expected_value^16'h0001;
                if(sample_out[i]!==expected_value)
                    $fatal(1,"T027 revised PCM mismatch lane=%0d addr=%0d timbre=%0d expected=%0d actual=%0d cycle=%0d",i,address_ref[i][3],timbre_ref[i][3],expected_value,sample_out[i],cycles);
                checks++;valid_outputs++;
                check(sample_out[i]>=-8192 && sample_out[i]<=8192,"frozen sample amplitude");
            end
        end
        if(recording && (&sample_valid))begin
            $fdisplay(fd,"PCM %0d %0d %0d %0d",sample_out[0],sample_out[1],sample_out[2],sample_out[3]);
            record_samples++;
        end
    end
    task automatic cycle;
        @(posedge clk);#2;@(negedge clk);
    endtask
    task automatic reset;
        rst_n=0;sample_tick=0;note_on=0;note_off=0;timbre_select=0;recording=0;
        repeat(5)cycle();rst_n=1;repeat(2)cycle();
    endtask
    task automatic select(input logic [3:0] values,input logic [3:0] mask);
        timbre_select=values;note_on=mask;cycle();note_on=0;cycle();
    endtask
    task automatic record_block(input string name,input integer count);
        $fdisplay(fd,"BEGIN %s %0d",name,count);recording=1;
        repeat(count)cycle();recording=0;
    endtask
    initial begin
        corrupt_expected=$test$plusargs("NEGATIVE_DATA");
        if(!$value$plusargs("CAPTURE=%s",capture))$fatal(1,"CAPTURE required");
        fd=$fopen(capture,"w");if(!fd)$fatal(1,"Capture open failed");
        $readmemh("sine_wavetable.hex",sine);$readmemh("triangle_wavetable.hex",triangle);
        for(integer i=0;i<1024;i++)
            if(^sine[i]===1'bx || ^triangle[i]===1'bx)$fatal(1,"Incomplete reference ROM %0d",i);
        for(integer i=0;i<4;i++)fcw[i]=32'h00400000;
        @(negedge clk);reset();select(4'b1010,4'b1111);
        sample_tick=15;repeat(1028)cycle();
        // Switching global input must not change an already latched lane.
        timbre_select=4'b0101;repeat(64)cycle();
        // Only lane1 relatches on NoteOn, with no phase reset.
        select(4'b0101,4'b0010);repeat(64)cycle();
        // Same-edge Note On and sample use old latch for this sample,
        // then the new latch; the integrator must honor this deterministic edge.
        select(4'b1010,4'b0100);repeat(64)cycle();
        // NoteOff does not stop any lane: waveform remains for external ADSR.
        note_off=15;cycle();note_off=0;repeat(4800)cycle();
        // Independent sparse enables / changing FCWs prove label alignment.
        for(integer n=0;n<512;n++)begin
            sample_tick={n%7==0,n%5==0,n%3==0,n%2==0};
            fcw[0]=32'hfc012345;fcw[1]=32'h00400000;
            fcw[2]=32'h0f123456;fcw[3]=32'h7f000001;
            if(n%31==0)begin timbre_select=~timbre_select;note_on=4'b0101;end
            else note_on=0;
            cycle();
        end
        // Reset while valid/data are still pending must discard them.
        reset();
        // Actual output frequency and four independent timbres captured at
        // exact FCW=2^32/1024; Fs=48000 gives coherent bin1=46.875Hz.
        for(integer i=0;i<4;i++)fcw[i]=32'h00400000;
        select(4'b1010,15);sample_tick=15;repeat(1032)cycle();
        record_block("four_timbres",8192);
        // Actual four oscillator frequencies at the keyboard limits and A4,
        // derived as rounded 32-bit FCWs from independent frequency formula.
        fcw[0]=32'd2460658;fcw[1]=32'd39370534;
        fcw[2]=32'd374557749;fcw[3]=32'd19685267;
        select(4'b1010,15);repeat(16)cycle();record_block("four_notes",32768);
        reset();$fclose(fd);
        check(record_samples==40960,"complete real output capture");
        check(valid_outputs>160000 && transitions>20,"non-vacuous four-lane lifecycle exercise");
        $display("PASS tb_t027_revised_delivery checks=%0d valid_outputs=%0d samples=%0d transitions=%0d cycles=%0d",checks,valid_outputs,record_samples,transitions,cycles);
        $finish;
    end
    initial begin #2000000;$fatal(1,"T027 revised timeout");end
endmodule
