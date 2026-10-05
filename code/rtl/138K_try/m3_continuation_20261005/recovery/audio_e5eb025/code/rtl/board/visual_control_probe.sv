// M2 standalone score/mode mailbox physical probe. NEVER PROGRAM.
// 98 unconstrained synthetic data input pins are not a board interface.
`timescale 1ns/1ps
module visual_control_probe(
    input logic sys_clk, sys_rst_n,
    input logic [97:0] stimulus_data,
    output logic debug_tx
);
    wire serial_clk,pixel_clk,pll_lock;
    wire shared_rst_n=sys_rst_n && pll_lock;
    wire src_done,dst_done,score_ready,mode_ready,mode_pulse,score_valid;
    wire [97:0] received_score;
    logic [11:0] src_counter;
    logic [7:0] dst_counter;
    logic [97:0] observed;
    logic [6:0] bit_index;
    logic mode_state;
    wire source_score_valid=(src_counter==12'hfff) && src_done;
    wire source_mode_valid=(src_counter[4:0]==5'd31) && src_done;
    wire sink_ready=dst_counter[3];
    TMDS_PLL u_video_pll(.clkin(sys_clk),.lock(pll_lock),
        .clkout0(serial_clk),.clkout1(pixel_clk));
    always_ff @(posedge sys_clk or negedge shared_rst_n) begin
        if(!shared_rst_n) src_counter<='0;
        else src_counter<=src_counter+1'b1;
    end
    visual_control_bridge u_control(
        .sys_clk(sys_clk),.pixel_clk(pixel_clk),.rst_n(shared_rst_n),
        .src_mode_valid(source_mode_valid),.src_mode_ready(mode_ready),
        .video_mode_toggle_pulse(mode_pulse),
        .src_score_valid(source_score_valid),.src_score_ready(score_ready),
        .src_score_note_id(stimulus_data[97:82]),
        .src_score_note_number(stimulus_data[81:75]),
        .src_score_hit_frame(stimulus_data[74:43]),
        .src_score_duration_valid(stimulus_data[42]),
        .src_score_duration_frames(stimulus_data[41:10]),
        .src_score_velocity(stimulus_data[9:0]),
        .video_score_valid(score_valid),.video_score_ready(sink_ready),
        .video_score_note_id(received_score[97:82]),
        .video_score_note_number(received_score[81:75]),
        .video_score_hit_frame(received_score[74:43]),
        .video_score_duration_valid(received_score[42]),
        .video_score_duration_frames(received_score[41:10]),
        .video_score_velocity(received_score[9:0]),
        .sys_reset_done(src_done),.video_reset_done(dst_done)
    );
    always_ff @(posedge pixel_clk or negedge dst_done) begin
        if(!dst_done) begin
            observed<='0;bit_index<='0;dst_counter<='0;
            debug_tx<=0;mode_state<=0;
        end else begin
            dst_counter<=dst_counter+1'b1;
            if(score_valid && sink_ready) observed<=received_score;
            if(mode_pulse) mode_state<=~mode_state;
            bit_index<=(bit_index==7'd97)?7'd0:bit_index+1'b1;
            debug_tx<=observed[bit_index]^mode_state;
        end
    end
endmodule
