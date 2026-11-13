`timescale 1ns/1ps

module tb_shared_envelope_equivalence;
    localparam integer N=4;
    logic clk=0,rst_n=0;
    always #5 clk=~clk;

    logic event_start,sample_start;
    logic [N-1:0] note_on,note_off,timbres;
    logic [N*10-1:0] velocity;
    wire shared_busy,shared_done;
    wire [N*16-1:0] shared_env,reference_env;
    wire [N*3-1:0] shared_state,reference_state;
    integer checks=0;

    m2_polyphony_envelope_engine #(.N(N)) dut(
        .clk(clk),.rst_n(rst_n),.event_start(event_start),
        .note_on(note_on),.note_off(note_off),.velocity(velocity),
        .timbres(timbres),.sample_start(sample_start),
        .busy(shared_busy),.done(shared_done),
        .live_envelopes(shared_env),.live_states(shared_state));

    for(genvar g=0;g<N;g=g+1) begin:g_reference
        wire [15:0] piano_env,organ_env;
        wire [2:0] piano_state,organ_state;
        m1td_adsr_piano_envelope u_piano(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(sample_start),
            .note_on(note_on[g]&&event_start),
            .note_off(note_off[g]&&event_start),
            .velocity(velocity[10*g+:10]),
            .envelope_level(piano_env),.state_out(piano_state));
        organ_envelope #(.VELOCITY_ROM_FILE("rom/organ_velocity_gain_1024.mem")) u_organ(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(sample_start),
            .note_on(note_on[g]&&event_start),
            .note_off(note_off[g]&&event_start),
            .velocity(velocity[10*g+:10]),
            .envelope_level(organ_env),.state_out(organ_state));
        assign reference_env[16*g+:16]=timbres[g]?organ_env:piano_env;
        assign reference_state[3*g+:3]=timbres[g]?organ_state:piano_state;
    end

    task automatic wait_done;
        integer guard;
        begin
            guard=0;
            while(!shared_done && guard<256) begin
                @(posedge clk); #1; guard=guard+1;
            end
            if(!shared_done) $fatal(1,"Shared envelope timeout");
        end
    endtask

    task automatic apply_event(
        input logic [N-1:0] on_mask,
        input logic [N-1:0] off_mask
    );
        begin
            @(negedge clk);
            note_on=on_mask;note_off=off_mask;event_start=1;
            @(negedge clk);
            event_start=0;note_on=0;note_off=0;
            wait_done();
            @(posedge clk); #1;
            if(shared_env!==reference_env || shared_state!==reference_state)
                $fatal(1,"Event mismatch env shared=%h ref=%h state shared=%h ref=%h",
                    shared_env,reference_env,shared_state,reference_state);
        end
    endtask

    task automatic sample_and_compare;
        begin
            @(negedge clk);sample_start=1;
            @(negedge clk);sample_start=0;
            wait_done();
            @(posedge clk); #1;
            checks=checks+1;
            if(shared_env!==reference_env || shared_state!==reference_state)
                $fatal(1,"Sample %0d mismatch env shared=%h ref=%h state shared=%h ref=%h",
                    checks,shared_env,reference_env,shared_state,reference_state);
        end
    endtask

    initial begin
        event_start=0;sample_start=0;note_on=0;note_off=0;
        timbres=4'b1010;
        velocity={10'd896,10'd640,10'd384,10'd128};
        repeat(4) @(posedge clk);
        rst_n=1;
        while(shared_busy) @(posedge clk);
        repeat(2) @(posedge clk);

        // Mixed Piano/Organ attack, including low and high velocities.
        apply_event(4'b1111,4'b0000);
        repeat(300) sample_and_compare();

        // Mixed releases followed by a retrigger from non-zero levels.
        apply_event(4'b0000,4'b0011);
        repeat(80) sample_and_compare();
        velocity[9:0]=10'd1000;
        velocity[19:10]=10'd300;
        apply_event(4'b0011,4'b0000);

        // Cross the complete Piano decay boundary and exercise Organ sustain.
        repeat(5050) sample_and_compare();

        // Release all voices; this covers Organ's 1024-sample and Piano's
        // 4800-sample releases, including exact terminal samples.
        apply_event(4'b0000,4'b1111);
        repeat(4810) sample_and_compare();

        if(shared_env!==0 || reference_env!==0)
            $fatal(1,"Envelope did not return to zero");
        $display("SHARED_ENVELOPE_EQUIVALENCE_PASS checks=%0d",checks);
        $finish;
    end
endmodule
