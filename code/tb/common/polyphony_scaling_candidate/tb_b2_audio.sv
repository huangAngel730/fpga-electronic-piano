`timescale 1ns/1ps
`ifndef B2_N
`define B2_N 4
`endif
`ifndef B2_RESPONSE
`define B2_RESPONSE 1
`endif
`ifndef B2_LONG
`define B2_LONG 0
`endif
module tb_b2_audio;
    localparam integer N=`B2_N, RESP=`B2_RESPONSE, LONG=`B2_LONG;
    logic clk=0,rst_n=0,cancel=0,events_valid=0,request_valid=0,result_ready=1;
    always #12.5 clk=~clk; // independent 40MHz candidate clock
    logic [N-1:0] note_on=0,note_off=0,occupied=0;
    logic [N*10-1:0] velocity=0;
    logic [N*32-1:0] base_fcw=0,generations=0;
    logic [N*12-1:0] bend=0,modulation=0;
    logic [N*5-1:0] pitch_range=0;
    logic [N*4-1:0] sources=0,channels=0;
    logic [31:0] request_id=32'hfffffffc;
    wire events_ready,request_ready,result_valid,advance_pulse,engine_empty,lane_valid;
    wire [31:0] result_id,lane_phase,lane_fcw;
    wire [N*4-1:0] result_sources,result_channels;
    wire [N*32-1:0] result_generations,computed_fcw;
    wire signed [23:0] pcm_left,pcm_right,lane_pcm;
    wire clipped,deadline_missed;
    wire [N-1:0] completed_mask;
    wire [$clog2(N)-1:0] lane_slot;
    wire signed [15:0] lane_wave;
    wire [15:0] lane_envelope;
    wire [1:0] lane_table;
    wire [N*16-1:0] live_envelopes;
    wire [N*3-1:0] live_states;
    b2_audio_backend #(.N(N),.WAVE_RESPONSE_CYCLES(RESP)) dut(.*);
    integer cycle=0,requests=0,events=0,advances=0,lanes=0,outputs=0,cancels=0;
    integer k,f,start_cycle,watchdog;
    logic [N-1:0] captured_occupied;
    logic [N*4-1:0] saved_sources,saved_channels;
    logic [N*32-1:0] saved_generations,saved_base;
    logic [N*12-1:0] saved_bend,saved_mod;
    logic [N-1:0] saved_occupied;
    logic held_last=0;
    logic [32+24+24+1+1+N+N*40-1:0] last_result;
    wire [32+24+24+1+1+N+N*40-1:0] result_tuple={result_id,pcm_left,pcm_right,
        clipped,deadline_missed,completed_mask,result_sources,result_channels,result_generations};
    wire [N*16-1:0] reference_waves;
    wire [N*24-1:0] reference_pcm;
    wire [N*32-1:0] reference_fcw;
    wire [N-1:0] reference_pitch_valid;
    generate if(N==4) begin:g_frozen_reference
        for(genvar j=0;j<N;j=j+1) begin:g_voice
            pitch_mod_fcw_pipeline original_pitch(
                .sys_clk(clk),.sys_rst_n(rst_n),
                .sample_enable(request_valid && request_ready && occupied[j]),
                .note_on(events_valid && events_ready && note_on[j]),
                .bend($signed(bend[j*12+:12])),.modulation(modulation[j*12+:12]),
                .pitch_range(pitch_range[j*5+:5]),.base_fcw(base_fcw[j*32+:32]),
                .fcw_out(reference_fcw[j*32+:32]),.fcw_valid(reference_pitch_valid[j]));
            wire [31:0] ref_input=engine_empty ? base_fcw[j*32+:32] :
                captured_occupied[j] ? reference_fcw[j*32+:32] : saved_base[j*32+:32];
            piano_dds_oscillator original_dds(
                .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(advance_pulse),
                .note_on(events_valid && events_ready && note_on[j]),
                .velocity(velocity[j*10+:10]),.fcw(ref_input),.wt_sample(reference_waves[j*16+:16]));
            voice_gain_q15_candidate original_gain(
                .wave_sample($signed(reference_waves[j*16+:16])),
                .envelope(live_envelopes[j*16+:16]),.sample_out(),.pcm_out(reference_pcm[j*24+:24]));
        end
    end endgenerate
    always @(posedge clk) begin
        cycle=cycle+1;
        if(rst_n) begin
            if(events_valid && events_ready) begin
                events=events+1;
                $display("E %0d %h %h %h %h",cycle,note_on,note_off,velocity,base_fcw);
            end
            if(request_valid && request_ready) begin
                requests=requests+1;captured_occupied=occupied;saved_base=base_fcw;
                $display("C %0d %h %h %h %h %h %h %h %h %h",cycle,request_id,
                    occupied,base_fcw,bend,modulation,pitch_range,sources,channels,generations);
            end
            if(advance_pulse) begin
                advances=advances+1;
                if(N==4) for(integer a=0;a<N;a=a+1)
                    if(captured_occupied[a] && computed_fcw[a*32+:32]!==reference_fcw[a*32+:32])
                        $fatal(1,"CHECK_PITCH_FROZEN");
                $display("A %0d %h",cycle,result_id);
            end
            if(cancel) begin cancels=cancels+1;$display("X %0d",cycle);end
            if(held_last && !cancel && (!result_valid || result_tuple!==last_result))
                $fatal(1,"CHECK_OUTPUT_BACKPRESSURE_STABILITY");
            held_last=result_valid && !result_ready && !cancel;last_result=result_tuple;
            if(result_valid && result_ready && !cancel) begin
                if(completed_mask!=={N{1'b1}}) $fatal(1,"CHECK_ALL_VOICES");
                outputs=outputs+1;
                $display("O %0d %h %0d %0d %0d %0d %h %h %h %h",cycle,result_id,
                    pcm_left,pcm_right,clipped,deadline_missed,completed_mask,
                    result_sources,result_channels,result_generations);
            end
            #1;
            if(lane_valid) begin
                lanes=lanes+1;
                if(N==4 && lane_wave!==$signed(reference_waves[16*lane_slot+:16]))
                    $fatal(1,"CHECK_WAVE_FROZEN");
                if(N==4 && lane_pcm!==(captured_occupied[lane_slot] ?
                    $signed(reference_pcm[24*lane_slot+:24]) : 24'sd0))
                    $fatal(1,"CHECK_GAIN_FROZEN");
                $display("L %0d %h %0d %h %0d %h %0d %0d %0d %0d",cycle,result_id,lane_slot,
                    lane_phase,lane_table,lane_fcw,lane_wave,lane_envelope,lane_pcm,
                    live_states[3*lane_slot+:3]);
            end
        end
    end
    task automatic reset_domain;
        @(negedge clk);rst_n=0;request_valid=0;events_valid=0;cancel=0;
        repeat(4) @(negedge clk);
        $display("R %0d",cycle);held_last=0;rst_n=1;
    endtask
    task automatic send_event(input logic [N-1:0] ons,input logic [N-1:0] offs);
        @(negedge clk);note_on=ons;note_off=offs;events_valid=1;
        while(!events_ready) @(negedge clk);
        @(negedge clk);events_valid=0;note_on=0;note_off=0;
    endtask
    task automatic launch;
        @(negedge clk);request_valid=1;
        while(!request_ready) @(negedge clk);
        @(posedge clk);#2;start_cycle=cycle;
        @(negedge clk);request_valid=0;request_id=request_id+1'b1;
    endtask
    task automatic await_idle;
        watchdog=0;
        while(!engine_empty) begin
            @(negedge clk);watchdog=watchdog+1;
            if(watchdog>1600) $fatal(1,"CHECK_FINITE_BACKEND_DRAIN_OR_RESULT");
        end
    endtask
    task automatic do_frame;
        launch();
        // Change live inputs AFTER admission: output must still name the old
        // complete snapshot; no accidental dependence on pending caller input.
        saved_sources=sources;saved_channels=channels;saved_generations=generations;
        saved_bend=bend;saved_mod=modulation;saved_occupied=occupied;
        sources=~sources;channels=~channels;generations=~generations;
        bend=~bend;modulation=~modulation;occupied=~occupied;
        repeat(12) @(negedge clk);
        sources=saved_sources;channels=saved_channels;generations=saved_generations;
        bend=saved_bend;modulation=saved_mod;occupied=saved_occupied;
        await_idle();
        // Consecutive ordinary launches are separated by 833 clocks. Slow
        // profile is explicitly late; it never skips a voice to recover time.
        while(cycle<start_cycle+831) @(negedge clk);
    endtask
    task automatic cancel_at(input integer age_to_cancel);
        launch();
        repeat(age_to_cancel-1) @(negedge clk);
        cancel=1;@(negedge clk);cancel=0;await_idle();
    endtask
    initial begin
        $display("B2 %0d %0d %0d",N,RESP,LONG);
        for(k=0;k<N;k=k+1) begin
            velocity[10*k+:10]= k%4==0 ? 255 : k%4==1 ? 256 : k%4==2 ? 512 : 1023;
            base_fcw[32*k+:32]= N==4 ? (k==0 ? 32'd39370534 : k==1 ? 32'd134217728 :
                k==2 ? 32'd268435457 : 32'd536870913) : 32'd39370534;
            pitch_range[5*k+:5]=2;
            sources[4*k+:4]=4'(k);channels[4*k+:4]=4'(k/16);
            generations[32*k+:32]=32'hffffffff;
        end
        reset_domain();
        repeat(8) do_frame(); // legal all-unoccupied silence, no blacklist
        occupied={N{1'b1}};send_event({N{1'b1}},0);
        if(RESP<32) begin
            cancel_at(3); // LFO launch happened, no DDS tick yet
            cancel_at(10); // DDS/ADSR advanced; cancelled token must not roll back
            cancel_at(18); // actual ROM/render work can already be in flight
            result_ready=0;launch();
            watchdog=0;
            while(!result_valid) begin @(negedge clk);watchdog=watchdog+1;
                if(watchdog>833) $fatal(1,"CHECK_RESULT_BOUND");end
            repeat(8) @(negedge clk);cancel=1;@(negedge clk);cancel=0;
            result_ready=1;await_idle();
            // Whole-domain reset during an in-flight pitch token, then recover.
            launch();repeat(2) @(negedge clk);reset_domain();
            send_event({N{1'b1}},0);
        end
        for(f=0;f<(LONG ? 10220 : RESP>=32 ? 8 : 96);f=f+1) begin
            if(f==20) begin
                velocity[9:0]=256;generations[31:0]=generations[31:0]+1'b1;
                send_event({{(N-1){1'b0}},1'b1},0);
            end
            if(f==100) begin
                for(k=0;k<N;k=k+1) begin
                    bend[12*k+:12]= k%2 ? 12'd2047 : 12'h800;
                    modulation[12*k+:12]=4095;pitch_range[5*k+:5]= k%2 ? 24 : 0;
                end
            end
            if(f==5400) send_event(0,{N{1'b1}});
            do_frame();
        end
        // Final reset must clear continuous DSP state as well as output tags.
        reset_domain();occupied=0;repeat(2) do_frame();
        $display("END %0d %0d %0d %0d %0d %0d %0d",cycle,requests,events,advances,lanes,outputs,cancels);
        $finish;
    end
    initial begin #500000000;$fatal(1,"TB_WATCHDOG");end
endmodule
