// Independent N4 integration of the ONE B2 hybrid candidate. No production use.
// Persistent router/control/DSP state is NEVER stored in the discardable B1
// token bank. Its 74-bit context is {PCM24,note8,velocity10,baseFCW32} only.
// Whole-domain rst_n asynchronously asserts; upstream synchronizes release.
module b2b_event_audio #(parameter integer RESPONSE=1) (
    input wire clk, rst_n, cancel,
    input wire event_valid, output wire event_ready, input wire [63:0] event_data,
    input wire sample_valid, output wire sample_ready, input wire [31:0] sample_id,
    output logic result_valid, input wire result_ready,
    output logic [31:0] result_id, output logic signed [23:0] left, right,
    output logic late, output wire aborted, output wire [1:0] abort_reason,
    output wire idle, output wire fault,
    // Verification input is a real result-port injection, disabled by caller
    // for ordinary operation. It never replaces a simultaneous real result.
    input wire inject_valid, input wire [73:0] inject_tag, inject_context,
    output wire inject_ready,
    input wire read_valid, input wire [1:0] read_slot,
    output wire read_ready, read_out_valid, output wire [73:0] read_context,
    output wire [3:0] ons, offs, occupied, releasing,
    output wire [39:0] velocities, output wire [127:0] bases, generations,
    output wire [31:0] notes, output wire [15:0] sources, channels,
    output wire issue_valid, output wire [73:0] issue_tag, issue_context,
    output wire [1:0] issue_flags, output wire [28:0] issue_control,
    output wire issue_pedal,
    output wire write_valid, write_accepted, write_injected,
    output wire [73:0] write_tag, write_context,
    output wire publish,
    output wire be_launch, advance, lane_valid,
    output wire [1:0] lane_slot, lane_table,
    output wire [31:0] lane_phase, lane_fcw,
    output wire signed [15:0] lane_wave, output wire [15:0] lane_env,
    output wire signed [23:0] lane_pcm,
    output wire [63:0] live_env, output wire [11:0] live_state,
    output logic [39:0] frame_velocity,
    output logic [127:0] frame_base, frame_gen,
    output logic [47:0] frame_bend, frame_mod,
    output logic [19:0] frame_range,
    output logic [15:0] frame_sources, frame_channels,
    output logic [3:0] frame_occupied
);
    localparam IDLE=0, WAIT_ROUTER=1, SETTLE=2, CONTROL=3, WAIT_CONTROL=4,
        LOAD_CTL=5, LOAD_CFG=6, START=7, GATHER=8, LAUNCH=9, RUN=10,
        HOLD=11, DRAIN=12;
    logic [3:0] state;
    logic [2:0] delay_count;
    logic [1:0] cfg_slot;
    logic [31:0] owned_id, age;
    logic [31:0] held_notes;
    logic [3:0] held_release, gathered, written;
    logic [127:0] held_base, held_gen;
    logic [39:0] held_velocity;
    logic [15:0] held_sources, held_channels;
    logic [3:0] held_occupied;
    logic [47:0] held_bend, held_mod;
    logic [19:0] held_range;
    logic [255:0] pedal_shadow; // mirrors accepted CC64/PANIC only, for B1 tags
    logic [73:0] tags [0:3], descriptors [0:3];
    wire router_busy, router_ready, control_event_ready, be_empty, be_events_ready;
    wire sched_busy, sched_drain, cfg_ready, ctl_ready, begin_ready;
    wire commit_valid, sched_late;
    wire be_valid, be_ready, be_clipped, be_late;
    wire [31:0] be_id;
    wire signed [23:0] be_left, be_right;
    wire [3:0] be_mask;
    wire [3:0] done_mask;
    wire control_ready, control_valid;
    wire [31:0] control_id;
    wire [3:0] control_occupied;
    wire [15:0] control_sources, control_channels;
    wire [127:0] control_gen;
    wire [47:0] control_bend, control_mod;
    wire [19:0] control_range;
    wire identity_guard = state>=LOAD_CTL && state<=HOLD;
    wire same_identity = occupied==held_occupied && sources==held_sources &&
        channels==held_channels && generations==held_gen;
    assign abort_reason = cancel ? 1 : identity_guard && !same_identity ? 2 : 0;
    assign aborted = rst_n && state!=IDLE && state!=DRAIN && abort_reason!=0;
    wire stop = cancel || aborted;
    assign idle = state==IDLE && !sched_busy && be_empty;
    assign sample_ready = rst_n && idle && !cancel && !read_valid;
    wire owner = idle && !sample_valid && !read_valid && !cancel;
    assign event_ready = router_ready && control_event_ready && be_events_ready;
    wire accepted_event = event_valid && event_ready;
    wire [3:0] release_done;
