`timescale 1ns/1ps
// Private real T062 UART receiver + M2 score event source + original four voices.
// Nominal PLL/DVI models. Synthetic T057 score fixture; not downloaded MIDI.
module tb_m2_score_board_uart;
    reg sys_clk=0,sys_rst_n=0,midi_rx=1,score_uart_rx=1;
    reg [1:0] key_n=2'b11;
    always #10 sys_clk=~sys_clk;  // actual board reference 50 MHz
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,score_uart_tx,tmds_clk_p,tmds_clk_n;
    wire [2:0] tmds_data_p,tmds_data_n;
    GSR GSR(.GSRI(1'b1));
    m2_score_playback_board_top dut(.*);
    localparam integer BIT_NS=8675; // 40MHz / 115200 = 347 cycles
    reg [7:0] bytes[0:127];
    reg [7:0] reply[0:141];
    integer p1=0,p2=0,p3=0,total=0,reply_count=0,reply_size=0;
    integer n=0; reg [7:0] raw_byte;
    integer frames=0,nonzero=0,score_notes=0,score_offs=0,score_panic=0,commits=0,serial_ones=0;
    string bytes_file;
    audio_defs_pkg::performance_event_t current;
    assign current=dut.score_mixed_data;
    always @(posedge dut.core_clk) if(dut.rst_sync_n)begin
        if(dut.score_mixed_valid && dut.score_mixed_ready && current.source_id==2)begin
            if(current.event_type==audio_defs_pkg::EVENT_NOTE_ON && current.note_number==7'd69)
                score_notes=score_notes+1;
            if(current.event_type==audio_defs_pkg::EVENT_NOTE_OFF && current.note_number==7'd69)
                score_offs=score_offs+1;
            if(current.event_type==audio_defs_pkg::EVENT_ALL_NOTES_OFF)
                score_panic=score_panic+1;
        end
        if(dut.i2s_frame_tick)begin
            frames=frames+1;
            if(dut.buffered_left!=0 || dut.buffered_right!=0)nonzero=nonzero+1;
        end
        if(dut.pcm_valid_q && dut.pcm_ready)commits=commits+1;
    end
    always @(posedge i2s_bclk)if(sys_rst_n && pa_en===0 && i2s_din===1)
        serial_ones=serial_ones+1;
    initial forever begin
        @(negedge score_uart_tx);
        if(dut.rst_sync_n)begin
            #(BIT_NS*1.5);raw_byte=0;
            for(n=0;n<8;n=n+1)begin raw_byte[n]=score_uart_tx;#(BIT_NS);end
            if(score_uart_tx!==1)$fatal(1,"UART_TX_STOPBIT");
            reply[total]=raw_byte;total=total+1;
            if(total==12)reply_size=14+{reply[11],reply[10]};
            if(reply_size && total==reply_size)begin reply_count=reply_count+1;total=0;reply_size=0;end
        end
    end
    task automatic send_byte(input [7:0]value);
        integer i;
        begin score_uart_rx=0;#(BIT_NS);
            for(i=0;i<8;i=i+1)begin score_uart_rx=value[i];#(BIT_NS);end
            score_uart_rx=1;#(BIT_NS);
        end
    endtask
    task automatic send_packet(input integer start_index,input integer count);
        integer k,before_reply;
        begin
            before_reply=reply_count;
            for(k=0;k<count;k=k+1)send_byte(bytes[start_index+k]);
            wait(reply_count==before_reply+1);
            repeat(30)@(negedge dut.core_clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("BYTES=%s",bytes_file) ||
           !$value$plusargs("P1=%d",p1) || !$value$plusargs("P2=%d",p2) ||
           !$value$plusargs("P3=%d",p3))$fatal(1,"INPUT_ARGS_MISSING");
        $readmemh(bytes_file,bytes);
        #500;
        if(pa_en!==1)$fatal(1,"RESET_PA_EN");
        sys_rst_n=1;wait(dut.rst_sync_n);
        send_packet(0,p1);
        send_packet(p1,p2);
        send_packet(p1+p2,p3);
        wait(dut.score_committed_valid && dut.score_committed_count==2);
        wait(dut.score_consumed_events==2);
        repeat(90)@(negedge dut.core_clk);
        if(dut.score_fault || dut.score_active_id!==32'd7 || reply_count!=3 ||
           score_panic!=1 || score_notes!=1 || score_offs!=1 ||
           nonzero<3 || commits<5 || serial_ones<5)
            $fatal(1,"SCORE_EVENT_NOT_REACHING_AUDIO");
        $display("END score_commit=%0d replies=%0d panic=%0d note_on=%0d note_off=%0d frames=%0d nonzero=%0d commits=%0d serial=%0d",
           dut.score_commit_pulse,reply_count,score_panic,score_notes,score_offs,frames,nonzero,commits,serial_ones);
        $display("PASS REAL_T062_UART_TO_SCORE_EVENT_TO_PCM_ISOLATED");$finish;
    end
    initial begin #30000000;$fatal(1,"SCORE_BOARD_TIME_LIMIT");end
endmodule