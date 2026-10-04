`timescale 1ns/1ps
module tb_t027_dynamic_bank;
    import audio_defs_pkg::*;
    logic clk=0;
    always #10 clk=~clk; // 50 MHz
    logic rst_n=0, event_valid=0, frame_tick=0, sample_req=0, result_ready=0;
    logic [63:0] event_data=0;
    logic [31:0] sample_req_id=0;
    wire event_ready,calc_ready,result_valid;
    wire [31:0] result_req_id,active_voice_count;
    wire [63:0] result_envelopes,result_waves;
    wire [127:0] result_fcw;
    wire [3:0] result_occupied;
    wire [11:0] result_states;
    logic signed [15:0] triangle [0:1023];
    wire signed [15:0] baseline_piano [0:3];
    logic signed [15:0] baseline_delay [0:3][0:2];
    logic [31:0] reference_phase [0:3];
    logic [3:0] expected_timbre=0;
    integer checks=0,samples=0;
    integer capture_fd=0;
    string capture_path;
    logic capture_enabled=0;

    polyphonic_envelope_bank #(.DYNAMIC_TIMBRE_ENABLE(1'b1),
        .WAVE_ROM_FILE("piano_band_4x256_8191.mem"),
        .SINE_ROM_FILE("sine_wavetable.hex"),
        .TRIANGLE_ROM_FILE("triangle_wavetable.hex")) dut (.*);

    // Independent legacy V1 lane instantiation checks Program 0 remains
    // byte-for-byte equal to the released piano path despite the adapter.
    for(genvar g=0;g<4;g++)begin:g_baseline
        piano_dds_oscillator #(.ROM_FILE("piano_band_4x256_8191.mem")) u_piano (
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(dut.lane_tick),
            .note_on(dut.slot_note_on[g]),.velocity(dut.slot_velocity[10*g+:10]),
            .fcw(dut.slot_fcw[32*g+:32]),.wt_sample(baseline_piano[g])
        );
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n)begin
                baseline_delay[g][0]<='0;baseline_delay[g][1]<='0;
                baseline_delay[g][2]<='0;
            end else begin
                baseline_delay[g][0]<=baseline_piano[g];
                baseline_delay[g][1]<=baseline_delay[g][0];
                baseline_delay[g][2]<=baseline_delay[g][1];
            end
        end
    end

    task automatic check(input logic cond, input string name);
        checks++;
        if(cond!==1'b1)$fatal(1,"T027 %s checks=%0d samples=%0d",name,checks,samples);
    endtask
    task automatic send(input logic [2:0] kind,input logic [3:0] src,ch,
                        input logic [6:0] note,input logic [9:0] velocity,
                        input logic [7:0] control_id,input logic [11:0] value);
        performance_event_t e;
        e='0;e.event_type=kind;e.source_id=src;e.channel=ch;
        e.note_number=note;e.velocity=velocity;e.control_id=control_id;e.control_value=value;
        wait(event_ready);@(negedge clk);event_data=e;event_valid=1;
        @(negedge clk);event_valid=0;wait(event_ready);repeat(3)@(negedge clk);
    endtask
    task automatic sample_once;
        logic [31:0] step;
        logic [9:0] addr;
        logic signed [15:0] expected_value;
        wait(calc_ready);@(negedge clk);sample_req_id++;
        sample_req=1;@(negedge clk);sample_req=0;
        wait(result_valid);@(negedge clk);
        check(result_req_id==sample_req_id,"request generation");
        for(integer i=0;i<4;i++)begin
            step=result_fcw[32*i+:32];
            addr=reference_phase[i][31:22];
            expected_value=expected_timbre[i] ? triangle[addr] : baseline_delay[i][2];
            check($signed(result_waves[16*i+:16])===expected_value,
                $sformatf("lane=%0d addr=%0d timbre=%0d exp=%0d got=%0d",
                    i,addr,expected_timbre[i],expected_value,
                    $signed(result_waves[16*i+:16])));
            reference_phase[i]=reference_phase[i]+step;
        end
        if(capture_enabled) $fdisplay(capture_fd,"%0d %0d",
            $signed(result_waves[15:0]),$signed(result_waves[31:16]));
        samples++;
        @(negedge clk);result_ready=1;@(negedge clk);result_ready=0;
        check(!result_valid,"result handshake");
    endtask
    initial begin
        if(!$value$plusargs("CAPTURE=%s",capture_path))$fatal(1,"T027 missing +CAPTURE");
        capture_fd=$fopen(capture_path,"w");
        if(!capture_fd)$fatal(1,"T027 capture open failed");
        $readmemh("triangle_wavetable.hex",triangle);
        for(integer i=0;i<1024;i++)
            check((^triangle[i]!==1'bx),"triangle ROM initialized");
        for(integer i=0;i<4;i++)reference_phase[i]=0;
        repeat(3)@(negedge clk);rst_n=1;
        // Program 0 remains Piano V1; Program 1 selects triangle on next Note On.
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,1);
        send(EVENT_NOTE_ON,2,3,60,900,0,0);expected_timbre[0]=1;
        send(EVENT_NOTE_ON,2,4,62,900,0,0); // same source, different channel -> V1
        send(EVENT_NOTE_ON,3,3,64,900,0,0); // same channel, different source -> V1
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,0);
        send(EVENT_NOTE_ON,2,3,65,900,0,0); // changed program -> V1 slot 3
        check(active_voice_count==4,"four independent voices");
        repeat(50)sample_once();
        // Program changes during sustain must not change a sounding slot.
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,1);
        repeat(24)sample_once();
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,0);
        send(EVENT_NOTE_ON,2,3,60,500,0,0); // same identity, reuses lane 0
        expected_timbre[0]=0;
        repeat(24)sample_once();
        // Unsupported program is ignored, not wrapped to 0/1.
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,127);
        send(EVENT_NOTE_ON,2,3,60,700,0,0);
        repeat(24)sample_once();
        check(active_voice_count==4,"program change does not allocate/release");
        check(samples==122,"sample count");
        // Same MIDI A4, Program 1 triangle versus Program 0 approved Piano V1.
        rst_n=0;repeat(4)@(negedge clk);
        for(integer i=0;i<4;i++)reference_phase[i]=0;
        expected_timbre=0;
        rst_n=1;
        send(EVENT_NOTE_ON,2,3,69,900,0,0);
        check(dut.slot_timbre[0]==0,"reset clears previous Program 1");
        send(EVENT_CONTROL_CHANGE,2,3,0,0,CTRL_VOICE_SELECT,1);
        send(EVENT_NOTE_ON,2,3,69,900,0,0);expected_timbre[0]=1;
        send(EVENT_NOTE_ON,2,4,69,900,0,0);
        check(dut.slot_timbre[0] && !dut.slot_timbre[1],"A4 mixed programs");
        repeat(1500)sample_once();
        capture_enabled=1;
        repeat(2048)sample_once();
        capture_enabled=0;
        $fclose(capture_fd);
        check(samples==3670,"total sample count");
        $display("PASS T027 dynamic four-lane samples=%0d checks=%0d",samples,checks);
        $finish;
    end
    initial begin #10000000;$fatal(1,"T027 timeout");end
endmodule