`ifdef B2B_MUTANT_NO_RETIRE
    assign release_done=0;
`else
    assign release_done=done_mask;
`endif
    for(genvar i=0;i<4;i=i+1) begin:g_done
        assign done_mask[i]=rst_n && occupied[i] && releasing[i] &&
            live_state[3*i+:3]==0 && !ons[i];
    end
    polyphonic_event_router router(
        .clk(clk),.rst_n(rst_n),.sample_owner_ready(owner && be_events_ready),
        .event_valid(event_valid && control_event_ready && be_events_ready),
        .event_ready(router_ready),.event_data(event_data),.dispatch_busy(router_busy),
        .release_done(release_done),.slot_note_on(ons),.slot_note_off(offs),
        .slot_occupied(occupied),.slot_releasing(releasing),.slot_velocity(velocities),
        .slot_fcw(bases),.slot_notes(notes),.active_voice_count(),
        .slot_source_ids(sources),.slot_channel_ids(channels),.slot_generations(generations));
    performance_control_snapshot controls(
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
    wire [73:0] cfg_context={24'd0,held_notes[8*cfg_slot+:8],
        held_velocity[10*cfg_slot+:10],held_base[32*cfg_slot+:32]};
    wire [28:0] cfg_control={held_range[5*cfg_slot+:5],held_mod[12*cfg_slot+:12],
        held_bend[12*cfg_slot+:12]};
    wire req_valid;
    assign issue_valid=req_valid && state==GATHER && !stop;
    wire [73:0] req_tag, req_context;
    wire [1:0] req_flags;
    wire [28:0] req_control;
    wire req_pedal;
    assign issue_tag=req_tag; assign issue_context=req_context;
    assign issue_flags=req_flags; assign issue_control=req_control; assign issue_pedal=req_pedal;
    wire real_write=lane_valid && state==RUN && !stop;
    assign inject_ready=rst_n && !real_write;
    assign write_valid=real_write || inject_valid;
    assign write_injected=!real_write && inject_valid;
    assign write_tag=real_write ? tags[lane_slot] : inject_tag;
    assign write_context=real_write ? {lane_pcm,descriptors[lane_slot][49:0]} : inject_context;
    assign publish=state==HOLD && result_valid && result_ready && !stop;
    b1_scheduler #(.N(4),.CW(74),.DRAIN_LIMIT(128)) scheduler(
        .clk(clk),.rst_n(rst_n),.cancel(stop),.soft_reset(1'b0),
        .cfg_valid(state==LOAD_CFG && !stop),.cfg_ready(cfg_ready),.cfg_slot(cfg_slot),
        .cfg_identity({cfg_identity,held_gen[32*cfg_slot+:32]}),
        .cfg_flags({held_release[cfg_slot],held_occupied[cfg_slot]}),.cfg_context(cfg_context),
        .ctl_valid(state==LOAD_CTL && !stop),.ctl_ready(ctl_ready),.ctl_identity(cfg_identity),
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
    b2_audio_backend #(.N(4),.WAVE_RESPONSE_CYCLES(RESPONSE)) backend(
        // A front-end token cancellation must not suppress a router pulse for
        // an already accepted event while the mathematical backend is empty.
        // Only an actually owned backend transaction receives token cancel.
        .clk(clk),.rst_n(rst_n),.cancel(stop && !be_empty),.events_valid((|ons)||(|offs)),
        .events_ready(be_events_ready),.note_on(ons),.note_off(offs),.velocity(velocities),
        // Events use live base FCW; a request uses the gathered B1 snapshot.
        .base_fcw(state==LAUNCH ? frame_base : bases),.bend(frame_bend),.modulation(frame_mod),
        .pitch_range(frame_range),.occupied(frame_occupied),.sources(frame_sources),
        .channels(frame_channels),.generations(frame_gen),
        .request_valid(state==LAUNCH && !stop),.request_ready(be_ready),.request_id(owned_id),
        .result_valid(be_valid),.result_ready(publish),.result_id(be_id),
        .result_sources(),.result_channels(),.result_generations(),.pcm_left(be_left),.pcm_right(be_right),
        .clipped(be_clipped),.deadline_missed(be_late),.completed_mask(be_mask),
        .advance_pulse(advance),.engine_empty(be_empty),.lane_valid(lane_valid),.lane_slot(lane_slot),
        .lane_wave(lane_wave),.lane_envelope(lane_env),.lane_pcm(lane_pcm),.lane_phase(lane_phase),
        .lane_fcw(lane_fcw),.lane_table(lane_table),.computed_fcw(),
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
            result_valid<=0;result_id<=0;left<=0;right<=0;late<=0;
            held_notes<=0;held_release<=0;gathered<=0;written<=0;
            held_base<=0;held_gen<=0;held_velocity<=0;held_sources<=0;held_channels<=0;
            held_occupied<=0;held_bend<=0;held_mod<=0;held_range<=0;
            frame_velocity<=0;frame_base<=0;frame_gen<=0;frame_bend<=0;frame_mod<=0;
            frame_range<=0;frame_sources<=0;frame_channels<=0;frame_occupied<=0;
            for(integer j=0;j<4;j=j+1) begin tags[j]<=0;descriptors[j]<=0;end
        end else begin
            if(state!=IDLE && state!=HOLD && state!=DRAIN) age<=age+1'b1;
            if(stop) begin state<=DRAIN;result_valid<=0;end
            else case(state)
                IDLE:if(sample_valid && sample_ready) begin
                    owned_id<=sample_id;age<=0;state<=WAIT_ROUTER;gathered<=0;written<=0;
                end
                WAIT_ROUTER:if(!router_busy && !(|ons) && !(|offs)) begin delay_count<=6;state<=SETTLE;end
                SETTLE:if(delay_count!=0) delay_count<=delay_count-1'b1;else state<=CONTROL;
                CONTROL:if(control_ready) begin
                    held_base<=bases;held_velocity<=velocities;held_notes<=notes;
                    held_release<=releasing;state<=WAIT_CONTROL;
                end
                WAIT_CONTROL:if(control_valid) begin
                    held_sources<=control_sources;held_channels<=control_channels;
                    held_gen<=control_gen;held_occupied<=control_occupied;
                    held_bend<=control_bend;held_mod<=control_mod;held_range<=control_range;
                    cfg_slot<=0;state<=LOAD_CTL;
                end
                LOAD_CTL:if(ctl_ready) state<=LOAD_CFG;
                LOAD_CFG:if(cfg_ready) begin
                    if(cfg_slot==3) state<=START;
                    else begin cfg_slot<=cfg_slot+1'b1;state<=LOAD_CTL;end
                end
                START:if(begin_ready) state<=GATHER;
                GATHER:if(req_valid) begin
                    tags[req_tag[1:0]]<=req_tag;descriptors[req_tag[1:0]]<=req_context;
                    frame_base[32*req_tag[1:0]+:32]<=req_context[31:0];
                    frame_velocity[10*req_tag[1:0]+:10]<=req_context[41:32];
                    frame_gen[32*req_tag[1:0]+:32]<=req_tag[33:2];
                    frame_sources[4*req_tag[1:0]+:4]<=req_tag[41:38];
                    frame_channels[4*req_tag[1:0]+:4]<=req_tag[37:34];
                    frame_occupied[req_tag[1:0]]<=req_flags[0];
                    frame_bend[12*req_tag[1:0]+:12]<=req_control[11:0];
                    frame_mod[12*req_tag[1:0]+:12]<=req_control[23:12];
                    frame_range[5*req_tag[1:0]+:5]<=req_control[28:24];
                    gathered[req_tag[1:0]]<=1;
                    if(req_tag[1:0]==3) state<=LAUNCH;
                end
                LAUNCH:if(be_ready) state<=RUN;
                RUN:begin
                    if(real_write && write_accepted) written[lane_slot]<=1;
                    if(be_valid && commit_valid && (&written)) begin
                        result_valid<=1;result_id<=be_id;left<=be_left;right<=be_right;
                        late<=age+1>=833;state<=HOLD;
                    end
                end
                HOLD:if(publish) begin result_valid<=0;state<=DRAIN;end
                DRAIN:if(!sched_busy && be_empty && control_ready && !control_valid) state<=IDLE;
                default:begin state<=DRAIN;result_valid<=0;end
            endcase
        end
    end
    // synthesis translate_off
    always @(posedge clk) if(rst_n) begin
        if(((|ons)||(|offs)) && !be_events_ready) $fatal(1,"B2B_LOST_NOTE_PULSE");
        if(be_launch && gathered!=4'hf) $fatal(1,"B2B_MISSING_ROUTE_DESCRIPTOR");
        if(real_write && !write_accepted) $fatal(1,"B2B_REAL_RESULT_REJECTED");
        if(publish && (written!=4'hf || be_mask!=4'hf)) $fatal(1,"B2B_INCOMPLETE_PUBLISH");
        if(fault) $fatal(1,"B2B_DRAIN_FAULT");
    end
    // synthesis translate_on
endmodule
