// E2 isolated 40->25 MHz, historical source replay + separately labelled fixtures.
// No model reads DUT memory/state. Oracle bins are independent Python products.
`timescale 1ns/1ps
module tb_pro_fixed_left_waveform;
    reg audio_clk=0, pixel_clk=0, pixel_run=1;
    always #12.5 audio_clk=~audio_clk;
    initial begin #7; forever begin #20; if (pixel_run) pixel_clk=~pixel_clk; end end
    reg audio_rst_n=0, display_rst_n=0;
    reg requested_load=0;
    reg signed [23:0] play_left=0, play_right=0;
    integer catalogue_id=-1, fault=0;
    reg bad_backpressure_active=0;
    wire [15:0] queue_level;
    wire actual_load = requested_load && !(fault==5 && bad_backpressure_active && queue_level>=32);
    reg [15:0] x=0,y=0;
    reg de=1, frame_start=0, enabled=1;
    wire mask, trace_valid, waveform_rst_n, restart, valid;
    wire [7:0] r,g,b;
    wire [31:0] gaps, windows, seq, observed_seq, drops;
    wire signed [23:0] left,right,observed_left,observed_right;
    wire observed_valid,enqueued,dropped,src_up,pix_up;
    wire bad_frame = frame_start || (valid && seq==4096);
    wire bad_valid = valid && seq!=1000;
    m3_pro_fixed_left_waveform dut (
        .audio_clk(audio_clk), .pixel_clk(pixel_clk), .audio_rst_n(audio_rst_n),
        .display_rst_n(display_rst_n), .audio_frame_load(actual_load),
        .audio_play_left(play_left), .audio_play_right(play_right),
        .pixel_x(x), .pixel_y(y), .data_enable(de), .frame_start(frame_start),
        .waveform_enable(enabled), .waveform_mask(mask), .waveform_r(r), .waveform_g(g),
        .waveform_b(b), .trace_valid(trace_valid), .display_gap_count(gaps),
        .window_drop_count(windows), .waveform_rst_n(waveform_rst_n),
        .stream_restart(restart), .sample_valid(valid), .sample_seq(seq),
        .sample_left(left), .sample_right(right), .observed_valid(observed_valid),
        .observed_seq(observed_seq), .observed_left(observed_left),
        .observed_right(observed_right), .observation_enqueued(enqueued),
        .observation_dropped(dropped), .observation_queue_level(queue_level),
        .observation_drop_count(drops), .source_reset_done(src_up), .pixel_reset_done(pix_up)
    );
    reg [63:0] catalogue[0:14240];
    reg [15:0] golden[0:2559];
    reg accepted[0:14240];
    integer requested=0, observed=0, delivered=0, drop_events=0, restarts=0;
    integer front=-1, pixels_checked=0, scans=0, last_delivered=-1;
    integer phase=0, j, s, lo, hi, idx;
    reg [24:0] p0=0,p1=0,p2=0;
    reg [191:0] pixel_reason="PIXEL_REFERENCE";
    reg [24:0] pixel_value;
    function [24:0] expected_pixel;
        input integer px,py;
        reg [23:0] rgb;
        integer minimum,maximum,bin_index;
        begin
            if (!de || !enabled || px<64 || px>575 || py<64 || py>319)
                expected_pixel=0;
            else begin
                rgb=24'h081020;
                if (py==191) rgb=24'h404040;
                if (front>=0) begin
                    bin_index=front*512+px-64;
                    minimum=golden[bin_index][15:8];
                    maximum=golden[bin_index][7:0];
                    if (minimum>=128) minimum=minimum-256;
                    if (maximum>=128) maximum=maximum-256;
                    if (py>=191-maximum && py<=191-minimum) rgb=24'h00e0ff;
                end
                expected_pixel={1'b1,rgb};
            end
        end
    endfunction
    task die;
        input [255:0] reason;
        begin
            $display("FIRST_REJECT %0s t=%0t phase=%0d requested=%0d observed=%0d delivered=%0d gaps=%0d drops=%0d windows=%0d",reason,$time,phase,requested,observed,delivered,gaps,drops,windows);
            $fatal(1,"E2_REJECT");
        end
    endtask
    always @(posedge audio_clk) begin
        if (audio_rst_n) begin
            if (requested_load) begin
                requested=requested+1;
                $display("A %0t %0d %0d %0d %0d",$time,catalogue_id,play_left,play_right,actual_load);
                if (!actual_load) die("AUDIO_DISPLAY_BACKPRESSURE");
            end
            // Observer outputs from the preceding audio edge, before NBA.
            if (observed_valid) begin
                if (observed_seq!==observed || observed_seq>=14241) die("OBSERVER_SEQUENCE");
                if ({observed_left,observed_right}!==catalogue[observed_seq][63:16]) die("OBSERVER_ATOMIC_PCM");
                if (enqueued==dropped) die("OBSERVATION_DISPOSITION");
                accepted[observed_seq]=enqueued;
                $display("O %0t %0d %0d %0d %0d %0d %0d",$time,observed_seq,observed_left,observed_right,enqueued,dropped,queue_level);
                observed=observed+1;
                if (dropped) drop_events=drop_events+1;
            end
        end
    end
    always @(posedge pixel_clk) begin
        if (waveform_rst_n) begin
            if (restart) begin
                restarts=restarts+1;
                $display("R %0t %0d",$time,restarts);
                if (valid) die("RESTART_OVERLAP");
            end
            if (valid) begin
                if (seq>=14241 || !accepted[seq] || seq<=last_delivered) die("DELIVERY_SEQUENCE_OR_EPOCH");
                if ({left,right}!==catalogue[seq][63:16]) die("DELIVERY_ATOMIC_PCM");
                $display("D %0t %0d %0d %0d",$time,seq,left,right);
                delivered=delivered+1;
                last_delivered=seq;
            end
            if (dut.render_valid) $display("I %0t %0d %0d %0d",$time,dut.render_seq,dut.render_left,dut.render_right);
        end
        if (!waveform_rst_n) begin p0=0;p1=0;p2=0; end
        else begin p2=p1;p1=p0;p0=expected_pixel(x,y); end
        #1;
        pixel_value={mask,r,g,b};
        if (pixel_value!==p2) begin
            $display("PIXEL_DIFFERENCE t=%0t x_now=%0d y_now=%0d front=%0d expected=%07x actual=%07x",$time,x,y,front,p2,pixel_value);
            die(pixel_reason);
        end
        pixels_checked=pixels_checked+1;
        if (phase<6 && gaps!=0) die("SAMPLE_SEQ_GAP");
    end
    task send_range;
        input integer first,last;
        integer k,delay_cycles;
        begin
            for (k=first;k<last;k=k+1) begin
                delay_cycles=catalogue[k][15:0];
                if (k==first) @(negedge audio_clk);
                else repeat(delay_cycles-1) @(negedge audio_clk);
                catalogue_id=k;
                {play_left,play_right}=catalogue[k][63:16];
                requested_load=1;
                @(negedge audio_clk); requested_load=0;
            end
        end
    endtask
    task drain;
        begin repeat(300) @(negedge pixel_clk); end
    endtask
    task publish;
        input integer snapshot;
        begin
            @(negedge pixel_clk);front=snapshot;frame_start=1;
            @(negedge pixel_clk);frame_start=0;
            repeat(3) @(negedge pixel_clk);
            if (!trace_valid) die("PUBLISH_TRACE_MISSING");
            $display("P %0t %0d %0d %0d %0d",$time,snapshot,delivered,gaps,windows);
        end
    endtask
    task scan;
        integer sx,sy;
        begin
            for (sy=64;sy<=319;sy=sy+1)
                for (sx=64;sx<=575;sx=sx+1) begin
                    @(negedge pixel_clk);x=sx;y=sy;
                end
            @(negedge pixel_clk);x=63;y=64;
            @(negedge pixel_clk);x=576;y=64;
            @(negedge pixel_clk);x=64;y=63;
            @(negedge pixel_clk);x=64;y=320;
            @(negedge pixel_clk);x=575;y=319;
            @(negedge pixel_clk);x=64;y=191;de=0;
            @(negedge pixel_clk);de=1;enabled=0;
            @(negedge pixel_clk);de=0;enabled=0;
            @(negedge pixel_clk);x=0;y=0;de=1;enabled=1;
            repeat(3) @(negedge pixel_clk);
            scans=scans+1;
            $display("S %0t %0d %0d %0d",$time,scans,front,pixels_checked);
        end
    endtask
    initial begin
        if (!$value$plusargs("FAULT=%d",fault)) fault=0;
        $readmemh("catalogue.mem",catalogue);
        $readmemh("golden.mem",golden);
        for (j=0;j<14241;j=j+1) accepted[j]=0;
        if (fault==1) force dut.render_left=dut.sample_right;
        if (fault==2) force dut.render_frame_start=bad_frame;
        if (fault==3) force dut.render_valid=bad_valid;
        repeat(10) @(negedge audio_clk);
        audio_rst_n=1;display_rst_n=1;
        drain();
        if (restarts!=1 || trace_valid || requested!=0) die("INITIAL_RESET_RESTART");
        phase=1;
        fork
            send_range(0,5849);
            begin
                wait(delivered>=2047);
                @(negedge pixel_clk);frame_start=1;
                @(negedge pixel_clk);frame_start=0;
                if (trace_valid) die("WINDOW_2047_PUBLISHED");
                $display("CHECK 2047_no_publish");
                wait(delivered>=2048); publish(0); scan();
                pixel_reason="WINDOW_FRAME_TEAR";
                wait(delivered>=4097); scan();
                pixel_reason="PIXEL_REFERENCE";
            end
        join
        drain();
        if (observed!=5849 || delivered!=5849 || drops!=0 || windows!=0) die("REAL_REPLAY_COUNTS");
        publish(1);scan();
        $display("CHECK historical_5849_exact_A_relative_cadence");
        phase=2;
        @(negedge pixel_clk);x=0;y=0;
        if (fault==4) force dut.render_rst_n=1'b1;
        display_rst_n=0;front=-1;
        #1;if (trace_valid) die("RESET_TRACE_STALE");
        repeat(20) @(negedge audio_clk);
        if (observed!=5849 || audio_rst_n!=1 || drops!=0) die("DISPLAY_RESET_AUDIO_CORRUPTION");
        display_rst_n=1;drain();
        if (restarts!=2 || trace_valid || delivered!=5849) die("DISPLAY_RESET_RESTART");
        phase=3;
        send_range(5849,7897);drain();publish(2);scan();
        $display("CHECK signed24_extrema_quantization_left_only");
        phase=4;
        send_range(7897,9945);send_range(9945,11993);drain();
        if (windows!=1 || gaps!=0 || drops!=0) die("PENDING_REPLACEMENT_COUNT");
        pixel_reason="WINDOW_FRAME_TEAR";scan();pixel_reason="PIXEL_REFERENCE";
        publish(3);scan();
        $display("CHECK pending_replace_front_stable");
        phase=5;
        @(negedge pixel_clk);pixel_run=0;
        bad_backpressure_active=1;
        send_range(11993,12193);
        repeat(10) @(negedge audio_clk);
        if (observed!=12193 || requested!=12193 || drop_events!=167 || drops!=167 || queue_level!=32)
            die("PIXEL_PAUSE_FIFO32_PLUS_MAILBOX");
        $display("CHECK pixel_pause_all200_audio_adopted_167_observation_drops");
        pixel_run=1;drain();
        if (delivered!=12026 || gaps!=0 || last_delivered!=12025) die("PAUSE_RETAINED_33");
        phase=6;
        send_range(12193,12197);drain();
        if (gaps!=1 || !trace_valid) die("GAP_ABORT_KEEP_FRONT");
        scan();
        send_range(12197,14241);drain();
        if (observed!=14241 || requested!=14241 || delivered!=14074 || gaps!=1 || windows!=1 || drops!=167)
            die("END_LEDGER_COUNTS");
        publish(4);scan();
        if (queue_level!=0 || !trace_valid || restarts!=2) die("END_UNDRAINED_OR_STALE");
        $display("CHECK gap_aborts_partial_current_sample_starts_recovery");
        if (fault!=0) die("FAULT_ESCAPED");
        $display("PASS E2 requested=%0d observed=%0d delivered=%0d drops=%0d gaps=%0d windows=%0d restarts=%0d scans=%0d pixels=%0d",requested,observed,delivered,drops,gaps,windows,restarts,scans,pixels_checked);
        $finish;
    end
    initial begin #300000000;die("SIM_TIME_LIMIT_300MS");end
endmodule
