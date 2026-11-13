// Three independently clocked-by-enable monophonic voices for the C1 candidate.
module c1_extra_voices #(
    parameter SAX_SOFT_ROM = "src/c1_extra/rom/sax_soft.hex",
    parameter SAX_HARD_ROM = "src/c1_extra/rom/sax_hard.hex",
    parameter SAX_NOISE_ROM = "src/c1_extra/rom/noise_levels.hex"
) (
    input wire clk, rst_n, sample_tick, event_take,
    input wire [2:0] selected,
    input audio_defs_pkg::performance_event_t event_data,
    output wire signed [23:0] snare_pcm, sax_pcm, guitar_pcm,
    output wire frame_pcm_ready
);
    import audio_defs_pkg::*;
    localparam integer SNARE=0, SAX=1, GUITAR=2;
    localparam logic [2:0] ALL_VOICES=3'b111;
    localparam logic [2:0] ENSEMBLE_SELECTION=3'd5;
    logic event_take_q,launch_pending,frame_pending;
    logic [2:0] selected_q;
    performance_event_t event_q;
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            event_take_q<=0;event_q<='0;selected_q<=0;launch_pending<=0;
        end else begin
            event_take_q<=event_take;
            if(event_take) begin event_q<=event_data;selected_q<=selected;end
            launch_pending<=sample_tick && !frame_pending && !launch_pending;
        end
    end
    wire [7:0] event_channel={event_q.source_id,event_q.channel};
    wire [31:0] event_fcw;
    note_pitch u_pitch(.note_number(event_q.note_number),.phase_step(event_fcw));
    wire [6:0] event_velocity=event_q.velocity[9:3]==0 ?
        7'd1 : event_q.velocity[9:3];
    wire event_on=event_q.event_type==EVENT_NOTE_ON && event_q.velocity!=0;
    wire event_off=event_q.event_type==EVENT_NOTE_OFF ||
        (event_q.event_type==EVENT_NOTE_ON && event_q.velocity==0);
    wire event_pedal=event_q.event_type==EVENT_CONTROL_CHANGE &&
        event_q.control_id==CTRL_SUSTAIN;
    wire pedal_down=event_q.control_value>=12'd2048;
    wire event_panic=event_q.event_type==EVENT_ALL_NOTES_OFF;

    logic [255:0] sustain;
    logic [2:0] owned, key_down, deferred, pending_on, pending_off, pending_kill;
    logic [7:0] owner_channel[0:2];
    logic [6:0] owner_note[0:2], velocity[0:2];
    logic [31:0] fcw[0:2];
    assign frame_pcm_ready=!frame_pending && !launch_pending;
    wire launch=launch_pending;
    wire [2:0] fire_kill=pending_kill & {3{launch}};
    wire [2:0] fire_on=pending_on & ~pending_kill & {3{launch}};
    wire [2:0] fire_off=pending_off & ~pending_on & ~pending_kill & {3{launch}};
    wire [2:0] voice_valid;
    wire signed [23:0] voice_pcm[0:2];
    logic [2:0] done;
    logic signed [23:0] captured[0:2], published[0:2];
    assign snare_pcm=published[SNARE];
    assign sax_pcm=published[SAX];
    assign guitar_pcm=published[GUITAR];

    snare_voice u_snare(
        .clk(clk),.rst_n(rst_n),.sample_tick(launch),
        .note_on(fire_on[SNARE]),.note_off(fire_off[SNARE]),.kill(fire_kill[SNARE]),
        .velocity(velocity[SNARE]),.fcw(fcw[SNARE]),.pcm(voice_pcm[SNARE]),
        .pcm_valid(voice_valid[SNARE]),.busy(),.active(),.protocol_error(),.invalid_pitch());
    sax_voice_r05 #(
        .SOFT_ROM_FILE(SAX_SOFT_ROM),.HARD_ROM_FILE(SAX_HARD_ROM),.NOISE_ROM_FILE(SAX_NOISE_ROM)
    ) u_sax(
        .clk(clk),.rst_n(rst_n),.sample_tick(launch),
        .note_on(fire_on[SAX]),.note_off(fire_off[SAX]),.kill(fire_kill[SAX]),
        .velocity(velocity[SAX]),.fcw(fcw[SAX]),.pcm(voice_pcm[SAX]),
        .pcm_valid(voice_valid[SAX]),.busy(),.active(),.protocol_error(),.invalid_pitch());
    guitar_voice u_guitar(
        .clk(clk),.rst_n(rst_n),.sample_tick(launch && !fire_kill[GUITAR]),
        .note_on(fire_on[GUITAR]),.note_off(fire_off[GUITAR]),.kill(fire_kill[GUITAR]),
        .velocity(velocity[GUITAR]),.fcw(fcw[GUITAR]),.pcm(voice_pcm[GUITAR]),
        .pcm_valid(voice_valid[GUITAR]),.busy(),.active(),.protocol_error(),.invalid_pitch());

    // Event order is explicit. A frame launches older pending actions; the
    // event accepted on that edge belongs to the following frame.
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            sustain<=0; owned<=0; key_down<=0; deferred<=0;
            pending_on<=0; pending_off<=0; pending_kill<=0;
            for(i=0;i<3;i=i+1) begin
                owner_channel[i]<=0; owner_note[i]<=0; velocity[i]<=0; fcw[i]<=0;
            end
        end else begin
            if(event_take_q && event_pedal) sustain[event_channel]<=pedal_down;
            if(event_take_q && event_panic) sustain[{event_q.source_id,4'b0}+:16]<=16'b0;
            for(i=0;i<3;i=i+1) begin
                if(launch) begin
                    if(pending_kill[i]) pending_kill[i]<=0;
                    else if(pending_on[i]) pending_on[i]<=0;
                    else if(pending_off[i]) pending_off[i]<=0;
                end
                if(event_take_q) begin
                    if(event_on && (selected_q==3'(i+2) || selected_q==ENSEMBLE_SELECTION) &&
                       (i==SNARE ||
                        (i==SAX && event_fcw!=0 && event_fcw<=32'h40000000) ||
                        (i==GUITAR && event_fcw>=32'd7000000 && event_fcw<=32'd120000000))) begin
                        owned[i]<=1; key_down[i]<=1; deferred[i]<=0;
                        owner_channel[i]<=event_channel; owner_note[i]<=event_q.note_number;
                        velocity[i]<=event_velocity; fcw[i]<=event_fcw;
                        pending_on[i]<=1; pending_off[i]<=0;
                    end else if(event_off && owned[i] && key_down[i] &&
                                owner_channel[i]==event_channel &&
                                owner_note[i]==event_q.note_number) begin
                        key_down[i]<=0;
                        if(i!=SNARE && sustain[event_channel]) deferred[i]<=1;
                        else pending_off[i]<=1;
                    end else if(event_pedal && !pedal_down && owned[i] && deferred[i] &&
                                owner_channel[i]==event_channel) begin
                        deferred[i]<=0; pending_off[i]<=1;
                    end else if(event_panic && owned[i] &&
                                owner_channel[i][7:4]==event_q.source_id) begin
                        owned[i]<=0; key_down[i]<=0; deferred[i]<=0;
                        pending_on[i]<=0; pending_off[i]<=0; pending_kill[i]<=1;
                    end
                end
            end
        end
    end

    // Different leaf latencies are hidden behind an atomic frame publish.
    // A guitar kill produces no valid pulse, so seed its completion with zero.
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            frame_pending<=0; done<=0;
            for(j=0;j<3;j=j+1) begin captured[j]<=0; published[j]<=0; end
        end else if(launch) begin
            frame_pending<=1;
            done<={fire_kill[GUITAR],2'b00};
            if(fire_kill[GUITAR]) captured[GUITAR]<=0;
        end else if(frame_pending) begin
            done<=done|voice_valid;
            for(j=0;j<3;j=j+1) begin
                if(voice_valid[j]) captured[j]<=voice_pcm[j];
                if((done|voice_valid)==ALL_VOICES)
                    published[j]<=voice_valid[j] ? voice_pcm[j] : captured[j];
            end
            if((done|voice_valid)==ALL_VOICES) frame_pending<=0;
        end
    end
endmodule
