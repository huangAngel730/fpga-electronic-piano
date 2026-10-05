// Physical button inputs -> public FIFO -> real four-voice core -> PT8211 pins.
// Audio frame cadence accelerated for Release lifecycle; not a frequency test.
`timescale 1ns/1ps
module tb_key_to_tone;
    logic sys_clk=0;always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0,midi_rx=1;
    logic [1:0] key_n=3;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
    electronic_piano_top #(.DEBOUNCE_CNT(16),.DEBOUNCE_CLK_HZ(1000)) dut(.*);
    defparam dut.u_i2s_tx.ACC_BITS=8;
    defparam dut.u_i2s_tx.BCLK_PHASE_STEP=8'd255;
    integer checks=0,words=0,nonzero=0,word_count=0,half=0,last_left=0,stereo_pairs=0;
    logic seen=0,previous_ws=0;logic [31:0] serial_word=0;
    task automatic check(input logic ok,input string name);
        checks++;if(ok!==1'b1)$fatal(1,"Key %s voices=%0d",name,dut.status_active_voice_count);
    endtask
    always @(posedge i2s_bclk) if(sys_rst_n)begin
        if(!seen)begin seen=1;previous_ws=i2s_lrck;end
        if(i2s_lrck!==previous_ws)begin
            if(half>6)begin
                if(word_count!=32)$fatal(1,"Invalid PT8211 WS interval");
                words++;if(serial_word[15:0]!=0)nonzero++;
                // Frame starts right (WS low), then left high; both equal.
                if(!previous_ws) last_left=$signed(serial_word[15:0]);
                else begin
                    if($signed(serial_word[15:0])!=last_left)$fatal(1,"Stereo PCM mismatch");
                    stereo_pairs++;
                end
            end
            half++;previous_ws=i2s_lrck;word_count=0;serial_word=0;
        end
        serial_word={serial_word[30:0],i2s_din};word_count++;
    end
    task automatic wait_frames(input integer n);
        integer target;
        target=dut.audio_frame_count+n;
        wait(dut.audio_frame_count>=target);
        repeat(15)@(negedge sys_clk);
    endtask
    initial begin
        repeat(5)@(negedge sys_clk);check(pa_en==1,"reset amplifier off");sys_rst_n=1;
        wait_frames(10);check(dut.status_active_voice_count==0 && nonzero==0,"idle silence");
        @(negedge sys_clk);key_n[0]=0;
        wait(dut.status_active_voice_count==1);wait_frames(260);
        check(nonzero>100,"actual PCM serialized after Attack");
        check(dut.g_polyphonic.u_audio_core.u_bank.slot_notes[7:0]==69,"first key A4");
        @(negedge sys_clk);key_n[1]=0;
        wait(dut.status_active_voice_count==2);wait_frames(260);
        check(dut.g_polyphonic.u_audio_core.u_bank.slot_notes[15:8]==72,"second key C5 gets own slot");
        check(dut.status_active_voice_count==2,"second key does not steal held first note");
        @(negedge sys_clk);key_n[0]=1;
        wait(dut.g_polyphonic.u_audio_core.u_bank.u_events.slot_releasing[0]);
        check(dut.status_active_voice_count==2,"release retains tail");
        wait_frames(4802);
        $display("DEBUG release state=%0d level=%0d elapsed=%0d bankPhase=%0d requests=%0d commits=%0d underrun=%0d releasing=%b",
          dut.g_polyphonic.u_audio_core.u_bank.g_lane[0].u_envelope.state_out,
          dut.g_polyphonic.u_audio_core.u_bank.g_lane[0].u_envelope.envelope_level,
          dut.g_polyphonic.u_audio_core.u_bank.g_lane[0].u_envelope.elapsed,
          dut.g_polyphonic.u_audio_core.u_bank.phase,dut.pcm_request_count,dut.pcm_commit_count,dut.audio_underrun,
          dut.g_polyphonic.u_audio_core.u_bank.u_events.slot_releasing);
        check(dut.status_active_voice_count==1,"only released first key retires");
        @(negedge sys_clk);key_n[1]=1;
        wait(dut.g_polyphonic.u_audio_core.u_bank.u_events.slot_releasing[1]);
        wait_frames(4802);check(dut.status_active_voice_count==0,"all tails retire");
        check(dut.buffered_left==0 && dut.buffered_right==0,"silence after full Release");
        check(dut.audio_underrun==0 && dut.status_clip_count==0,"normal PCM has no underrun/clip");
        check(stereo_pairs>1000,"physical stereo samples match");
        @(negedge sys_clk);sys_rst_n=0;repeat(5)@(negedge sys_clk);
        check(pa_en==1 && dut.status_active_voice_count==0,"reset clears lifecycle");
        $display("PASS tb_key_to_tone checks=%0d serial_words=%0d pairs=%0d",checks,words,stereo_pairs);$finish;
    end
    initial begin #150_000_000;$fatal(1,"Key lifecycle timeout");end
endmodule