`timescale 1ns/1ps
module tb_v3_oscillator;
    reg clk=0, rst_n=0, tick=0, strike=0;
    reg [31:0] fcw=0;
    reg [9:0] velocity=0;
    wire signed [15:0] sample_v3, sample_v1;
    integer fd, result, reset_row, strike_row, tick_row, step, vel;
    integer expected, bass_row, idle, checks=0, rows=0;
    always #10 clk=~clk;
    piano_dds_oscillator_v3 #(.ROM_FILE("piano_rom.mem"),
        .SINE_ROM_FILE("sine_rom.mem")) dut (
        .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(tick),
        .note_on(strike),.velocity(velocity),.fcw(fcw),.wt_sample(sample_v3));
    piano_dds_oscillator #(.ROM_FILE("piano_rom.mem")) formal_v1 (
        .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(tick),
        .note_on(strike),.velocity(velocity),.fcw(fcw),.wt_sample(sample_v1));
    initial begin
        fd=$fopen("oscillator_vectors.txt","r");
        if(fd==0) $fatal(1,"missing independent vectors");
        while(!$feof(fd)) begin
            result=$fscanf(fd,"%d %d %d %h %d %d %d %d\n",
                reset_row,strike_row,tick_row,step,vel,expected,bass_row,idle);
            if(result!=8) $fatal(1,"bad vector row %0d",rows);
            @(negedge clk);
            rst_n=!reset_row;fcw=step;velocity=vel;strike=strike_row;tick=tick_row;
            // An async assertion is checked before the next rising edge.
            if(reset_row && bass_row==1) begin
                #1;
                if(sample_v3!==16'sd0) $fatal(1,"async reset row %0d",rows);
                checks=checks+1;
            end
            @(posedge clk);#1;
            @(negedge clk);strike=0;tick=0;
            repeat(idle) @(negedge clk);
            if(bass_row==1) begin
                if(sample_v3!==16'(expected))
                    $fatal(1,"bass row %0d actual=%0d expected=%0d",rows,sample_v3,expected);
            end else if(bass_row==0 && sample_v3!==sample_v1)
                $fatal(1,"formal V1 selection row %0d V3=%0d V1=%0d",rows,sample_v3,sample_v1);
            if(bass_row!=2 && (sample_v3>8191 || sample_v3 < -8192))
                $fatal(1,"amplitude bound row %0d",rows);
            checks=checks+2;rows=rows+1;
        end
        $fclose(fd);
        if(rows<10000) $fatal(1,"insufficient vectors");
        $display("PASS independent V3 oscillator rows=%0d checks=%0d",rows,checks);
        $finish;
    end
    initial begin #1000000000; $fatal(1,"oscillator test timeout");end
endmodule
