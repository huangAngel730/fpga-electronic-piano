// T025 independent chain: synthetic four-voice PCM -> mixer -> registered
// generation+clip -> real frame buffer handshake -> real clip counter ->
// seven-field STAT UART bytes. No electronic_piano_top or hardware claims.
`timescale 1ns/1ps
module tb_t025_stat_chain;
    logic clk=0;
    always #5 clk=~clk;
    logic rst_n=1, frame_tick=0, calc_ready=1, result_valid=0;
    logic [31:0] result_req_id=0, sample_req_id, pcm_req_id;
    logic [95:0] voices_left=0,voices_right=0;
    wire signed [23:0] result_left,result_right,pcm_left,pcm_right;
    wire signed [23:0] play_left,play_right;
    wire clip_left,clip_right,result_clip_any,pcm_clip_any;
    wire result_ready,pcm_valid,pcm_ready,sample_req,pending_valid;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count;
    wire [31:0] audio_underrun,clip_count;
    wire tx, report_busy, rx_valid, frame_error, rx_busy;
    wire [7:0] rx_data;
    integer checks=0, lines=0;
    string received="", expected_first, expected_second;
    localparam logic [95:0] POS={4{24'd2097152}};
    localparam logic [95:0] NEG={4{24'sh9fffff}};

    pcm_mixer_4voice mixer (
        .voices_left(voices_left),.voices_right(voices_right),
        .mixed_left(result_left),.mixed_right(result_right),
        .clip_left(clip_left),.clip_right(clip_right),.clip_any(result_clip_any)
    );
    pcm_result_hold hold_dut (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .current_req_id(sample_req_id),.result_valid(result_valid),
        .result_ready(result_ready),.result_req_id(result_req_id),
        .result_left(result_left),.result_right(result_right),
        .result_clip_any(result_clip_any),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .pcm_req_id(pcm_req_id),.pcm_left(pcm_left),.pcm_right(pcm_right),
        .pcm_clip_any(pcm_clip_any)
    );
    pcm_frame_buffer buffer_dut (
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),.pcm_req_id(pcm_req_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),
        .play_left(play_left),.play_right(play_right),
        .pending_valid(pending_valid),
        .audio_frame_count(audio_frame_count),.pcm_request_count(pcm_request_count),
        .pcm_commit_count(pcm_commit_count),.audio_underrun(audio_underrun)
    );
    pcm_clip_counter clip_dut (
        .clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),
        .pcm_ready(pcm_ready),.clip_any(pcm_clip_any),.clip_count(clip_count)
    );
    uart_status_reporter #(
        .CLK_HZ(1_000_000),.BAUD(100_000),.REPORT_CYCLES(30_000),
        .CLIP_COUNT_VALID(1'b1)
    ) status (
        .clk(clk),.rst_n(rst_n),.active_voice_count(32'd4),
        .clip_count(clip_count),.event_fifo_level(32'd0),
        .event_fifo_high_watermark(32'd0),.event_fifo_overflow(32'd0),
        .audio_underrun(audio_underrun),.max_processing_cycles(32'd9),
        .tx(tx),.report_busy(report_busy)
    );
    uart_rx #(.CLK_HZ(1_000_000),.BAUD(100_000)) monitor (
        .clk(clk),.rst_n(rst_n),.rx(tx),.rx_data(rx_data),
        .rx_valid(rx_valid),.frame_err(frame_error),.rx_busy(rx_busy)
    );
    task automatic check(input logic ok,input string msg);
        checks++;
        if(ok!==1'b1)$fatal(1,"FAIL STAT chain %s clip=%0d commit=%0d id=%0d",
                            msg,clip_count,pcm_commit_count,sample_req_id);
    endtask
    task automatic frame;
        @(negedge clk);frame_tick=1;
        @(posedge clk);#1;
        @(negedge clk);frame_tick=0;
    endtask
    task automatic send(input integer req,input logic [95:0] left,right);
        @(negedge clk);
        result_req_id=req;voices_left=left;voices_right=right;result_valid=1;
        #1;check(result_ready,"ready for matching generation");
        @(posedge clk);#1;
        @(negedge clk);result_valid=0;
        #1;check(pcm_valid && pcm_req_id==req,"PCM held with request ID");
        @(posedge clk);#1;
        @(negedge clk);
    endtask

    always @(posedge clk) if(rst_n && rx_valid)begin
        if(frame_error)$fatal(1,"STAT UART frame error");
        received={received,rx_data};
        if(rx_data==8'h0a)begin
            if(lines==0)begin
                if(received!=expected_first)$fatal(1,"STAT first snapshot mismatch: %s",received);
                check(clip_count==3,"first UART line remained snapshot despite later clip");
            end else if(lines==1)begin
                if(received!=expected_second)$fatal(1,"STAT second snapshot mismatch: %s",received);
            end else $fatal(1,"Unexpected extra status line");
            checks++;
            lines++;
            received="";
        end
    end

    initial begin
        expected_first={
            "STAT active_voice_count=0x00000004 clip_count=0x00000002",
            " event_fifo_level=0x00000000 event_fifo_high_watermark=0x00000000",
            " event_fifo_overflow=0x00000000 audio_underrun=0x00000000",
            " max_processing_cycles=0x00000009",8'h0d,8'h0a};
        expected_second={
            "STAT active_voice_count=0x00000004 clip_count=0x00000003",
            " event_fifo_level=0x00000000 event_fifo_high_watermark=0x00000000",
            " event_fifo_overflow=0x00000000 audio_underrun=0x00000000",
            " max_processing_cycles=0x00000009",8'h0d,8'h0a};
        #1;rst_n=0;
        repeat(4)@(negedge clk);
        check(tx===1'b1 && clip_count==0 && pcm_commit_count==0,"reset status");
        rst_n=1;
        frame();send(1,POS,0);
        check(clip_count==1 && pcm_commit_count==1,"left clip committed");
        frame();send(2,0,NEG);
        check(clip_count==2 && pcm_commit_count==2,"right clip committed");
        wait(report_busy);
        check(clip_count==2 && pcm_commit_count==2,"first snapshot taken at two clips");
        frame();send(3,POS,NEG);
        check(clip_count==3 && pcm_commit_count==3,"both channels clip counts once");
        wait(lines==2);
        check(expected_first.len()==213 && received.len()==0,"complete ASCII CRLF line");
        $display("PASS tb_t025_stat_chain lines=%0d checks=%0d commits=%0d clips=%0d",
                 lines,checks,pcm_commit_count,clip_count);
        $finish;
    end
    initial begin #1_200_000;$fatal(1,"STAT chain timeout lines=%0d",lines);end
endmodule
