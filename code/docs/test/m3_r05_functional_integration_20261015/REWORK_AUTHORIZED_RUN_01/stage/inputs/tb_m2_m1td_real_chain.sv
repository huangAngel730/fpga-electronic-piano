`timescale 1ns/1ps
// Real M1 candidate in a copied 138K L board graph. No arithmetic stub.
module tb_m2_m1td_real_chain;
    reg sys_clk=0,sys_rst_n=0,midi_rx=1;
    reg [1:0] key_n=2'b11;
    always #10 sys_clk=~sys_clk;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,tmds_clk_p,tmds_clk_n;
    wire [2:0] tmds_data_p,tmds_data_n;
    GSR GSR(.GSRI(1'b1));
    m2_fourvoice_timbre_delay_board_top dut(.*);
    integer accepted=0,commits=0,nonzero=0,frames=0,config_count=0,serial_ones=0;
    integer before_fifth=0, before_frames=0, before_commit=0;
    always @(posedge dut.core_clk)if(dut.rst_sync_n)begin
        if(dut.shared_event_valid && dut.shared_event_ready)accepted=accepted+1;
        if(dut.g_polyphonic.m1_config_pending && dut.g_polyphonic.m1_config_ready)config_count=config_count+1;
        if(dut.g_polyphonic.m1_commit)begin
            commits=commits+1;
            if(dut.produced_left!=0 || dut.produced_right!=0)nonzero=nonzero+1;
        end
        if(dut.i2s_frame_tick)frames=frames+1;
    end
    always @(posedge i2s_bclk)if(sys_rst_n && pa_en===0 && i2s_din===1)serial_ones=serial_ones+1;
    task automatic midi_byte(input[7:0]v);
        integer i;
        begin midi_rx=0;#32000;
            for(i=0;i<8;i=i+1)begin midi_rx=v[i];#32000;end
            midi_rx=1;#32000;
        end
    endtask
    initial begin
        #500;if(pa_en!==1)$fatal(1,"M1TD_AMP_NOT_MUTED_IN_RESET");
        #1500;sys_rst_n=1;
        #4000;if(pa_en!==0 || config_count!=1)$fatal(1,"M1TD_CONFIG_OR_PLL_STARTUP");
        midi_byte(8'h90);midi_byte(8'd69);midi_byte(8'd100);
        #220000;
        if(accepted<1 || (dut.status_active_voice_count>=1)!==1'b1 || commits<3 || nonzero<3)
            $fatal(1,"M1TD_REAL_PIANO_EVENT_TO_PCM_MISSING");
        midi_byte(8'hC0);midi_byte(8'd1);
        midi_byte(8'h90);midi_byte(8'd64);midi_byte(8'd80);
        #220000;
        if(accepted<3 || (dut.status_active_voice_count>=2)!==1'b1 || commits<10 || nonzero<10 || serial_ones<5)
            $fatal(1,"M1TD_REAL_PROGRAM_EVENT_TO_AUDIO_MISSING");
        // The four notes overlap in the 40 MHz board graph. Existing allocator
        // identity/steal mathematics are reused, but this checks the new graph.
        midi_byte(8'h90);midi_byte(8'd60);midi_byte(8'd95);
        midi_byte(8'h90);midi_byte(8'd67);midi_byte(8'd85);
        #220000;
        if(dut.status_active_voice_count!==4 || commits<20 || nonzero<20)
            $fatal(1,"M1TD_FOUR_SIMULTANEOUS_VOICES_MISSING");
        before_fifth=accepted;before_frames=frames;before_commit=commits;
        midi_byte(8'h90);midi_byte(8'd72);midi_byte(8'd110);
        #220000;
        if(accepted<=before_fifth || dut.status_active_voice_count!==4 ||
           frames<=before_frames+2 || commits<=before_commit+2 ||
           (dut.status_max_processing_cycles<834)!==1'b1)
            $fatal(1,"M1TD_FIFTH_STEAL_OR_833_CYCLE_DEADLINE_FAIL");
        $display("END REAL_M1 accepted=%0d active=%0d commits=%0d nonzero=%0d frames=%0d serial=%0d max_cycles=%0d",
            accepted,dut.status_active_voice_count,commits,nonzero,frames,serial_ones,
            dut.status_max_processing_cycles);
        sys_rst_n=0;#1000;
        if(pa_en!==1 || dut.status_active_voice_count!==0 || dut.buffered_left!==0 || dut.buffered_right!==0)
            $fatal(1,"M1TD_SHARED_RESET_NOT_CLEAN");
        $display("PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY");$finish;
    end
    initial begin #6000000;$fatal(1,"M1TD_REAL_CHAIN_TIMEOUT");end
endmodule