`timescale 1ns/1ps
// Deliberate M1 public-port STUB. Never claim M1 timbre/delay math from this TB.
module m1td_timbre_delay_chain (
    input logic clk,rst_n,event_valid,frame_tick,sample_req,
    input logic [63:0] event_data,
    input logic [31:0] sample_req_id,
    output wire event_ready,calc_ready,
    input logic config_valid,
    output wire config_ready,
    input logic config_enable,
    input logic [15:0] config_delay_samples,
    input logic [14:0] config_dry_gain,config_wet_gain,config_feedback,
    output wire result_valid,
    input logic result_ready,
    output logic [31:0] result_id,
    output logic signed [23:0] result_left,result_right,
    output logic clipped_left,clipped_right,
    output wire upstream_clipped_left,upstream_clipped_right,
    output wire effect_clipped_left,effect_clipped_right,
    output wire feedback_clipped_left,feedback_clipped_right,
    output logic [31:0] active_voice_count
);
    logic held,configured;
    assign event_ready=rst_n;
    assign calc_ready=rst_n && !held;
    assign config_ready=rst_n && !held && !frame_tick;
    assign result_valid=rst_n && held && !frame_tick && result_id==sample_req_id;
    assign upstream_clipped_left=clipped_left;
    assign upstream_clipped_right=clipped_right;
    assign effect_clipped_left=1'b0;
    assign effect_clipped_right=1'b0;
    assign feedback_clipped_left=1'b0;
    assign feedback_clipped_right=1'b0;
    wire [2:0] event_type=event_data[63:61];
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin held<=0;configured<=0;active_voice_count<=0;
            result_id<=0;result_left<=0;result_right<=0;
            clipped_left<=0;clipped_right<=0;end
        else begin
            if(config_valid && config_ready)configured<=config_enable;
            if(event_valid && event_ready && event_type==0)active_voice_count<=1;
            if(frame_tick)held<=0;
            else if(result_valid && result_ready)held<=0;
            else if(sample_req && calc_ready)begin
                held<=1;result_id<=sample_req_id;
                result_left<=active_voice_count ? 24'sd131072:24'sd0;
                result_right<=active_voice_count ? -24'sd65536:24'sd0;
                clipped_left<=0;clipped_right<=0;
            end
        end
    end
endmodule

module tb_m2_m1td_board_contract;
    reg sys_clk=0,sys_rst_n=0,midi_rx=1;
    reg [1:0] key_n=2'b11;
    always #10 sys_clk=~sys_clk;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,tmds_clk_p,tmds_clk_n;
    wire [2:0] tmds_data_p,tmds_data_n;
    GSR GSR(.GSRI(1'b1));
    m2_fourvoice_timbre_delay_board_top dut(.*);
    integer accepted=0,commits=0,nonzero=0,serial_ones=0,frames=0,config_count=0;
    always @(posedge dut.core_clk) if(dut.rst_sync_n)begin
        if(dut.shared_event_valid && dut.shared_event_ready)accepted=accepted+1;
        if(dut.g_polyphonic.m1_config_pending && dut.g_polyphonic.m1_config_ready)config_count=config_count+1;
        if(dut.g_polyphonic.m1_commit)begin
            commits=commits+1;
            if(dut.produced_left!=0 || dut.produced_right!=0)nonzero=nonzero+1;
        end
        if(dut.i2s_frame_tick)frames=frames+1;
    end
    always @(posedge i2s_bclk)if(sys_rst_n && pa_en===0 && i2s_din===1)serial_ones=serial_ones+1;
    task automatic midi_byte(input logic [7:0] value);
        integer b;
        begin
            midi_rx=0;#32000;
            for(b=0;b<8;b=b+1)begin midi_rx=value[b];#32000;end
            midi_rx=1;#32000;
        end
    endtask
    initial begin
        #500;
        if(pa_en!==1)$fatal(1,"BOARD_AMP_RESET");
        #1500;sys_rst_n=1;
        #4000;
        if(pa_en!==0 || config_count!=1)$fatal(1,"BOARD_CONFIG_RESET_RELEASE");
        midi_byte(8'h90);midi_byte(8'd69);midi_byte(8'd100);
        #180000;
        if(accepted!=1 || dut.status_active_voice_count!==32'd1 ||
           nonzero<3 || commits<5 || serial_ones<5 || dut.audio_underrun!=0)
            $fatal(1,"BOARD_MIDI_FRAME_TRANSPORT_STUB_MISSING");
        if(dut.produced_left!==24'sd131072 || dut.produced_right!==-24'sd65536)
            $fatal(1,"BOARD_STEREO_COMMIT_WIRING_MISMATCH");
        $display("END STUB midi=%0d config=%0d commits=%0d nonzero=%0d frames=%0d serial=%0d underrun=%0d",
           accepted,config_count,commits,nonzero,frames,serial_ones,dut.audio_underrun);
        sys_rst_n=0;#1000;
        if(pa_en!==1 || dut.status_active_voice_count!==0 ||
           dut.buffered_left!==0 || dut.buffered_right!==0)
            $fatal(1,"BOARD_RESET_NOT_CLEAN");
        $display("PASS M2_M1TD_BOARD_WIRING_WITH_M1_STUB_ONLY");$finish;
    end
    initial begin #1500000;$fatal(1,"BOARD_STUB_TIMEOUT");end
endmodule