// M2 scoreboard: two independent display-control mailboxes, shared reset.
`timescale 1ns/1ps
module tb_visual_control_bridge;
    parameter integer VIDEO_HALF = 17;
    logic sys_clk=0, pixel_clk=0, video_clock_run=1, rst_n=0;
    always #10 sys_clk=~sys_clk;
    always #(VIDEO_HALF) if(video_clock_run) pixel_clk=~pixel_clk;
    logic src_mode_valid=0, src_score_valid=0, video_score_ready=1;
    wire src_mode_ready, mode_pulse, src_score_ready, video_score_valid;
    logic [97:0] source_packet='0;
    wire [97:0] destination_packet;
    wire source_reset_done, destination_reset_done;
    logic [97:0] expected[0:63];
    integer sent=0, received=0, mode_sent=0, mode_received=0, checks=0;
    logic prior_stall=0;
    logic [97:0] stalled_data;
    logic previous_mode_pulse=0;
    visual_control_bridge dut(
        .sys_clk(sys_clk),.pixel_clk(pixel_clk),.rst_n(rst_n),
        .src_mode_valid(src_mode_valid),.src_mode_ready(src_mode_ready),
        .video_mode_toggle_pulse(mode_pulse),
        .src_score_valid(src_score_valid),.src_score_ready(src_score_ready),
        .src_score_note_id(source_packet[97:82]),
        .src_score_note_number(source_packet[81:75]),
        .src_score_hit_frame(source_packet[74:43]),
        .src_score_duration_valid(source_packet[42]),
        .src_score_duration_frames(source_packet[41:10]),
        .src_score_velocity(source_packet[9:0]),
        .video_score_valid(video_score_valid),.video_score_ready(video_score_ready),
        .video_score_note_id(destination_packet[97:82]),
        .video_score_note_number(destination_packet[81:75]),
        .video_score_hit_frame(destination_packet[74:43]),
        .video_score_duration_valid(destination_packet[42]),
        .video_score_duration_frames(destination_packet[41:10]),
        .video_score_velocity(destination_packet[9:0]),
        .sys_reset_done(source_reset_done),.video_reset_done(destination_reset_done)
    );
    always @(posedge sys_clk or negedge rst_n) begin
        if(!rst_n) begin sent=0; mode_sent=0; end
        else if(source_reset_done) begin
            if(src_score_valid && src_score_ready) begin
                if(sent>=64) $fatal(1,"scoreboard overflow");
                expected[sent]=source_packet; sent=sent+1;
            end
            if(src_mode_valid && src_mode_ready) mode_sent=mode_sent+1;
        end
    end
    always @(posedge pixel_clk or negedge rst_n) begin
        if(!rst_n) begin
            received=0;mode_received=0;prior_stall=0;previous_mode_pulse=0;
        end else if(destination_reset_done) begin
            if(prior_stall && (!video_score_valid || destination_packet!==stalled_data))
                $fatal(1,"score payload changed while receiver stalled");
            prior_stall=video_score_valid && !video_score_ready;
            if(prior_stall) stalled_data=destination_packet;
            if(video_score_valid && video_score_ready) begin
                if(received>=sent || destination_packet!==expected[received])
                    $fatal(1,"98-bit packet mismatch/order/duplicate index=%0d",received);
                received=received+1;
            end
            if(mode_pulse) begin
                if(previous_mode_pulse) $fatal(1,"mode pulse lasted more than one destination cycle");
                mode_received=mode_received+1;
                if(mode_received>mode_sent) $fatal(1,"mode command duplicated");
            end
            previous_mode_pulse=mode_pulse;
        end
    end
    function automatic [97:0] packet(input integer i);
        // All fields vary, including top/bottom bits and both frame counters.
        packet={16'(16'h8140+i),7'(36+i%49),32'(32'hfedc0000+i*17),
                1'(i%2),32'(32'habcdef00+i*19),10'(1+i*31)};
    endfunction
    task automatic send_score(input logic [97:0] value);
        begin
            @(negedge sys_clk);source_packet=value;src_score_valid=1;
            do @(posedge sys_clk); while(!src_score_ready);
            @(negedge sys_clk);src_score_valid=0;source_packet=~value;
        end
    endtask
    task automatic send_mode;
        begin
            @(negedge sys_clk);src_mode_valid=1;
            do @(posedge sys_clk); while(!src_mode_ready);
            @(negedge sys_clk);src_mode_valid=0;
        end
    endtask
    task automatic reset_all;
        begin
            @(negedge sys_clk);rst_n=0;src_mode_valid=0;src_score_valid=0;
            repeat(3) @(negedge sys_clk);
            video_clock_run=1;video_score_ready=1;
            rst_n=1;wait(source_reset_done && destination_reset_done);
        end
    endtask
    initial begin
        #4_000_000;$fatal(1,"timeout half=%0d sent/recv=%0d/%0d modes=%0d/%0d",VIDEO_HALF,sent,received,mode_sent,mode_received);
    end
    initial begin
        #1;
        if(src_score_ready || src_mode_ready || video_score_valid || mode_pulse)
            $fatal(1,"reset published a transaction");
        reset_all();checks=checks+1;
        fork
            begin for(integer i=0;i<12;i=i+1) send_score(packet(i));end
            begin repeat(7) send_mode();end
        join
        wait(received==12 && mode_received==7);
        repeat(5) @(negedge pixel_clk);
        if(sent!=received || mode_sent!=mode_received) $fatal(1,"transfer count mismatch");
        checks=checks+1;

        // Score backpressure cannot block the independent mode channel.
        video_score_ready=0;send_score(packet(20));wait(video_score_valid);
        repeat(12) @(negedge pixel_clk);
        if(src_score_ready || received!=12 || destination_packet!==packet(20))
            $fatal(1,"backpressure did not hold packet and source busy");
        send_mode();wait(mode_received==8);checks=checks+1;
        video_score_ready=1;wait(received==13);wait(src_score_ready);checks=checks+1;

        // Destination clock may stop; accepted packets remain pending once.
        @(negedge pixel_clk);video_clock_run=0;
        send_score(packet(21));send_mode();
        repeat(15) @(negedge sys_clk);
        if(src_mode_ready || src_score_ready || received!=13 || mode_received!=8)
            $fatal(1,"destination stop lost source busy state");
        video_clock_run=1;wait(received==14 && mode_received==9);
        checks=checks+1;

        // Flush an in-flight packet and mode during shared reset/PLL loss.
        @(negedge pixel_clk);video_clock_run=0;
        wait(src_mode_ready && src_score_ready);
        send_score(packet(22));send_mode();
        @(negedge sys_clk);rst_n=0;
        #1;if(video_score_valid || mode_pulse || src_score_ready || src_mode_ready)
            $fatal(1,"asynchronous reset failed with stopped destination");
        reset_all();repeat(20) @(negedge pixel_clk);
        if(received!=0 || mode_received!=0 || video_score_valid || mode_pulse)
            $fatal(1,"old transaction replayed after shared reset");
        checks=checks+1;
        send_score(packet(30));send_mode();wait(received==1 && mode_received==1);
        repeat(10) @(negedge pixel_clk);
        if(sent!=1 || mode_sent!=1) $fatal(1,"reset did not establish clean epoch");
        checks=checks+1;

        // Reset while receiver owns valid but has not accepted the packet.
        video_score_ready=0;send_score(packet(31));wait(video_score_valid);
        reset_all();repeat(12) @(negedge pixel_clk);
        if(received!=0 || mode_received!=0 || video_score_valid)
            $fatal(1,"stalled destination packet survived reset");
        checks=checks+1;
        send_score(98'h3ffffffffffffffffffffffff);wait(received==1);
        send_score(98'd0);wait(received==2);checks=checks+1;
        $display("PASS visual_control_bridge: %0d scenarios, video_half=%0d ns, exact 98-bit score and once-only modes",checks,VIDEO_HALF);
        $finish;
    end
endmodule
