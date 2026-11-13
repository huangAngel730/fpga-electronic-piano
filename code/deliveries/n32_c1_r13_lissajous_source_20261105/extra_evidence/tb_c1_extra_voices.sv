`timescale 1ns/1ps
module tb_c1_extra_voices;
    import audio_defs_pkg::*;
    reg clk=0;
    always #12.5 clk=~clk;
    reg rst_n=0, sample_tick=0, event_take=0;
    reg [2:0] selected=0;
    performance_event_t event_data;
    wire signed [23:0] snare_pcm, sax_pcm, guitar_pcm;
    wire frame_pcm_ready;
    wire signed [23:0] ref_snare,ref_sax,ref_guitar;
    wire ref_ready;
    r05_c1_extra_voices #(
        .SAX_SOFT_ROM("rom/c1_fx/sax_soft.hex"),
        .SAX_HARD_ROM("rom/c1_fx/sax_hard.hex"),
        .SAX_NOISE_ROM("rom/c1_fx/noise_levels.hex")
    ) reference(
        .clk(clk),.rst_n(rst_n),.sample_tick(sample_tick),.event_take(event_take),
        .selected(selected),.event_data(event_data),.snare_pcm(ref_snare),
        .sax_pcm(ref_sax),.guitar_pcm(ref_guitar),.frame_pcm_ready(ref_ready));
    wire [71:0] all_pcm={guitar_pcm,sax_pcm,snare_pcm};
    c1_extra_voices #(
        .SAX_SOFT_ROM("rom/c1_fx/sax_soft.hex"),
        .SAX_HARD_ROM("rom/c1_fx/sax_hard.hex"),
        .SAX_NOISE_ROM("rom/c1_fx/noise_levels.hex")
    ) dut(.*);
    integer frames=0, max_cycles=0;
    reg [2:0] heard=0;

    function automatic performance_event_t note(
        input [2:0] typ, input [3:0] source, channel,
        input [6:0] pitch, input [9:0] velocity
    );
        performance_event_t result;
        begin
            result='0; result.event_type=typ; result.source_id=source;
            result.channel=channel; result.note_number=pitch; result.velocity=velocity;
            note=result;
        end
    endfunction
    function automatic performance_event_t pedal(
        input [3:0] source, channel, input [11:0] value
    );
        performance_event_t result;
        begin
            result=note(EVENT_CONTROL_CHANGE,source,channel,0,0);
            result.control_id=CTRL_SUSTAIN; result.control_value=value;
            pedal=result;
        end
    endfunction
    task automatic send(input [2:0] choice, input performance_event_t data);
        begin
            @(negedge clk); selected=choice; event_data=data; event_take=1;
            @(negedge clk); event_take=0;
            if(dut.fire_on!==0 || dut.fire_off!==0 || dut.fire_kill!==0)
                $fatal(1,"leaf event escaped sample boundary");
        end
    endtask
    task automatic frame(
        input [2:0] on_mask, off_mask, kill_mask,
        input bit simultaneous_event, overlap,
        input performance_event_t data
    );
        reg [71:0] previous_pcm, stable_pcm;
        integer cycles;
        begin
            @(negedge clk);
            previous_pcm=all_pcm; sample_tick=1;
            if(simultaneous_event) begin selected=2; event_data=data; event_take=1; end
            @(posedge clk); #1;
            if(!dut.launch || dut.fire_on!==on_mask || dut.fire_off!==off_mask ||
                dut.fire_kill!==kill_mask)
                $fatal(1,"event routing frame %0d on=%b/%b off=%b/%b kill=%b/%b",
                    frames,dut.fire_on,on_mask,dut.fire_off,off_mask,dut.fire_kill,kill_mask);
            @(negedge clk); sample_tick=0; event_take=0;
            @(posedge clk); #1;
            if(all_pcm!==previous_pcm || !dut.frame_pending) $fatal(1,"early publish/accept");
            cycles=0;
            while(dut.frame_pending && cycles<200) begin
                @(negedge clk); sample_tick=overlap && cycles==5; event_take=0;
                #1;
                if(dut.launch) $fatal(1,"overlap launched");
                @(posedge clk); #1; cycles=cycles+1;
                if(dut.frame_pending && all_pcm!==previous_pcm) $fatal(1,"partial publish");
            end
            if(dut.frame_pending || ^all_pcm===1'bx) $fatal(1,"missing/unknown frame");
            if(!kill_mask[2] && (cycles<66 || cycles>91)) $fatal(1,"normal deadline %0d",cycles);
            if(kill_mask[2] && (cycles!=14 || guitar_pcm!==0)) $fatal(1,"guitar kill publish");
            if(!ref_ready || all_pcm!=={ref_guitar,ref_sax,ref_snare})
                $fatal(1,"R05/R06 extra PCM mismatch at frame %0d",frames);
            if(cycles>max_cycles) max_cycles=cycles;
            heard=heard|{guitar_pcm!=0,sax_pcm!=0,snare_pcm!=0};
            frames=frames+1;
            stable_pcm=all_pcm;
            @(negedge clk); sample_tick=0; event_take=0;
            repeat(2) begin
                @(posedge clk); #1;
                if(all_pcm!==stable_pcm || dut.frame_pending) $fatal(1,"hold/ghost");
            end
        end
    endtask
    task automatic tick(input [2:0] on_mask,off_mask,kill_mask);
        frame(on_mask,off_mask,kill_mask,0,0,'0);
    endtask

    initial begin
        event_data='0;
        repeat(3) @(negedge clk); rst_n=1;
        frame(0,0,0,1,1,note(EVENT_NOTE_ON,1,3,40,900));
        tick(1,0,0);
        send(3,note(EVENT_NOTE_ON,2,5,57,840));
        send(4,note(EVENT_NOTE_ON,1,7,52,900));
        tick(6,0,0);
        repeat(8500) tick(0,0,0);
        send(3,note(EVENT_NOTE_ON,2,5,85,780)); // third ROM region
        tick(2,0,0);
        repeat(4000) tick(0,0,0);
        send(0,note(EVENT_NOTE_OFF,2,5,85,0)); tick(0,2,0);
        send(3,note(EVENT_NOTE_ON,2,5,57,840)); tick(2,0,0);
        if(heard!==3'b111) $fatal(1,"all three real voices must produce PCM");
        send(4,note(EVENT_NOTE_ON,1,7,0,900)); // invalid guitar note keeps owner
        send(0,note(EVENT_NOTE_OFF,1,6,52,0)); // wrong channel
        send(0,note(EVENT_NOTE_OFF,2,5,56,0)); // wrong note
        tick(0,0,0);
        send(0,pedal(2,5,2048));
        send(0,pedal(1,7,4095));
        send(0,note(EVENT_NOTE_OFF,2,5,57,0));
        send(0,note(EVENT_NOTE_ON,1,7,52,0)); // velocity-zero release
        tick(0,0,0);
        send(0,pedal(1,6,0));
        tick(0,0,0);
        send(0,pedal(2,5,2047));
        send(0,pedal(1,7,0));
        tick(0,6,0);
        tick(0,0,0);
        if(guitar_pcm===0) $fatal(1,"release tail unexpectedly muted");
        send(4,note(EVENT_NOTE_ON,1,7,57,600));
        send(0,note(EVENT_NOTE_OFF,1,7,57,0)); // on then off across frames
        tick(4,0,0); tick(0,4,0);
        send(0,note(EVENT_ALL_NOTES_OFF,1,0,0,0));
        send(4,note(EVENT_NOTE_ON,3,7,60,700)); // retain new on after panic
        tick(0,0,5); tick(4,0,0);
        send(0,note(EVENT_ALL_NOTES_OFF,2,0,0,0));
        tick(0,0,2);
        @(negedge clk); sample_tick=1;
        @(posedge clk); #1;
        repeat(5) @(posedge clk);
        @(negedge clk); rst_n=0; sample_tick=0;
        #1; if(all_pcm!==0 || dut.frame_pending) $fatal(1,"reset during frame");
        @(negedge clk); rst_n=1;
        repeat(62) begin
            @(posedge clk); #1; if(all_pcm!==0 || dut.frame_pending) $fatal(1,"post reset ghost");
        end
        tick(0,0,0);
        $display("PASS C1_EXTRA_VOICES frames=%0d heard=%b max_cycles=%0d",frames,heard,max_cycles);
        $finish;
    end
    initial begin #40000000; $fatal(1,"watchdog"); end
endmodule
