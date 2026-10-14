`timescale 1ns/1ps
// Actual frozen T062 115200 UART and dual-bank RAM; no voice/DAC/HDMI here.
module tb_m2_score_rx_event;
    reg clk=0,rst_n=0,uart_rx_i=1,base_valid=0,event_ready=1;
    always #12.5 clk=~clk; // 40 MHz
    wire uart_tx_o,rd_req,rd_valid,committed_valid,commit_pulse;
    wire [8:0] rd_index;
    wire [63:0] rd_event;
    wire [9:0] committed_count,consumed_events;
    wire [31:0] committed_score_id,late_events,active_score_id;
    wire [7:0] last_error;
    wire base_ready,event_valid,fault;
    wire [63:0] event_data;
    reg [63:0] base_data=0;
    wire frame_tick;
    reg [9:0] frame_phase=0;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)frame_phase<=0;
        else if(frame_phase==10'd832)frame_phase<=0;
        else frame_phase<=frame_phase+1'b1;
    end
    assign frame_tick=rst_n && frame_phase==10'd832;
    score_transfer_bram_candidate #(.CLK_HZ(40000000),.BAUD(115200)) receiver (
        .clk(clk),.rst_n(rst_n),.uart_rx_i(uart_rx_i),.uart_tx_o(uart_tx_o),
        .rd_req(rd_req),.rd_index(rd_index),.rd_valid(rd_valid),.rd_event(rd_event),
        .committed_valid(committed_valid),.committed_count(committed_count),
        .committed_score_id(committed_score_id),.commit_pulse(commit_pulse),.last_error(last_error)
    );
    m2_score_playback_candidate player(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .committed_valid(committed_valid),.commit_pulse(commit_pulse),
        .committed_count(committed_count),.committed_score_id(committed_score_id),
        .rd_req(rd_req),.rd_index(rd_index),.rd_valid(rd_valid),.rd_event(rd_event),
        .base_valid(base_valid),.base_data(base_data),.base_ready(base_ready),
        .event_valid(event_valid),.event_data(event_data),.event_ready(event_ready),
        .consumed_events(consumed_events),.late_events(late_events),
        .active_score_id(active_score_id),.fault(fault)
    );
    audio_defs_pkg::performance_event_t decoded;
    assign decoded=event_data;
    integer packet1=0,packet2=0,packet3=0,rx_packets=0,rx_index=0,rx_length=0;
    integer score_panic=0,score_on=0,score_off=0,read_requests=0,frames=0;
    reg [7:0] tx_bytes[0:71],reply[0:141],byte_value;
    string input_path;
    localparam integer BIT_NS=8675; // 347 core cycles at 115200
    always @(posedge clk)if(rst_n)begin
        if(rd_req)read_requests=read_requests+1;
        if(frame_tick)frames=frames+1;
        if(fault)$fatal(1,"REAL_RAM_SCORE_RX_EVENT_BAD");
        if(event_valid && event_ready && decoded.source_id==2)begin
            if(decoded.event_type==audio_defs_pkg::EVENT_ALL_NOTES_OFF)score_panic=score_panic+1;
            else if(decoded.event_type==audio_defs_pkg::EVENT_NOTE_ON)begin
                if(decoded.note_number!=69 || decoded.channel!=0 || decoded.velocity!=
                   audio_defs_pkg::midi_velocity_to_10bit(7'd100))
                    $fatal(1,"REAL_RAM_SCORE_RX_EVENT_BAD");
                score_on=score_on+1;
            end else if(decoded.event_type==audio_defs_pkg::EVENT_NOTE_OFF)begin
                if(decoded.note_number!=69 || decoded.channel!=0)
                    $fatal(1,"REAL_RAM_SCORE_RX_EVENT_BAD");
                score_off=score_off+1;
            end else $fatal(1,"REAL_RAM_SCORE_RX_EVENT_BAD");
        end
    end
    integer bit_index;
    initial forever begin
        @(negedge uart_tx_o);
        if(rst_n)begin
            #(BIT_NS*1.5);byte_value=0;
            for(bit_index=0;bit_index<8;bit_index=bit_index+1)begin
                byte_value[bit_index]=uart_tx_o;#(BIT_NS);
            end
            if(uart_tx_o!==1)$fatal(1,"REAL_RAM_REPLY_STOP_BIT");
            reply[rx_index]=byte_value;rx_index=rx_index+1;
            if(rx_index==12)rx_length=14+{reply[11],reply[10]};
            if(rx_index>141 || rx_length>141)$fatal(1,"REAL_RAM_REPLY_LENGTH");
            if(rx_length && rx_index==rx_length)begin
                if(reply[3]!==8'h80 || reply[13]!==8'h00)
                    $fatal(1,"REAL_RAM_REPLY_NOT_ACK");
                rx_packets=rx_packets+1;rx_index=0;rx_length=0;
            end
        end
    end
    task automatic send_byte(input [7:0]value);
        integer j;
        begin uart_rx_i=0;#(BIT_NS);
            for(j=0;j<8;j=j+1)begin uart_rx_i=value[j];#(BIT_NS);end
            uart_rx_i=1;#(BIT_NS);
        end
    endtask
    task automatic send_packet(input integer start_index,input integer count);
        integer n,prior;
        begin
            prior=rx_packets;
            for(n=0;n<count;n=n+1)send_byte(tx_bytes[start_index+n]);
            wait(rx_packets==prior+1);
            repeat(30)@(negedge clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("BYTES=%s",input_path) ||
           !$value$plusargs("P1=%d",packet1) ||
           !$value$plusargs("P2=%d",packet2) ||
           !$value$plusargs("P3=%d",packet3))$fatal(1,"REAL_RAM_BYTES_ARGS");
        if(packet1+packet2+packet3!=72)$fatal(1,"REAL_RAM_PACKET_COUNT");
        $readmemh(input_path,tx_bytes);
        repeat(5)@(negedge clk);rst_n=1;
        send_packet(0,packet1);
        send_packet(packet1,packet2);
        send_packet(packet1+packet2,packet3);
        wait(committed_valid && committed_count==2 && active_score_id==32'd7);
        wait(consumed_events==2);
        repeat(20)@(negedge clk);
        if(last_error!=0 || rx_packets!=3 || score_panic!=1 || score_on!=1 ||
           score_off!=1 || read_requests!=2 || fault || frames<16)
            $fatal(1,"REAL_RAM_SCORE_EVENT_COVERAGE");
        $display("END REAL_T062 packets=%0d panic=%0d on=%0d off=%0d rd=%0d frames=%0d late=%0d",
            rx_packets,score_panic,score_on,score_off,read_requests,frames,late_events);
        $display("PASS REAL_T062_UART_TO_SCORE_EVENTS_NO_AUDIO");$finish;
    end
    initial begin #30000000;$fatal(1,"REAL_T062_UART_EVENT_TIME_LIMIT");end
endmodule