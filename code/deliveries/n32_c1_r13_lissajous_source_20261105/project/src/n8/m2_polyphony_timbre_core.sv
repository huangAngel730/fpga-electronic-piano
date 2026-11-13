// Isolated dual-timbre N-slot core. No board/I2S/clock generation or shared-package writes.
// Single clk; rst_n async assertion, synchronized release supplied upstream.
// 75-bit descriptor={PCM24,timbre1,note8,velocity10,baseFCW32}; NOT DSP context.
// All public diagnostic taps use the same pre-NBA convention as the frozen M1 reference.
module m2_polyphony_timbre_core #(
    parameter integer N=8, RESPONSE=1, SW=$clog2(N), TW=72+SW,
    parameter integer FRAME_LIMIT=833, ENABLE_C1_FX=0,
    parameter integer DRAIN_LIMIT=N*(RESPONSE+4)+64,
    parameter WAVE_FILE="rom/piano_band_4x256_8191.mem",
    parameter TRIANGLE_FILE="rom/triangle_wavetable.hex",
    parameter OCT_FILE="rom/oct_ratio_q16.mem",
    parameter SUB_FILE="rom/sub_ratio_q16.mem",
    parameter LFO_FILE="rom/lfo_sine_q15.mem"
) (
    input wire clk, rst_n, frame_tick, cancel_in,
    input wire [2:0] fx_mode,
    input wire [2:0] fx_timbre,
    input wire extra_pcm_ready,
    input wire signed [23:0] snare_pcm,sax_pcm,guitar_pcm,
    input wire event_valid, output wire event_ready, input wire [63:0] event_data,
    input wire sample_valid, output wire sample_ready, input wire [31:0] sample_id,
    output wire result_valid, input wire result_ready,
    output wire [31:0] result_id, output wire signed [23:0] left,right,
    output wire [7:0] clip_bits,
    output wire late, output wire [31:0] completion_cycles,
    output wire aborted, output wire [1:0] abort_reason,
    input wire config_valid, output wire config_ready,
    input wire config_enable, input wire [15:0] config_delay_samples,
    input wire [14:0] config_dry_gain,config_wet_gain,config_feedback,
    output wire idle, output wire fault,
    // Verification input is a real result-port injection, disabled by caller
    // for ordinary operation. It never replaces a simultaneous real result.
    input wire inject_valid, input wire [TW-1:0] inject_tag, input wire [74:0] inject_context,
    output wire inject_ready,
    input wire read_valid, input wire [SW-1:0] read_slot,
    output wire read_ready, read_out_valid, output wire [74:0] read_context,
    output wire [N-1:0] ons, offs, occupied, releasing,timbres,
    output wire [31:0] active_voice_count,
    output wire [N*10-1:0] velocities, output wire [N*32-1:0] bases, generations,
    output wire [N*8-1:0] notes, output wire [N*4-1:0] sources, channels,
    output wire issue_valid, output wire [TW-1:0] issue_tag, output wire [74:0] issue_context,
    output wire [1:0] issue_flags, output wire [28:0] issue_control,
    output wire issue_pedal,
    output wire write_valid, write_accepted, write_injected,
    output wire [TW-1:0] write_tag, output wire [74:0] write_context,
    output wire publish,
    output wire be_launch, advance, lane_valid,
    output wire [SW-1:0] lane_slot, output wire [1:0] lane_table,
    output wire lane_timbre,
    output wire [31:0] lane_phase, lane_triangle_phase, lane_fcw,
    output wire [N*32-1:0] piano_phases,triangle_phases,
    output wire signed [15:0] lane_wave, output wire [15:0] lane_env,
    output wire signed [23:0] lane_pcm,
    output wire [N*16-1:0] live_env, output wire [N*3-1:0] live_state,
    output logic [N*10-1:0] frame_velocity,
    output logic [N*32-1:0] frame_base, frame_gen,
    output logic [N*12-1:0] frame_bend, frame_mod,
    output logic [N*5-1:0] frame_range,
    output logic [N*4-1:0] frame_sources, frame_channels,
    output logic [N-1:0] frame_occupied,frame_timbres,
    // FW_PASSIVE_PORTS_BEGIN: one-way aliases only, same clk/pre-NBA.
    output wire [3:0] fw_state,
    output wire [31:0] fw_owned_id,
    output wire fw_owner,
    output wire fw_stop,
    output wire fw_router_busy,
    output wire fw_router_ready,
    output wire fw_control_event_ready,
    output wire fw_control_ready,
    output wire fw_control_valid,
    output wire [31:0] fw_control_id,
    output wire fw_sched_busy,
    output wire fw_sched_drain,
    output wire [N-1:0] fw_done_mask,
    output wire fw_be_empty,
    output wire fw_be_events_ready,
    output wire fw_be_valid,
    output wire fw_be_ready,
    output wire [31:0] fw_be_id,
    output wire fw_raw_valid,
    output wire fw_raw_ready,
    output wire [31:0] fw_raw_id,
    output wire fw_post_busy,
    output wire fw_same_identity
    // FW_PASSIVE_PORTS_END
);
    wire cancel=frame_tick || cancel_in;
    logic raw_valid,raw_late,raw_clip;
    wire raw_ready,post_busy,post_config_ready;
    logic [31:0] raw_id;
    logic signed [23:0] raw_left,raw_right;
    logic signed [31:0] raw_piano,raw_organ;
    wire signed [31:0] be_piano,be_organ;
    localparam IDLE=0, WAIT_ROUTER=1, SETTLE=2, CONTROL=3, WAIT_CONTROL=4,
        LOAD_CTL=5, LOAD_CFG=6, START=7, GATHER=8, LAUNCH=9, RUN=10,
        HOLD=11, DRAIN=12;
    logic [3:0] state;
    logic [2:0] delay_count;
    logic [SW-1:0] cfg_slot;
    logic [31:0] owned_id, age;
    logic [N*8-1:0] held_notes;
    logic [N-1:0] held_release, gathered, written;
    logic [N*32-1:0] held_base, held_gen;
    logic [31:0] held_identity_epoch;
    logic [N*10-1:0] held_velocity;
    logic [N*4-1:0] held_sources, held_channels;
    logic [N-1:0] held_occupied,held_timbres;
    logic [N*12-1:0] held_bend, held_mod;
    logic [N*5-1:0] held_range;
    logic [255:0] pedal_shadow; // mirrors accepted CC64/PANIC only, for B1 tags
    logic [TW-1:0] tags [0:N-1];
    logic [74:0] descriptors [0:N-1];
    wire note_pulse_valid;
    wire router_busy, router_ready, control_event_ready, be_empty, be_events_ready;
    wire sched_busy, sched_drain, cfg_ready, ctl_ready, begin_ready;
    wire commit_valid, sched_late;
    wire be_valid, be_ready, be_clipped, be_late;
    wire [31:0] be_id;
    wire signed [23:0] be_left, be_right;
    wire [N-1:0] be_mask;
    wire [N-1:0] done_mask;
    wire control_ready, control_valid;
    wire [31:0] control_id;
    wire [N-1:0] control_occupied;
    wire [N*4-1:0] control_sources, control_channels;
    wire [N*32-1:0] control_gen;
    wire [N*12-1:0] control_bend, control_mod;
    wire [N*5-1:0] control_range;
    wire identity_guard = state>=LOAD_CTL && state<=HOLD;
    // The original N32 guard compared all 1,312 identity bits continuously
    // and fed that cone through stop/cancel into the scheduler.  The router
    // now advances one registered epoch whenever an included identity field
    // changes (allocation or retirement).  Freezing and comparing that epoch
    // preserves the whole-frame identity fence without the cross-module cone.
    wire [31:0] identity_epoch;
    logic same_identity_q;
    // Register the frame-identity decision before it reaches stop/cancel and
    // the scheduler.  The direct epoch comparator otherwise fans out through
    // nearly every scheduler and state-bank clock enable.
    wire same_identity = same_identity_q;
    assign abort_reason = cancel ? 1 : identity_guard && !same_identity ? 2 : 0;
    assign aborted = state!=IDLE && state!=DRAIN && abort_reason!=0;
    wire stop = cancel || aborted;
    // A serialized N32 allocation/release remains part of the accepted event
    // transaction.  Do not let a sample claim the backend before the delayed
    // router pulse has been committed.
    assign idle = state==IDLE && !router_busy && !note_pulse_valid &&
        !sched_busy && be_empty && !post_busy;
    assign sample_ready = idle && !cancel && !read_valid && !config_valid;
    wire owner = idle && !sample_valid && !read_valid && !cancel && !config_valid;
    assign event_ready = router_ready && control_event_ready && be_events_ready;
    wire accepted_event = event_valid && event_ready;
    wire [N-1:0] release_done;
    assign release_done=done_mask;
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) same_identity_q<=1'b1;
        else if(!identity_guard) same_identity_q<=1'b1;
        else same_identity_q<=(identity_epoch==held_identity_epoch);
    end
    for(genvar i=0;i<N;i=i+1) begin:g_done
        // Retire only after the owned frame/postprocessor drains. Otherwise our
        // own zero-envelope retirement would invalidate its frozen identity.
        assign done_mask[i]=idle && occupied[i] && releasing[i] &&
            live_state[3*i+:3]==0 && !ons[i];
    end
    m2_polyphony_event_router #(.N(N)) router(
        .clk(clk),.rst_n(rst_n),.sample_owner_ready(owner && be_events_ready),
        .event_valid(event_valid && control_event_ready && be_events_ready),
        .event_ready(router_ready),.event_data(event_data),.dispatch_busy(router_busy),
        .note_pulse_valid(note_pulse_valid),
        .release_done(release_done),.slot_note_on(ons),.slot_note_off(offs),
        .slot_occupied(occupied),.slot_releasing(releasing),.slot_velocity(velocities),
        .slot_fcw(bases),.slot_notes(notes),.slot_timbre(timbres),
        .active_voice_count(active_voice_count),
        .slot_source_ids(sources),.slot_channel_ids(channels),.slot_generations(generations),
        .identity_epoch(identity_epoch));
    m2_polyphony_control_snapshot #(.N(N)) controls(
        .clk(clk),.rst_n(rst_n),.event_valid(accepted_event),.event_ready(control_event_ready),
        .event_data(event_data),.request_valid(state==CONTROL && !stop),
        .request_ready(control_ready),.request_id(owned_id),.slot_occupied(occupied),
        .slot_source_ids(sources),.slot_channels(channels),.slot_generations(generations),
        .snapshot_valid(control_valid),.snapshot_ready(state==WAIT_CONTROL || state==DRAIN),
        .snapshot_id(control_id),.snapshot_occupied(control_occupied),
        .snapshot_sources(control_sources),.snapshot_channels(control_channels),
        .snapshot_generations(control_gen),.snapshot_pitch_bend(control_bend),
        .snapshot_modulation(control_mod),.snapshot_pitch_range(control_range),
        .control_applied(),.invalid_range());
    wire [7:0] cfg_identity={held_sources[4*cfg_slot+:4],held_channels[4*cfg_slot+:4]};
    wire [74:0] cfg_context={24'd0,held_timbres[cfg_slot],held_notes[8*cfg_slot+:8],
        held_velocity[10*cfg_slot+:10],held_base[32*cfg_slot+:32]};
    wire [28:0] cfg_control={held_range[5*cfg_slot+:5],held_mod[12*cfg_slot+:12],
        held_bend[12*cfg_slot+:12]};
    wire req_valid;
    assign issue_valid=req_valid && state==GATHER && !stop;
    wire [TW-1:0] req_tag; wire [74:0] req_context;
    wire [1:0] req_flags;
    wire [28:0] req_control;
    wire req_pedal;
    assign issue_tag=req_tag; assign issue_context=req_context;
    assign issue_flags=req_flags; assign issue_control=req_control; assign issue_pedal=req_pedal;
    wire real_write=lane_valid && state==RUN && !stop;
    assign inject_ready=!real_write;
    assign write_valid=real_write || inject_valid;
    assign write_injected=!real_write && inject_valid;
    assign write_tag=real_write ? tags[lane_slot] : inject_tag;
    assign write_context=real_write ? {lane_pcm,descriptors[lane_slot][50:0]} : inject_context;
    assign publish=state==HOLD && raw_valid && raw_ready && !stop &&
        (!ENABLE_C1_FX || extra_pcm_ready);
    m2_polyphony_scheduler #(.N(N),.CW(75),.DRAIN_LIMIT(DRAIN_LIMIT),.FRAME_LIMIT(FRAME_LIMIT)) scheduler(
        .clk(clk),.rst_n(rst_n),.cancel(stop),.soft_reset(1'b0),
        .cfg_valid(state==LOAD_CFG && !stop),.cfg_ready(cfg_ready),.cfg_slot(cfg_slot),
        .cfg_identity({cfg_identity,held_gen[32*cfg_slot+:32]}),
        .cfg_flags({held_release[cfg_slot],held_occupied[cfg_slot]}),.cfg_context(cfg_context),
        .ctl_valid(state==LOAD_CTL && !stop && held_occupied[cfg_slot]),.ctl_ready(ctl_ready),.ctl_identity(cfg_identity),
        .ctl_value(cfg_control),.ctl_pedal(pedal_shadow[cfg_identity]),
        .begin_valid(state==START && !stop),.begin_ready(begin_ready),.begin_request(owned_id),
        .req_valid(req_valid),.req_ready(state==GATHER && !stop),.req_tag(req_tag),
        .req_context(req_context),.req_flags(req_flags),.req_control(req_control),.req_pedal(req_pedal),
        .res_valid(write_valid),.res_ready(),.res_tag(write_tag),.res_context(write_context),
        .res_accepted(write_accepted),.commit_valid(commit_valid),.commit_ready(publish),
        .commit_request(),.deadline_missed(sched_late),.rom_empty(be_empty),
        .engine_empty(be_empty),.result_empty(!be_valid && !lane_valid && !inject_valid),
        .busy(sched_busy),.draining(sched_drain),.drain_fault(fault),
        .read_valid(read_valid && idle),.read_ready(read_ready),.read_slot(read_slot),
        .read_out_valid(read_out_valid),.read_context(read_context));
    assign be_launch=state==LAUNCH && be_ready && !stop;
    m2_polyphony_audio_backend #(.N(N),.WAVE_RESPONSE_CYCLES(RESPONSE),
        .FRAME_LIMIT(FRAME_LIMIT),.WAVE_FILE(WAVE_FILE),.TRIANGLE_FILE(TRIANGLE_FILE),
        .OCT_FILE(OCT_FILE),.SUB_FILE(SUB_FILE),.LFO_FILE(LFO_FILE)) backend(
        // A front-end token cancellation must not suppress a router pulse for
        // an already accepted event while the mathematical backend is empty.
        // Only an actually owned backend transaction receives token cancel.
        .clk(clk),.rst_n(rst_n),.cancel(stop && !be_empty),.events_valid(note_pulse_valid),
        .events_ready(be_events_ready),.note_on(ons),.note_off(offs),.velocity(velocities),
        // Event table selection uses live FCW. The pitch engine consumes
        // the gathered frame FCW only at its accepted launch.
        .base_fcw(frame_base),.event_base_fcw(bases),.bend(frame_bend),.modulation(frame_mod),
        .pitch_range(frame_range),.occupied(frame_occupied),.timbres(frame_timbres),.sources(frame_sources),
        .channels(frame_channels),.generations(frame_gen),
        .layer_both(ENABLE_C1_FX && fx_mode==3'd2),
        .request_valid(state==LAUNCH && !stop),.request_ready(be_ready),.request_id(owned_id),
        .result_valid(be_valid),.result_ready(publish),.result_id(be_id),
        .result_sources(),.result_channels(),.result_generations(),.pcm_left(be_left),.pcm_right(be_right),
        .piano_pcm(be_piano),.organ_pcm(be_organ),
        .clipped(be_clipped),.deadline_missed(be_late),.completed_mask(be_mask),
        .advance_pulse(advance),.engine_empty(be_empty),.lane_valid(lane_valid),.lane_slot(lane_slot),
        .lane_wave(lane_wave),.lane_envelope(lane_env),.lane_pcm(lane_pcm),.lane_phase(lane_phase),
        .lane_fcw(lane_fcw),.lane_table(lane_table),.lane_timbre(lane_timbre),
        .lane_triangle_phase(lane_triangle_phase),.piano_phases(piano_phases),
        .triangle_phases(triangle_phases),.computed_fcw(),
        .live_envelopes(live_env),.live_states(live_state));
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            pedal_shadow<=0;
        end else if(accepted_event) begin
            if(event_data[63:61]==5) pedal_shadow<=0;
            else if(event_data[63:61]==4 && event_data[25:18]==6)
                pedal_shadow[event_data[60:53]]<=event_data[17:6]>=2048;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;delay_count<=0;cfg_slot<=0;owned_id<=0;age<=0;
            raw_valid<=0;raw_id<=0;raw_left<=0;raw_right<=0;raw_late<=0;raw_clip<=0;
            raw_piano<=0;raw_organ<=0;
            held_notes<=0;held_release<=0;gathered<=0;written<=0;
            held_base<=0;held_gen<=0;held_identity_epoch<=0;
            held_velocity<=0;held_sources<=0;held_channels<=0;
            held_occupied<=0;held_timbres<=0;held_bend<=0;held_mod<=0;held_range<=0;
            frame_velocity<=0;frame_base<=0;frame_gen<=0;frame_bend<=0;frame_mod<=0;
            frame_range<=0;frame_sources<=0;frame_channels<=0;frame_occupied<=0;frame_timbres<=0;
            for(integer j=0;j<N;j=j+1) begin tags[j]<=0;descriptors[j]<=0;end
        end else begin
            if(state!=IDLE && state!=HOLD && state!=DRAIN) age<=age+1'b1;
            if(stop) begin state<=DRAIN;raw_valid<=0;end
            else case(state)
                IDLE:if(sample_valid && sample_ready) begin
                    owned_id<=sample_id;age<=0;state<=WAIT_ROUTER;gathered<=0;written<=0;
                end
                WAIT_ROUTER:if(!router_busy && !note_pulse_valid) begin delay_count<=6;state<=SETTLE;end
                SETTLE:if(delay_count!=0) delay_count<=delay_count-1'b1;else state<=CONTROL;
                CONTROL:if(control_ready) begin
                    held_base<=bases;held_velocity<=velocities;held_notes<=notes;held_timbres<=timbres;
                    held_release<=releasing;held_identity_epoch<=identity_epoch;
                    state<=WAIT_CONTROL;
                end
                WAIT_CONTROL:if(control_valid) begin
                    // Router ownership and held_identity_epoch keep these
                    // identity fields stable throughout the serialized
                    // control read.  Sample the live table once instead of
                    // retaining a second 1,312-bit copy inside controls.
                    held_sources<=sources;held_channels<=channels;
                    held_gen<=generations;held_occupied<=occupied;
                    held_bend<=control_bend;held_mod<=control_mod;held_range<=control_range;
                    cfg_slot<=0;state<=LOAD_CTL;
                end
                // Unoccupied defaults must not overwrite another occupied voice's identity controls.
                LOAD_CTL:if(!held_occupied[cfg_slot] || ctl_ready) state<=LOAD_CFG;
                LOAD_CFG:if(cfg_ready) begin
                    if(cfg_slot==N-1) state<=START;
                    else begin cfg_slot<=cfg_slot+1'b1;state<=LOAD_CTL;end
                end
                START:if(begin_ready) state<=GATHER;
                GATHER:if(req_valid) begin
                    tags[req_tag[SW-1:0]]<=req_tag;descriptors[req_tag[SW-1:0]]<=req_context;
                    frame_base[32*req_tag[SW-1:0]+:32]<=req_context[31:0];
                    frame_velocity[10*req_tag[SW-1:0]+:10]<=req_context[41:32];
                    frame_timbres[req_tag[SW-1:0]]<=req_context[50];
                    frame_gen[32*req_tag[SW-1:0]+:32]<=req_tag[SW+31:SW];
                    frame_sources[4*req_tag[SW-1:0]+:4]<=req_tag[SW+39:SW+36];
                    frame_channels[4*req_tag[SW-1:0]+:4]<=req_tag[SW+35:SW+32];
                    frame_occupied[req_tag[SW-1:0]]<=req_flags[0];
                    frame_bend[12*req_tag[SW-1:0]+:12]<=req_control[11:0];
                    frame_mod[12*req_tag[SW-1:0]+:12]<=req_control[23:12];
                    frame_range[5*req_tag[SW-1:0]+:5]<=req_control[28:24];
                    gathered[req_tag[SW-1:0]]<=1;
                    if(req_tag[SW-1:0]==N-1) state<=LAUNCH;
                end
                LAUNCH:if(be_ready) state<=RUN;
                RUN:begin
                    if(real_write && write_accepted) written[lane_slot]<=1;
                    if(be_valid && commit_valid && (&written)) begin
                        raw_valid<=1;raw_id<=be_id;raw_left<=be_left;raw_right<=be_right;raw_clip<=be_clipped;
                        raw_piano<=be_piano;raw_organ<=be_organ;
                        raw_late<=age+1>=FRAME_LIMIT;state<=HOLD;
                    end
                end
                HOLD:if(publish) begin raw_valid<=0;state<=DRAIN;end
                DRAIN:if(!sched_busy && be_empty && control_ready && !control_valid) state<=IDLE;
                default:begin state<=DRAIN;raw_valid<=0;end
            endcase
        end
    end
    // Config is atomic with idle audio ownership, never concurrent with a sample.
    wire config_idle=idle && !sample_valid && !raw_valid && !cancel;
    assign config_ready=post_config_ready && config_idle;
    generate if(ENABLE_C1_FX) begin:g_c1_fx
        assign post_config_ready=1'b1;
        c1_pcm_effects post(
            .clk(clk),.rst_n(rst_n),.cancel(cancel_in),.frame_tick(frame_tick),
            .current_req_id(owned_id),.input_valid(raw_valid && !stop && extra_pcm_ready),.input_ready(raw_ready),
            .input_id(raw_id),.requested_mode(fx_mode),.requested_timbre(fx_timbre),
            .piano(raw_piano),.organ(raw_organ),.snare(snare_pcm),.sax(sax_pcm),.guitar(guitar_pcm),
            .upstream_clip(raw_clip),.result_valid(result_valid),.result_ready(result_ready),
            .result_id(result_id),.left(left),.right(right),.clip_bits(clip_bits),.busy(post_busy));
    end else begin:g_legacy_post
    m2_polyphony_pcm_adapter post(
        .clk(clk),.rst_n(rst_n),.cancel(cancel_in),.frame_tick(frame_tick),
        .current_req_id(owned_id),.input_valid(raw_valid && !stop),.input_ready(raw_ready),
        .input_id(raw_id),.input_left(raw_left),.input_right(raw_right),
        .input_clip_left(raw_clip),.input_clip_right(raw_clip),
        .config_valid(config_valid && config_idle),.config_ready(post_config_ready),
        .config_enable(config_enable),.config_delay_samples(config_delay_samples),
        .config_dry_gain(config_dry_gain),.config_wet_gain(config_wet_gain),
        .config_feedback(config_feedback),.result_valid(result_valid),.result_ready(result_ready),
        .result_id(result_id),.left(left),.right(right),.clip_bits(clip_bits),.busy(post_busy));
    end endgenerate
    // Completion timing excludes downstream HOLD duration. These are diagnostics,
    // not a substitute for independent input-to-output cycle/deadline checking.
    logic service_pending,recorded_late;
    logic [31:0] service_age,recorded_cycles;
    assign completion_cycles=result_valid ?
        (service_pending ? service_age+1'b1 : recorded_cycles) : 32'd0;
    assign late=result_valid && (service_pending ? service_age+1>=FRAME_LIMIT : recorded_late);
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            service_pending<=0;service_age<=0;recorded_cycles<=0;recorded_late<=0;
        end else if(cancel) service_pending<=0;
        else if(sample_valid && sample_ready) begin
            service_pending<=1;service_age<=0;recorded_cycles<=0;recorded_late<=0;
        end else if(service_pending) begin
            if(result_valid) begin
                recorded_cycles<=service_age+1'b1;
                recorded_late<=service_age+1>=FRAME_LIMIT;service_pending<=0;
            end else service_age<=service_age+1'b1;
        end
    end
    // synthesis translate_off
    always @(posedge clk) if(rst_n) begin
        if(note_pulse_valid !== ((|ons)||(|offs))) $fatal(1,"NOTE_PULSE_FENCE_MISMATCH");
        if(note_pulse_valid && state==LAUNCH) $fatal(1,"event and frame FCW ownership overlapped");
        if(note_pulse_valid && !be_events_ready) $fatal(1,"B2B_LOST_NOTE_PULSE");
        if(be_launch && gathered!={N{1'b1}}) $fatal(1,"B2B_MISSING_ROUTE_DESCRIPTOR");
        if(real_write && !write_accepted) $fatal(1,"B2B_REAL_RESULT_REJECTED");
        if(publish && (written!={N{1'b1}} || be_mask!={N{1'b1}})) $fatal(1,"B2B_INCOMPLETE_PUBLISH");
        if(fault) $fatal(1,"B2B_DRAIN_FAULT");
    end
    // synthesis translate_on
    // FW_PASSIVE_ALIASES_BEGIN: no state/control/fanback, not early per-ROM release.
    assign fw_state = state;
    assign fw_owned_id = owned_id;
    assign fw_owner = owner;
    assign fw_stop = stop;
    assign fw_router_busy = router_busy;
    assign fw_router_ready = router_ready;
    assign fw_control_event_ready = control_event_ready;
    assign fw_control_ready = control_ready;
    assign fw_control_valid = control_valid;
    assign fw_control_id = control_id;
    assign fw_sched_busy = sched_busy;
    assign fw_sched_drain = sched_drain;
    assign fw_done_mask = done_mask;
    assign fw_be_empty = be_empty;
    assign fw_be_events_ready = be_events_ready;
    assign fw_be_valid = be_valid;
    assign fw_be_ready = be_ready;
    assign fw_be_id = be_id;
    assign fw_raw_valid = raw_valid;
    assign fw_raw_ready = raw_ready;
    assign fw_raw_id = raw_id;
    assign fw_post_busy = post_busy;
    assign fw_same_identity = same_identity;
    // FW_PASSIVE_ALIASES_END
endmodule
