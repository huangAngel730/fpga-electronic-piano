`timescale 1ns/1ps
module tb_shared_pitch_equivalence;
    localparam integer N=4;
    localparam integer SW=2;
    logic clk=0,rst_n=0,start=0;
    logic [N-1:0] note_on=0,occupied=0;
    logic [N*32-1:0] base_fcw=0;
    logic [N*12-1:0] bend=0,modulation=0;
    logic [N*5-1:0] pitch_range=0;
    wire start_ready,busy,done;
    wire [N*32-1:0] shared_fcw;
    wire [N-1:0] old_valid;
    wire [N*32-1:0] old_fcw;
    integer cases=0;

    always #5 clk=~clk;

    m2_polyphony_pitch_engine #(.N(N),.SW(SW)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.start_ready(start_ready),
        .busy(busy),.done(done),.note_on(note_on),.occupied(occupied),
        .base_fcw(base_fcw),.bend(bend),.modulation(modulation),
        .pitch_range(pitch_range),.fcw_values(shared_fcw));

    for(genvar i=0;i<N;i=i+1) begin:g_old
        m1td_pitch_mod_fcw_pipeline ref_pipe(
            .sys_clk(clk),.sys_rst_n(rst_n),
            .sample_enable(start && occupied[i]),.note_on(note_on[i]),
            .bend($signed(bend[12*i+:12])),
            .modulation(modulation[12*i+:12]),
            .pitch_range(pitch_range[5*i+:5]),
            .base_fcw(base_fcw[32*i+:32]),
            .fcw_out(old_fcw[32*i+:32]),.fcw_valid(old_valid[i]));
    end

    task automatic pulse_note_on(input logic [N-1:0] mask);
        begin
            @(negedge clk); note_on=mask;
            @(negedge clk); note_on=0;
        end
    endtask

    task automatic run_and_compare;
        integer timeout;
        begin
            while(!start_ready) @(negedge clk);
            start=1;
            @(negedge clk); start=0;
            timeout=0;
            while(!done && timeout<100) begin
                @(negedge clk); timeout=timeout+1;
            end
            if(!done) $fatal(1,"shared pitch timeout");
            for(integer i=0;i<N;i=i+1) begin
                if(occupied[i]) begin
                    if(shared_fcw[32*i+:32]!==old_fcw[32*i+:32])
                        $fatal(1,"pitch mismatch case=%0d slot=%0d shared=%h old=%h",
                            cases,i,shared_fcw[32*i+:32],old_fcw[32*i+:32]);
                end else if(shared_fcw[32*i+:32]!==base_fcw[32*i+:32]) begin
                    $fatal(1,"inactive pitch mismatch case=%0d slot=%0d shared=%h base=%h",
                        cases,i,shared_fcw[32*i+:32],base_fcw[32*i+:32]);
                end
            end
            cases=cases+1;
        end
    endtask

    initial begin
        repeat(4) @(negedge clk);
        rst_n=1;
        occupied=4'b1111;
        for(integer i=0;i<N;i=i+1) begin
            base_fcw[32*i+:32]=32'd12000000+i*32'd3100000;
            bend[12*i+:12]=$signed(i*137-180);
            modulation[12*i+:12]=12'(i*211+17);
            pitch_range[5*i+:5]=5'(2+i*3);
        end
        pulse_note_on(4'b1111);

        // Repeated frames exercise independent LFO phase progression.
        for(integer frame=0;frame<48;frame=frame+1) begin
            for(integer i=0;i<N;i=i+1) begin
                bend[12*i+:12]=$signed(((frame*19+i*101)%1200)-600);
                modulation[12*i+:12]=12'((frame*73+i*211)%4096);
            end
            run_and_compare();
        end

        // Sparse occupancy must hold base FCW and must not advance inactive LFOs.
        occupied=4'b0101;
        repeat(8) run_and_compare();
        pulse_note_on(4'b0100);
        repeat(8) run_and_compare();
        occupied=4'b1111;
        repeat(8) run_and_compare();

        if(cases!=72) $fatal(1,"unexpected case count %0d",cases);
        $display("SHARED_PITCH_EQUIVALENCE_PASS cases=%0d",cases);
        $finish;
    end
endmodule
