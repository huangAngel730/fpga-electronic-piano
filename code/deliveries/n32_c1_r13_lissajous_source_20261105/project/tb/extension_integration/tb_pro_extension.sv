// End-to-end physical-wrapper simulation. PLL frequencies are a fixture;
// board electrical behavior and real PLL phases require implementation/board QA.
`timescale 1ns/1ps
module tb_pro_extension;
    import audio_defs_pkg::*;
    reg clk50=0, rst_n=0, ble_rx=1;
    always #10 clk50=~clk50;
    reg [1:0] keys=2'b11;
    wire ble_tx,pa,ib,il,idata,tx;
    wire ck_p,ck_n;
    wire [2:0] d_p,d_n;
    pro_audio_minimal_top dut(.sys_clk_50m(clk50),.sys_rst_n(rst_n),
        .key_n(keys),.midi_rx(1'b1),.i2s_bclk(ib),.i2s_lrck(il),.i2s_din(idata),
        .pa_en(pa),.uart_tx(tx),.ble_uart_rx(ble_rx),.ble_uart_tx(ble_tx),
        .tmds_clk_p(ck_p),.tmds_clk_n(ck_n),.tmds_data_p(d_p),.tmds_data_n(d_n));
    wire clk=dut.core_clk;
    wire [7:0] byte_data;
    wire byte_valid,byte_error;
    uart_rx #(.CLK_HZ(40000000),.BAUD(115200)) response_monitor(
        .clk(clk),.rst_n(dut.core_rst_n),.rx(ble_tx),.rx_data(byte_data),
        .rx_valid(byte_valid),.frame_err(byte_error),.rx_busy());
    reg [7:0] payload[0:127], reply[0:141], records[0:47];
    integer rx_pos=0,target=0,replies=0,score_timeline_events=0,score_stop_events=0,human_events=0;
    integer audio_nonzero=0;
    integer checks=0;
    function automatic [15:0] crc_byte(input [15:0] old,input [7:0] b);
        reg [15:0] c;
        begin
            c=old^{b,8'b0};
            for(integer k=0;k<8;k=k+1)c=c[15] ? (c<<1)^16'h1021 : c<<1;
            crc_byte=c;
        end
    endfunction
    always @(posedge clk) begin
        if(byte_error)$fatal(1,"real UART response framing error");
        if(byte_valid)begin
            reply[rx_pos]=byte_data;
            if(rx_pos==0 && byte_data!=8'ha5)$fatal(1,"response magic1");
            if(rx_pos==1 && byte_data!=8'h5a)$fatal(1,"response magic2");
            if(rx_pos==11)begin
                target=14+{reply[11],reply[10]};
                if(target!=26 && target!=34)$fatal(1,"response wire shape");
            end
            rx_pos=rx_pos+1;
            if(target!=0 && rx_pos==target)begin
                replies=replies+1;rx_pos=0;target=0;
            end
        end
        if(dut.score_event_valid && dut.score_event_ready)begin
            if(dut.score_event_data.source_id!=14)$fatal(1,"score timeline source identity");
            if(dut.score_event_data.event_type==EVENT_ALL_NOTES_OFF)score_stop_events=score_stop_events+1;
            else begin
                score_timeline_events=score_timeline_events+1;
                if($test$plusargs("FULL_PLAYBACK"))begin : exact_imported_sequence
                    integer r;
                    logic [31:0] offset_tick;
                    r=(score_timeline_events-1)*8;
                    if(score_timeline_events>6)$fatal(1,"extra score timeline event after complete imported song");
                    offset_tick={records[r+3],records[r+2],records[r+1],records[r]};
                    if(dut.u_score_visual.global_tick!=dut.u_score_visual.u_scheduler.t0+96768+offset_tick)
                        $fatal(1,"score timeline event%0d due tick",score_timeline_events);
                    if(dut.score_event_data.event_type!=(records[r+4]==0 ? EVENT_NOTE_ON : EVENT_NOTE_OFF) ||
                       dut.score_event_data.note_number!=records[r+6] ||
                       dut.score_event_data.channel!=records[r+5])
                        $fatal(1,"score timeline event%0d stable identity/order",score_timeline_events);
                    if(records[r+4]==0 && dut.score_event_data.velocity!=
                       {records[r+7][6:0],records[r+7][6:4]})
                        $fatal(1,"score timeline velocity mapping");
                end
                if($test$plusargs("FULL_PLAYBACK") && score_timeline_events==1)begin
                    if(dut.score_event_data.event_type!=EVENT_NOTE_ON ||
                       dut.score_event_data.note_number!=69)
                        $fatal(1,"first score timeline event identity");
                    if(dut.u_score_visual.global_tick!=dut.u_score_visual.u_scheduler.t0+96768)
                        $fatal(1,"first score timeline event did not share exact future anchor");
                    $display("PASS FULL_LEAD_FIRST_TIMELINE tick=%0d F0=%0d T0=%0d phase=%0d",
                        dut.u_score_visual.global_tick,dut.u_score_visual.u_scheduler.f0,
                        dut.u_score_visual.u_scheduler.t0,dut.u_score_visual.u_scheduler.phase0);
                end
            end
        end
        if(dut.accepted_event_valid && dut.accepted_event_ready)begin
            if(dut.accepted_event_data.source_id==14)$fatal(1,"score event reached audio core");
            else if(dut.accepted_event_data.source_id==0 || dut.accepted_event_data.source_id==1)human_events=human_events+1;
            else $fatal(1,"unexpected accepted source");
        end
        if(dut.core_rst_n && dut.sample_tick &&
           (dut.u_audio.buffered_left!=0 || dut.u_audio.buffered_right!=0))audio_nonzero=audio_nonzero+1;
        if(!rst_n && pa!==1'b0)$fatal(1,"physical PA active during reset");
    end
    task automatic send_byte(input [7:0] b);
        begin
            @(negedge clk);ble_rx=0;repeat(347)@(negedge clk);
            for(integer i=0;i<8;i=i+1)begin ble_rx=b[i];repeat(347)@(negedge clk);end
            ble_rx=1;repeat(347)@(negedge clk);
        end
    endtask
    task automatic request(input [7:0] cmd,input [15:0] seq,offset,input integer len,
                           input [7:0] error_code);
        reg [7:0] header[0:9];
        reg [15:0] crc,actual;
        integer before_reply,expected_len;
        begin
            header[0]=2;header[1]=cmd;header[2]=8'h21;header[3]=8'h3e;
            header[4]=seq[7:0];header[5]=seq[15:8];header[6]=offset[7:0];header[7]=offset[15:8];
            header[8]=len[7:0];header[9]=len[15:8];
            before_reply=replies;crc=16'hffff;
            send_byte(8'ha5);send_byte(8'h5a);
            for(integer i=0;i<10;i=i+1)begin crc=crc_byte(crc,header[i]);send_byte(header[i]);end
            for(integer i=0;i<len;i=i+1)begin crc=crc_byte(crc,payload[i]);send_byte(payload[i]);end
            send_byte(crc[7:0]);send_byte(crc[15:8]);
            wait(replies>before_reply);
            @(negedge clk);
            if(reply[2]!=2 || reply[3]!=(error_code==0 ? 8'h80 : 8'h81) || reply[12]!=cmd || reply[13]!=error_code)
                $fatal(1,"command%0d response status=%0d error=%0d expected=%0d",cmd,reply[3],reply[13],error_code);
            for(integer i=2;i<8;i=i+1)
                if(reply[i+2]!=header[i])$fatal(1,"response identity");
            expected_len=(cmd==6 && error_code==0) ? 20 : 12;
            if({reply[11],reply[10]}!=expected_len)$fatal(1,"strict ACK/NACK shape");
            actual=16'hffff;
            for(integer i=2;i<12+expected_len;i=i+1)actual=crc_byte(actual,reply[i]);
            if(actual!={reply[13+expected_len],reply[12+expected_len]})$fatal(1,"response CRC");
            checks=checks+1;
        end
    endtask
    task automatic identity_payload;
        begin
            payload[0]=23;payload[1]=0;payload[2]=0;payload[3]=0;
            payload[4]=6;payload[5]=0;payload[6]=0;payload[7]=0;
        end
    endtask
    initial begin : scenario
        reg [15:0] crc;
        integer old_human,silent_audio_nonzero;
        for(integer i=0;i<128;i=i+1)payload[i]=0;
        // Actual bytes produced by the new PC MIDI importer from the shipped
        // A4/C5 SMF, not a hand-built approximation of its output.
        $readmemh("demo_records.hex",records);
        repeat(20)@(negedge clk50);rst_n=1;
        wait(dut.core_rst_n);repeat(100)@(negedge clk);
        identity_payload();request(7,0,0,8,13); // no published score/full READ
        crc=16'hffff;for(integer i=0;i<48;i=i+1)crc=crc_byte(crc,records[i]);
        payload[0]=23;payload[1]=0;payload[2]=0;payload[3]=0;
        payload[4]=6;payload[5]=0;payload[6]=48;payload[7]=0;
        payload[8]=crc[7:0];payload[9]=crc[15:8];
        payload[10]=8'h80;payload[11]=8'hbb;payload[12]=0;payload[13]=0;
        request(1,0,0,14,0);
        for(integer i=0;i<48;i=i+1)payload[i]=records[i];
        request(2,1,0,48,0);request(3,2,0,0,0);
        if(score_timeline_events!=0 || dut.lease_busy)$fatal(1,"COMMIT auto-started");
        identity_payload();request(7,3,0,8,13);
        identity_payload();request(10,4,0,8,0);
        request(4,5,0,0,15); // persistent read lease protects mutation
        for(integer index=0;index<6;index=index+1)begin
            request(6,16'(6+index),16'(index),0,0);
            for(integer i=0;i<8;i=i+1)
                if(reply[24+i]!=records[index*8+i])$fatal(1,"READ%0d byte%0d",index,i);
        end
        request(11,12,0,0,0);
        if(!dut.full_read_verified)$fatal(1,"full READ did not verify");
        if(dut.u_audio.obs_occupied_mask!=0)$fatal(1,"cold visual START has an active audio voice");
        silent_audio_nonzero=audio_nonzero;
        identity_payload();request(7,13,0,8,0);
        if(!dut.lease_busy)$fatal(1,"START did not lock bank");
        request(4,14,0,0,15);request(5,15,0,0,0);
        if($test$plusargs("FULL_PLAYBACK"))begin
            wait(dut.u_score_visual.u_display.falling_valid!=0);
            if(dut.u_score_visual.u_display.live_valid!=0)$fatal(1,"cold visual START fabricated a live key");
            $display("PASS VISUAL_ONLY_PREVIEW_QUEUED frame=%0d",dut.u_score_visual.u_display.current_frame);
            wait(score_timeline_events==1);
            wait(score_timeline_events==6);
            repeat(800000)@(negedge clk);
            if(audio_nonzero!=silent_audio_nonzero || dut.u_audio.obs_occupied_mask!=0)
                $fatal(1,"visual-only score produced PCM/audio voice");
            if(dut.desync_latched)$fatal(1,"full lead generated desync");
            if(!dut.lease_busy)$fatal(1,"natural score end released mutable bank");
            request(4,16,0,0,15);
            $display("PASS FULL_VISUAL_ONLY_SEQUENCE timeline=6 audio_source14=0 natural_end_lease=1");
        end
        request(8,17,0,0,0);
        if(dut.lease_busy)$fatal(1,"STOP ACK before lease release");
        if(score_stop_events!=1)$fatal(1,"visual-only STOP did not consume exactly one local cleanup token");
        keys=2'b10;old_human=human_events;repeat(800000)@(negedge clk);
        if(human_events<=old_human || !dut.u_score_visual.u_display.key_down[69] ||
           audio_nonzero==silent_audio_nonzero)$fatal(1,"physical MIDI path did not produce live bar and audio");
        identity_payload();request(7,18,0,8,0);
        wait(dut.u_score_visual.u_display.falling_valid!=0);
        if(dut.u_score_visual.u_display.live_valid==0 ||
           !dut.u_score_visual.u_display.key_down[69])$fatal(1,"live MIDI and falling score did not coexist");
        request(8,19,0,0,0);
        if(dut.lease_busy || score_stop_events!=2)$fatal(1,"second STOP/lease cleanup incomplete");
        if(!pa || !dut.u_score_visual.u_display.key_down[69])$fatal(1,"score STOP erased or muted held MIDI");
        request(9,20,0,0,0);
        if(dut.lease_busy)$fatal(1,"CLEAR ACK before empty");
        if(!dut.u_score_visual.u_display.key_down[69])$fatal(1,"CLEAR erased held human bar");
        keys=2'b11;repeat(800000)@(negedge clk);
        if(dut.u_score_visual.u_display.key_down[69])$fatal(1,"human release missing after CLEAR");
        rst_n=0;#1;if(pa!==0)$fatal(1,"physical asynchronous mute");
        $display("PASS PRO_UART_RAM_CONTROL checks=%0d human=%0d timeline=%0d",checks,human_events,score_timeline_events);
        $display("PRO_EXTENSION_TEST_COMPLETE");$finish;
    end
    initial begin
        if($test$plusargs("FULL_PLAYBACK"))#4000000000;
        else #500000000;
        $fatal(1,"physical integration test watchdog");
    end
endmodule
