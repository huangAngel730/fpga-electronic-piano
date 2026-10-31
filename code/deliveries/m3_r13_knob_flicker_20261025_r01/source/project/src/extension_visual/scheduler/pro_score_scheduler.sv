// Raw score scheduler, core-clock domain only. Asynchronous reset assertion;
// rst_n release must be synchronized by the caller. No human audio inputs.
// anchor_tick belongs to global_tick and denotes relative score tick zero.
module pro_score_scheduler #(
    parameter logic [31:0] MAX_SCORE_TICK = 32'd16777215,
    parameter integer READ_TIMEOUT_CYCLES = 16
) (
    input logic core_clk, rst_n, sample_tick,
    output logic event_valid,
    input logic event_ready,
    output audio_defs_pkg::performance_event_t event_data,
    input logic command_valid,
    input logic [1:0] command_kind,
    output logic command_ready, command_done,
    output logic [7:0] command_error,
    input logic committed_valid,
    input logic [9:0] committed_count,
    input logic [31:0] committed_score_id, committed_generation,
    input logic committed_bank, full_read_verified,
    output logic rd_req,
    output logic [8:0] rd_index,
    input logic rd_valid,
    input logic [63:0] rd_event,
    output logic lease_busy,
    output logic score_valid,
    input logic score_ready,
    output logic [97:0] score_payload,
    output logic flush_req,
    input logic flush_ack,
    input logic [31:0] anchor_frame, anchor_tick,
    input logic [11:0] anchor_phase,
    input logic anchor_valid,
    output logic [31:0] global_tick,
    output logic fault_latched
);
    import audio_defs_pkg::*;
    localparam logic [31:0] AUDIO_LEAD_TICKS = 32'd96768;
    localparam logic [3:0] IDLE=0, START_FLUSH=1, ISSUE=2, READ_WAIT=3,
        CHECK=4, ANCHOR=5, RUN=6, STOP_AUDIO=7, STOP_FLUSH=8, STOP_DRAIN=9,
        STOP_PENDING=10, PREP_DIV=11, VALIDATE=12;
    localparam logic [1:0] FETCH=0, MEM_WAIT=1, HOLD=2, FINISHED=3;
    logic [3:0] state;
    logic [1:0] audio_state, visual_state;
    logic [63:0] raw_mem [0:511];
    // Exact floor(5*raw_tick/4032) and remainder are prepared before START
    // success, so runtime endpoint ceil uses only a 13-bit sum/comparison.
    logic [26:0] qr_mem [0:511], end_qr_mem [0:511];
    logic [26:0] div_shift;
    logic [14:0] div_quotient;
    logic [11:0] div_remainder;
    logic [5:0] div_steps;
    logic [8:0] div_end_index;
    logic div_is_on;
    logic [26:0] last_qr;
    logic [8:0] active_on_index [0:2047];
    logic [2047:0] active;
    logic [11:0] active_count;
    logic [9:0] count, load_index, audio_index, visual_index;
    logic [31:0] bound_id, bound_generation, previous_tick;
    logic bound_bank;
    logic [31:0] f0, t0;
    logic [11:0] phase0;
    logic [31:0] wait_cycles;
    logic [11:0] anchor_wait_ticks;
    logic [63:0] audio_word, visual_word, held_audio;
    logic [63:0] read_word;
    // R09 hold #9/#10: buffer only the raw_mem write payload.
    // Validation, divider, previous_tick and all control/CE use read_word directly.
    (* syn_keep=1, syn_dont_touch=1 *) wire [1:0] raw_write_l0, raw_write_l1;
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_raw13_hold_0(.I0(read_word[13]),.F(raw_write_l0[0]));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_raw13_hold_1(.I0(raw_write_l0[0]),.F(raw_write_l1[0]));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_raw19_hold_0(.I0(read_word[19]),.F(raw_write_l0[1]));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_raw19_hold_1(.I0(raw_write_l0[1]),.F(raw_write_l1[1]));
    wire [63:0] raw_write_word={read_word[63:20],raw_write_l1[1],read_word[18:14],raw_write_l1[0],read_word[12:0]};
    logic [26:0] visual_qr_word, visual_end_qr_word;
    logic [31:0] held_visual_tick;
    logic [97:0] held_payload;
    logic [7:0] pending_error;
    // Once a valid offer has met backpressure, preserve it across command,
    // deadline and fault edges. Only handshake or explicit display epoch ACK
    // may retire that offer. The audio arbiter has no cancel input.
    logic audio_presented, visual_presented;
    wire [10:0] raw_key = {read_word[43:40],read_word[54:48]};
    wire is_on = read_word[39:32]==8'd0;
    wire identity_ok = committed_valid && committed_count==count &&
        committed_score_id==bound_id && committed_generation==bound_generation &&
        committed_bank==bound_bank;
    wire command_fire = command_valid && command_ready;
    wire malformed = read_word[39:32]>1 || read_word[47:40]>15 ||
        read_word[55:48]<36 || read_word[55:48]>84 || read_word[63:56]>127 ||
        (is_on && read_word[63:56]==0) || read_word[31:24]!=0 || read_word[31:0]>MAX_SCORE_TICK ||
        (load_index!=0 && read_word[31:0]<previous_tick) ||
        (is_on ? active[raw_key] : !active[raw_key]);
    wire active_clear = (command_fire && command_kind==0 && state==IDLE &&
        committed_valid && full_read_verified && committed_count!=0 && committed_count<=512) ||
        (state==STOP_FLUSH && flush_ack==flush_req);
    wire active_write = state==VALIDATE && !command_fire && identity_ok &&
        !malformed;
    // Static-bit guarded writes infer the device's native CE. Unlike the old
    // vector/dynamic-bit update, no bit's D input contains its own hold-Q mux.
    // Two bounded generate loops also respect the existing looplimit=2000.
    for(genvar active_channel=0; active_channel<16; active_channel=active_channel+1) begin:g_active
        for(genvar active_note=0; active_note<128; active_note=active_note+1) begin:g_note
            localparam integer ACTIVE_INDEX=active_channel*128+active_note;
            always_ff @(posedge core_clk or negedge rst_n) begin
                if(!rst_n) active[ACTIVE_INDEX]<=1'b0;
                else if(active_clear) active[ACTIVE_INDEX]<=1'b0;
                else if(active_write && raw_key==11'(ACTIVE_INDEX)) active[ACTIVE_INDEX]<=is_on;
            end
        end
    end
    wire [12:0] div_trial = {div_remainder,div_shift[26]};
    wire div_bit = div_trial>=13'd4032;
    wire [11:0] div_next_remainder = div_bit ? 12'(div_trial-13'd4032) : div_trial[11:0];
    wire [14:0] div_next_quotient = {div_quotient[13:0],div_bit};
    function automatic logic [14:0] ceil_from_qr(input logic [26:0] qr,
                                                 input logic [11:0] phase);
        logic [12:0] sum;
        begin
            sum={1'b0,qr[11:0]}+{1'b0,phase};
            ceil_from_qr=qr[26:12]+(sum==0 ? 15'd0 : sum<=4032 ? 15'd1 : 15'd2);
        end
    endfunction
    wire [14:0] hit_offset=ceil_from_qr(visual_qr_word,phase0);
    wire [14:0] end_offset=ceil_from_qr(visual_end_qr_word,phase0);
    // Both absolute endpoints share the same 33-bit base with no 33-bit wrap.
    // After checking end >= hit, the difference fits exactly in 15 bits.
    wire [14:0] duration_offset=end_offset-hit_offset;
    wire [32:0] hit_frame_wide={1'b0,f0}+33'd120+{18'd0,hit_offset};
    wire [32:0] end_frame_wide={1'b0,f0}+33'd120+{18'd0,end_offset};
    wire [14:0] anchor_last_offset=ceil_from_qr(last_qr,anchor_phase);
    wire [32:0] anchor_frame_end={1'b0,anchor_frame}+33'd120+{18'd0,anchor_last_offset};
    // Capture each absolute deadline on the same edge as its held row.
    // Runtime equality/late guards no longer combine t0 addition with a
    // 33-bit comparison and the other path's payload clock-enable. No extra
    // state or latency: these values are consumed only while that row is HOLD.
    logic [32:0] audio_due, visual_due;
    assign command_ready = rst_n && (state==IDLE || state==RUN ||
        ((command_kind==1 || command_kind==2) &&
         (state==START_FLUSH || state==ISSUE || state==READ_WAIT || state==VALIDATE || state==PREP_DIV || state==CHECK || state==ANCHOR)));
    assign lease_busy = rst_n && state!=IDLE;
    assign rd_req = rst_n && state==ISSUE;
    assign rd_index = load_index[8:0];
    wire visual_epoch_cancel = state==STOP_FLUSH && flush_ack==flush_req;
    assign score_valid = rst_n && !visual_epoch_cancel &&
        (visual_presented || (state==RUN && visual_state==HOLD &&
         !fault_latched && {1'b0,global_tick}==visual_due));
    assign score_payload = held_payload;
    always_comb begin
        event_valid = 1'b0;
        event_data = '0;
        if(rst_n && state==STOP_AUDIO) begin
            event_valid = 1'b1;
            event_data = make_all_notes_off(4'd14);
        end else if(rst_n && (audio_presented ||
                    (state==RUN && audio_state==HOLD &&
                     !fault_latched && {1'b0,global_tick}==audio_due))) begin
            event_valid = 1'b1;
            event_data = make_note_event(held_audio[39:32]==0,4'd14,
                held_audio[43:40],held_audio[54:48],
                midi_velocity_to_10bit(held_audio[62:56]));
        end
    end
    // No RAM clear: validity and active bitmap protect every uninitialized row.
    // Two synchronous read ports are only used after the write/prepare phase.
    always_ff @(posedge core_clk) begin
        audio_word <= raw_mem[audio_index[8:0]];
        visual_word <= raw_mem[visual_index[8:0]];
        visual_qr_word <= qr_mem[visual_index[8:0]];
        visual_end_qr_word <= end_qr_mem[visual_index[8:0]];
    end
    always_ff @(posedge core_clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; audio_state<=FETCH; visual_state<=FETCH;
            global_tick<=0; active_count<=0; count<=0;
            load_index<=0; audio_index<=0; visual_index<=0;
            bound_id<=0; bound_generation<=0; bound_bank<=0; previous_tick<=0;
            f0<=0; t0<=0; phase0<=0; wait_cycles<=0; anchor_wait_ticks<=0;
            held_audio<=0; held_payload<=0; held_visual_tick<=0; read_word<=0;
            audio_due<=0; visual_due<=0;
            command_done<=0; command_error<=0; pending_error<=0;
            flush_req<=0; fault_latched<=0; audio_presented<=0; visual_presented<=0;
            div_shift<=0; div_quotient<=0; div_remainder<=0; div_steps<=0;
            div_end_index<=0; div_is_on<=0; last_qr<=0;
        end else begin
            command_done<=0;
            if(sample_tick && global_tick!=32'hffffffff) global_tick<=global_tick+1'b1;
            if(state!=STOP_AUDIO && event_valid) audio_presented<=!event_ready;
            if(score_valid) visual_presented<=!score_ready;
            // A rejected START is independent of both data-path handshakes.
            if(command_fire && state==RUN && command_kind!=1 && command_kind!=2) begin
                command_done<=1; command_error<=command_kind==0 ? 8'd15 : 8'd13;
            end
            if(command_fire && !(state==RUN && command_kind!=1 && command_kind!=2)) begin
                command_error<=0;
                if(command_kind==0) begin
                    if(state!=IDLE) begin command_done<=1; command_error<=15; end
                    else if(!committed_valid || !full_read_verified || committed_count==0 ||
                            committed_count>512) begin command_done<=1; command_error<=13; end
                    else begin
                        count<=committed_count; bound_id<=committed_score_id;
                        bound_generation<=committed_generation; bound_bank<=committed_bank;
                        active_count<=0; load_index<=0; previous_tick<=0;
                        audio_index<=0; visual_index<=0; audio_state<=FETCH; visual_state<=FETCH;
                        pending_error<=0; fault_latched<=0;
                        audio_presented<=0; visual_presented<=0;
                        flush_req<=~flush_req; state<=START_FLUSH;
                    end
                end else if(command_kind==1 || command_kind==2) begin
                    pending_error<=0; state<=STOP_PENDING;
                end else begin command_done<=1; command_error<=13; end
            end else begin
                case(state)
                    IDLE: begin end
                    START_FLUSH: if(flush_ack==flush_req) state<=ISSUE;
                    ISSUE: begin state<=READ_WAIT; wait_cycles<=0; end
                    READ_WAIT: begin
                        if(!identity_ok) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else if(rd_valid) begin
                            // Native RAM data only drives this capture stage.
                            // The following cycle validates this stable word;
                            // late changes on rd_event cannot rewrite the row.
                            read_word<=rd_event; state<=VALIDATE;
                        end else if(wait_cycles>=READ_TIMEOUT_CYCLES-1) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else wait_cycles<=wait_cycles+1'b1;
                    end
                    VALIDATE: begin
                        if(!identity_ok) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else begin
                            if(malformed) begin
                                fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                            end else begin
                                raw_mem[load_index[8:0]]<=raw_write_word;
                                previous_tick<=read_word[31:0];
                                if(is_on) begin
                                    active_on_index[raw_key]<=load_index[8:0];
                                    active_count<=active_count+1'b1;
                                end else begin
                                    active_count<=active_count-1'b1;
                                end
                                div_shift<=({3'd0,read_word[23:0]}<<2)+{3'd0,read_word[23:0]};
                                div_quotient<=0; div_remainder<=0; div_steps<=27;
                                div_is_on<=is_on; div_end_index<=active_on_index[raw_key];
                                state<=PREP_DIV;
                            end
                        end
                    end
                    PREP_DIV: begin
                        div_shift<={div_shift[25:0],1'b0};
                        div_quotient<=div_next_quotient; div_remainder<=div_next_remainder;
                        div_steps<=div_steps-1'b1;
                        if(!identity_ok) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else if(div_steps==1) begin
                            qr_mem[load_index[8:0]]<={div_next_quotient,div_next_remainder};
                            if(!div_is_on) end_qr_mem[div_end_index]<={div_next_quotient,div_next_remainder};
                            last_qr<={div_next_quotient,div_next_remainder};
                            if(load_index+1'b1==count) state<=CHECK;
                            else begin load_index<=load_index+1'b1; state<=ISSUE; end
                        end
                    end
                    CHECK: begin
                        if(active_count!=0) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else begin state<=ANCHOR; anchor_wait_ticks<=0; end
                    end
                    ANCHOR: if(anchor_valid) begin
                        if(anchor_phase>=4032 ||
                           ({1'b0,anchor_tick}+{1'b0,previous_tick}+33'd96768)>33'h0ffffffff ||
                           anchor_frame_end[32]) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else begin
                            f0<=anchor_frame; t0<=anchor_tick; phase0<=anchor_phase;
                            command_done<=1; command_error<=0; state<=RUN;
                        end
                    end else if(sample_tick) begin
                        if(anchor_wait_ticks==2047) begin
                            pending_error<=13; state<=STOP_PENDING;
                        end else anchor_wait_ticks<=anchor_wait_ticks+1'b1;
                    end
                    RUN: begin
                        if(!identity_ok) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else if((audio_state==HOLD && {1'b0,global_tick}>audio_due) ||
                                    (visual_state==HOLD && {1'b0,global_tick}>visual_due)) begin
                            fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                        end else begin
                            case(audio_state)
                                FETCH: audio_state <= audio_index==count ? FINISHED : MEM_WAIT;
                                MEM_WAIT: begin
                                    held_audio<=audio_word;
                                    audio_due<={1'b0,t0}+{1'b0,audio_word[31:0]}+
                                        {1'b0,AUDIO_LEAD_TICKS};
                                    audio_state<=HOLD;
                                end
                                HOLD: if(event_valid && event_ready) begin
                                    audio_index<=audio_index+1'b1; audio_state<=FETCH;
                                end
                                default: begin end
                            endcase
                            case(visual_state)
                                FETCH: visual_state <= visual_index==count ? FINISHED : MEM_WAIT;
                                MEM_WAIT: begin
                                    if(visual_word[39:32]!=0) begin
                                        visual_index<=visual_index+1'b1; visual_state<=FETCH;
                                    end else if(hit_frame_wide[32] || end_frame_wide[32] ||
                                                end_offset<hit_offset) begin
                                        fault_latched<=1; pending_error<=13; state<=STOP_PENDING;
                                    end else begin
                                        held_payload<={6'd0,visual_index,visual_word[54:48],
                                            hit_frame_wide[31:0],1'b1,
                                            {17'd0,duration_offset},
                                            midi_velocity_to_10bit(visual_word[62:56])};
                                        held_visual_tick<=visual_word[31:0];
                                        visual_due<={1'b0,t0}+{1'b0,visual_word[31:0]};
                                        visual_state<=HOLD;
                                    end
                                end
                                HOLD: if(score_valid && score_ready) begin
                                    visual_index<=visual_index+1'b1; visual_state<=FETCH;
                                end
                                default: begin end
                            endcase
                        end
                    end
                    STOP_PENDING: if(!audio_presented) state<=STOP_AUDIO;
                    STOP_AUDIO: if(event_valid && event_ready) state<=STOP_DRAIN;
                    // The final audio router deasserts ready while scanning
                    // its source14 release list after accepting ALL_NOTES_OFF.
                    // Observe it idle on a later edge before flushing display.
                    // Also do not toggle over an unacknowledged START flush.
                    STOP_DRAIN: if(flush_ack==flush_req && event_ready) begin
                        flush_req<=~flush_req; state<=STOP_FLUSH;
                    end
                    STOP_FLUSH: if(flush_ack==flush_req) begin
                        active_count<=0; audio_state<=FINISHED; visual_state<=FINISHED;
                        visual_presented<=0;
                        command_done<=1; command_error<=pending_error; state<=IDLE;
                    end
                    default: begin fault_latched<=1; pending_error<=13; state<=STOP_PENDING; end
                endcase
            end
        end
    end
endmodule
