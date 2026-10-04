// Real 50MHz / 31250 8N1 Program Change -> shared FIFO -> dynamic four lanes.
// Audio BCLK is accelerated only for simulation; UART timing remains real.
`timescale 1ns/1ps
module tb_t027_midi_program_top;
    logic sys_clk=0;
    always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0,midi_rx=1;
    logic [1:0] key_n=2'b11;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
    electronic_piano_top dut(.*);
    defparam dut.u_i2s_tx.ACC_BITS=8;
    defparam dut.u_i2s_tx.BCLK_PHASE_STEP=32'd255;
    localparam integer BIT_CYCLES=1600;
    integer checks=0,decoded=0,nonzero=0;
    wire [3:0] timbres=dut.g_polyphonic.u_audio_core.u_bank.slot_timbre;
    wire [3:0] occupied=dut.g_polyphonic.u_audio_core.u_bank.slot_occupied;
    wire [31:0] notes=dut.g_polyphonic.u_audio_core.u_bank.slot_notes;
    task automatic check(input logic ok,input string label_text);
        checks++;
        if(ok!==1'b1)$fatal(1,"T027 UART %s occupied=%b timbres=%b",label_text,occupied,timbres);
    endtask
    task automatic byte_in(input logic [7:0] value);
        @(negedge sys_clk);midi_rx=0;repeat(BIT_CYCLES)@(negedge sys_clk);
        for(integer i=0;i<8;i++)begin midi_rx=value[i];repeat(BIT_CYCLES)@(negedge sys_clk);end
        midi_rx=1;repeat(BIT_CYCLES)@(negedge sys_clk);
    endtask
    task automatic settle;
        wait(dut.event_fifo_level==0 && !dut.shared_event_valid &&
             !dut.g_polyphonic.u_audio_core.u_bank.dispatch_busy);
        repeat(100)@(negedge sys_clk);
    endtask
    task automatic program_change(input logic [3:0] channel,input logic [6:0] number);
        byte_in({4'hc,channel});byte_in({1'b0,number});settle();
    endtask
    task automatic note(input logic [3:0] channel,input logic [6:0] number);
        byte_in({4'h9,channel});byte_in({1'b0,number});byte_in(8'd100);settle();
    endtask
    integer edges=0;
    logic [31:0] word_bits=0;
    always @(posedge i2s_bclk) if(dut.rst_sync_n) begin
        word_bits={word_bits[30:0],i2s_din};
        edges++;
        if(edges==64)begin
            edges=0;decoded++;
            if(word_bits[15:0]!=0)nonzero++;
        end
    end
    initial begin
        repeat(6)@(negedge sys_clk);check(pa_en==1,"power-on mute");
        sys_rst_n=1;repeat(100)@(negedge sys_clk);
        program_change(0,1);
        note(0,60);
        check(occupied[0] && timbres[0],"channel0 Program1 triangle on NoteOn");
        program_change(0,0);
        check(timbres[0],"held note does not follow Program Change");
        note(0,62);
        check(occupied[1] && !timbres[1],"channel0 Program0 keeps V1");
        program_change(1,1);
        note(1,64);
        check(occupied[2] && timbres[2],"channel1 Program1 independent");
        note(2,67);
        check(occupied[3] && !timbres[3],"channel2 defaults to V1");
        program_change(0,127);
        note(0,62);
        check(timbres==4'b0101 && notes[15:8]==62,
              "unknown Program ignored, same identity retains slot");
        repeat(2000)@(negedge sys_clk);
        check(dut.status_active_voice_count==4 && nonzero>4,
              "active PCM reaches serial DAC pins");
        check(dut.u_midi_input.parser_error_count==0 &&
              dut.u_midi_input.uart_frame_error_count==0,
              "real UART Program/Note parsed without errors");
        check(dut.audio_underrun==0 && dut.status_clip_count==0,
              "no audio underrun or clipping");
        $display("PASS T027 real UART Program checks=%0d serial_nonzero=%0d",checks,nonzero);
        $finish;
    end
    initial begin #300000000;$fatal(1,"T027 real UART timeout");end
endmodule
