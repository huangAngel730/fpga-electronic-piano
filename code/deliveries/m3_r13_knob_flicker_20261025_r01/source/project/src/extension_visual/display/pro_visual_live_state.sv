// Video-domain physical-key-duration bars. Audio has no dependency on this
// bounded display state. All published geometry is a frame_start snapshot.
`timescale 1ns/1ps
module pro_visual_live_state #(
    parameter integer SLOT_COUNT=32, Y_WIDTH=10, JUDGE_Y=400, RISE_STEP=4
) (
    input logic clk,rst_n,frame_start,performance_fire,flush,
    input audio_defs_pkg::performance_event_t performance_data,
    input logic video_desync,
    output logic [127:0] key_down,
    output logic [SLOT_COUNT-1:0] live_valid,
    output logic [SLOT_COUNT*7-1:0] live_note_number,
    output logic [SLOT_COUNT*Y_WIDTH-1:0] live_y,
    output logic [SLOT_COUNT*Y_WIDTH-1:0] live_end_y,
    output logic [SLOT_COUNT-1:0] live_held,
    output logic [SLOT_COUNT*10-1:0] live_velocity,
    output logic [31:0] visual_slot_drop_count,
    output logic desync_latched,
    output wire [31:0] pending_drop_count
);
    import audio_defs_pkg::*;
    // Reachable geometry starts at 0/JUDGE_Y/JUDGE_Y+10 and only saturates
    // downward. Store that range, zero-extending at the unchanged Y_WIDTH ports.
    // Wide constants avoid overflow before the existing parameter guards run.
    localparam logic [63:0] MAX_GEOM=64'(JUDGE_Y)+64'd10;
    localparam integer GEOM_WIDTH=(MAX_GEOM<1)?1:$clog2(MAX_GEOM+64'd1);
    localparam logic [GEOM_WIDTH-1:0] RISE_GEOM=GEOM_WIDTH'(RISE_STEP);
    localparam bit STEP_EXCEEDS_RANGE=(64'(RISE_STEP)>MAX_GEOM);
    logic [SLOT_COUNT-1:0] valid_q,valid_d,held_q,held_d;
    logic [6:0] note_q[0:SLOT_COUNT-1],note_d[0:SLOT_COUNT-1];
    logic [3:0] source_q[0:SLOT_COUNT-1],source_d[0:SLOT_COUNT-1];
    logic [3:0] channel_q[0:SLOT_COUNT-1],channel_d[0:SLOT_COUNT-1];
    logic [GEOM_WIDTH-1:0] top_q[0:SLOT_COUNT-1],top_d[0:SLOT_COUNT-1];
    logic [GEOM_WIDTH-1:0] end_q[0:SLOT_COUNT-1],end_d[0:SLOT_COUNT-1];
    logic [9:0] velocity_q[0:SLOT_COUNT-1],velocity_d[0:SLOT_COUNT-1];
    logic [31:0] drops_q,drops_d;
    assign pending_drop_count=drops_q;
    logic desync_pending_q,desync_pending_d;
    logic [127:0] snapshot_keys;
    integer i,j,k;
    logic note_on,note_off,clear_event;
    logic [SLOT_COUNT-1:0] match_held,eligible_free,eligible_tail;
    logic [SLOT_COUNT-1:0] first_free,last_retrigger,oldest_tail,allocate_slot;
    wire [SLOT_COUNT-1:0] legacy_oldest_tail,cached_oldest_tail;
    logic [GEOM_WIDTH-1:0] moved_end[0:SLOT_COUNT-1];
    wire [SLOT_COUNT-1:0] end_expired,top_expired;
    generate
        for(genvar g=0;g<SLOT_COUNT;g=g+1)begin:g_geometry
            // A large legal step clears every reachable position. Do not
            // truncate it into the smaller position range before comparing.
            assign end_expired[g]=STEP_EXCEEDS_RANGE || end_q[g]<=RISE_GEOM;
            assign top_expired[g]=STEP_EXCEEDS_RANGE || top_q[g]<=RISE_GEOM;
        end
    endgenerate
    // R07: constant leaf qualification followed by balanced winner trees.
    // No extra cycle/event queue/clock domain or audio feedback.
    always_comb begin
        for(integer a=0;a<SLOT_COUNT;a=a+1)begin
            moved_end[a]=(frame_start && !held_q[a]) ?
                (end_expired[a] ? GEOM_WIDTH'(0) : end_q[a]-RISE_GEOM) : end_q[a];
            eligible_free[a]=!valid_q[a] ||
                (frame_start && !held_q[a] && end_expired[a]);
            match_held[a]=valid_q[a] && held_q[a] &&
                note_q[a]==performance_data.note_number &&
                source_q[a]==performance_data.source_id && channel_q[a]==performance_data.channel;
            eligible_tail[a]=!eligible_free[a] &&
                (!held_q[a] || (match_held[a] && (note_on || note_off)));
        end
    end
    // BEGIN R07_BALANCED_SELECTION
    // Padded power-of-two leaves support SLOT_COUNT=1 and non-power-of-two N.
    localparam integer INDEX_WIDTH=(SLOT_COUNT<=1)?1:$clog2(SLOT_COUNT);
    localparam integer TREE_LEAVES=1<<$clog2(SLOT_COUNT);
    wire free_tree[1:2*TREE_LEAVES-1];
    wire retrigger_tree[1:2*TREE_LEAVES-1];
    wire tail_tree[1:2*TREE_LEAVES-1];
    wire [INDEX_WIDTH-1:0] free_index[1:2*TREE_LEAVES-1];
    wire [INDEX_WIDTH-1:0] retrigger_index[1:2*TREE_LEAVES-1];
    wire [INDEX_WIDTH-1:0] tail_index[1:2*TREE_LEAVES-1];
    wire [GEOM_WIDTH-1:0] tail_end[1:2*TREE_LEAVES-1];
    generate
        for(genvar leaf=0;leaf<TREE_LEAVES;leaf=leaf+1)begin:g_select_leaf
            if(leaf<SLOT_COUNT)begin:g_real
                assign free_tree[TREE_LEAVES+leaf]=eligible_free[leaf];
                assign retrigger_tree[TREE_LEAVES+leaf]=match_held[leaf];
                assign tail_tree[TREE_LEAVES+leaf]=eligible_tail[leaf];
                assign tail_end[TREE_LEAVES+leaf]=moved_end[leaf];
            end else begin:g_pad
                assign free_tree[TREE_LEAVES+leaf]=1'b0;
                assign retrigger_tree[TREE_LEAVES+leaf]=1'b0;
                assign tail_tree[TREE_LEAVES+leaf]=1'b0;
                assign tail_end[TREE_LEAVES+leaf]='0;
            end
            assign free_index[TREE_LEAVES+leaf]=INDEX_WIDTH'(leaf);
            assign retrigger_index[TREE_LEAVES+leaf]=INDEX_WIDTH'(leaf);
            assign tail_index[TREE_LEAVES+leaf]=INDEX_WIDTH'(leaf);
        end
        for(genvar node=1;node<TREE_LEAVES;node=node+1)begin:g_select_branch
            wire choose_left_tail=tail_tree[2*node] &&
                (!tail_tree[2*node+1] || tail_end[2*node]<=tail_end[2*node+1]);
            assign free_tree[node]=free_tree[2*node] || free_tree[2*node+1];
            assign free_index[node]=free_tree[2*node] ? free_index[2*node] : free_index[2*node+1];
            assign retrigger_tree[node]=retrigger_tree[2*node] || retrigger_tree[2*node+1];
            assign retrigger_index[node]=retrigger_tree[2*node+1] ?
                retrigger_index[2*node+1] : retrigger_index[2*node];
            assign tail_tree[node]=tail_tree[2*node] || tail_tree[2*node+1];
            // Left subtree has lower indices: <= preserves the original tie rule.
            assign tail_index[node]=choose_left_tail ? tail_index[2*node] : tail_index[2*node+1];
            assign tail_end[node]=choose_left_tail ? tail_end[2*node] : tail_end[2*node+1];
        end
        for(genvar slot=0;slot<SLOT_COUNT;slot=slot+1)begin:g_select_decode
            assign first_free[slot]=free_tree[1] && free_index[1]==INDEX_WIDTH'(slot);
            assign last_retrigger[slot]=retrigger_tree[1] && retrigger_index[1]==INDEX_WIDTH'(slot);
            assign legacy_oldest_tail[slot]=tail_tree[1] && tail_index[1]==INDEX_WIDTH'(slot);
        end
    endgenerate
    assign allocate_slot=free_tree[1] ? first_free :
        (retrigger_tree[1] ? last_retrigger : oldest_tail);
    // END R07_BALANCED_SELECTION
    // R05: four-slot lookahead caches are captured with the slot q state.
    // Invariant after each edge: every cache is the released minimum of its
    // current q group, because its D input is derived from final slot *_d.
    // This is not an extra event/handshake stage; public state timing is kept.
    localparam integer GROUP_SIZE=4;
    localparam integer GROUP_COUNT=(SLOT_COUNT+GROUP_SIZE-1)/GROUP_SIZE;
    logic [GROUP_SIZE-1:0] group_mask_q[0:GROUP_COUNT-1];
    wire [GROUP_SIZE-1:0] group_mask_d[0:GROUP_COUNT-1];
    logic [GEOM_WIDTH-1:0] group_end_q[0:GROUP_COUNT-1];
    wire [GEOM_WIDTH-1:0] group_end_d[0:GROUP_COUNT-1];
    wire [GROUP_COUNT-1:0] group_valid,group_winner;
    wire [GROUP_COUNT-1:0] group_terms[0:GROUP_COUNT-1];
    wire group_precedes[0:GROUP_COUNT-1][0:GROUP_COUNT-1];
    generate
        for(genvar group=0;group<GROUP_COUNT;group=group+1)begin:g_tail_cache
            wire [3:0] valid_next;
            wire [GEOM_WIDTH-1:0] end_next[0:3];
            for(genvar lane=0;lane<GROUP_SIZE;lane=lane+1)begin:g_lane
                localparam integer SLOT=group*GROUP_SIZE+lane;
                if(SLOT<SLOT_COUNT)begin:g_real
                    assign valid_next[lane]=valid_d[SLOT] && !held_d[SLOT];
                    assign end_next[lane]=end_d[SLOT];
                end else begin:g_pad
                    assign valid_next[lane]=1'b0;
                    assign end_next[lane]='0;
                end
            end
            // Six comparisons are parallel within one four-slot group.
            wire le01=(end_next[0]<=end_next[1]);
            wire le02=(end_next[0]<=end_next[2]);
            wire le03=(end_next[0]<=end_next[3]);
            wire le12=(end_next[1]<=end_next[2]);
            wire le13=(end_next[1]<=end_next[3]);
            wire le23=(end_next[2]<=end_next[3]);
            assign group_mask_d[group][0]=valid_next[0] &&
                (!valid_next[1] || le01) && (!valid_next[2] || le02) &&
                (!valid_next[3] || le03);
            assign group_mask_d[group][1]=valid_next[1] &&
                (!valid_next[0] || !le01) && (!valid_next[2] || le12) &&
                (!valid_next[3] || le13);
            assign group_mask_d[group][2]=valid_next[2] &&
                (!valid_next[0] || !le02) && (!valid_next[1] || !le12) &&
                (!valid_next[3] || le23);
            assign group_mask_d[group][3]=valid_next[3] &&
                (!valid_next[0] || !le03) && (!valid_next[1] || !le13) &&
                (!valid_next[2] || !le23);
            assign group_end_d[group]=
                (end_next[0] & {GEOM_WIDTH{group_mask_d[group][0]}}) |
                (end_next[1] & {GEOM_WIDTH{group_mask_d[group][1]}}) |
                (end_next[2] & {GEOM_WIDTH{group_mask_d[group][2]}}) |
                (end_next[3] & {GEOM_WIDTH{group_mask_d[group][3]}});
            always_ff @(posedge clk or negedge rst_n)begin
                if(!rst_n)begin
                    group_mask_q[group]<='0;group_end_q[group]<='0;
                end else if(flush)begin
                    group_mask_q[group]<='0;group_end_q[group]<='0;
                end else begin
                    group_mask_q[group]<=group_mask_d[group];
                    group_end_q[group]<=group_end_d[group];
                end
            end
            assign group_valid[group]=|group_mask_q[group];
            // With32slots only8 group values remain. All28 unordered pairs
            // compare in parallel, rather than a cascade of value/index muxes.
            for(genvar other=0;other<GROUP_COUNT;other=other+1)begin:g_global_pair
                if(group<other)begin:g_left
                    assign group_precedes[group][other]=(group_end_q[group]<=group_end_q[other]);
                end else if(group>other)begin:g_right
                    assign group_precedes[group][other]=!group_precedes[other][group];
                end else begin:g_self
                    assign group_precedes[group][other]=1'b1;
                end
                assign group_terms[group][other]=!group_valid[other] || group_precedes[group][other];
            end
            assign group_winner[group]=group_valid[group] && (&group_terms[group]);
        end
        for(genvar slot=0;slot<SLOT_COUNT;slot=slot+1)begin:g_cached_tail_decode
            assign cached_oldest_tail[slot]=group_winner[slot/GROUP_SIZE] &&
                group_mask_q[slot/GROUP_SIZE][slot%GROUP_SIZE];
        end
    endgenerate
    // Released q-end ordering is sufficient whenever tail allocation wins:
    // free (including this-frame expiry) and retrigger still have priority.
    // Keep the original unknown-frame behavior through the complete-case
    // default. Native must independently confirm this binary-unreachable
    // legacy cone is pruned; no SYNTHESIS-only alternate implementation.
    always_comb begin
        case(frame_start)
            1'b0,1'b1: oldest_tail=cached_oldest_tail;
            default: oldest_tail=legacy_oldest_tail;
        endcase
    end
    always_comb begin
        valid_d=valid_q;held_d=held_q;drops_d=drops_q;
        desync_pending_d=desync_pending_q || video_desync;
        
        note_on=performance_fire && performance_data.event_type==EVENT_NOTE_ON && performance_data.velocity!=0;
        note_off=performance_fire && (performance_data.event_type==EVENT_NOTE_OFF ||
            (performance_data.event_type==EVENT_NOTE_ON && performance_data.velocity==0));
        clear_event=performance_fire && performance_data.event_type==EVENT_ALL_NOTES_OFF;
        snapshot_keys=0;
        for(i=0;i<SLOT_COUNT;i=i+1)begin
            note_d[i]=note_q[i];source_d[i]=source_q[i];channel_d[i]=channel_q[i];
            top_d[i]=top_q[i];end_d[i]=end_q[i];velocity_d[i]=velocity_q[i];
            if(valid_q[i] && held_q[i])snapshot_keys[note_q[i]]=1;
            if(frame_start && valid_q[i])begin
                top_d[i]=top_expired[i] ? GEOM_WIDTH'(0) : top_q[i]-RISE_GEOM;
                if(!held_q[i])begin
                    end_d[i]=moved_end[i];
                    if(end_expired[i])valid_d[i]=0;
                end
            end
        end
        if(video_desync || desync_pending_q || desync_latched || clear_event)begin
            valid_d=0;held_d=0;
            for(i=0;i<SLOT_COUNT;i=i+1)begin
                top_d[i]=0;end_d[i]=0;note_d[i]=0;velocity_d[i]=0;
                source_d[i]=0;channel_d[i]=0;
            end
        end else begin
            // Source/channel/pitch identity prevents one source's NoteOff
            // from stopping another source's held bar of the same pitch.
            for(i=0;i<SLOT_COUNT;i=i+1)begin
                // Before allocation only non-held entries can retire, so the
                // original q identity test is also the d identity test here.
                if(match_held[i] && (note_off || note_on))held_d[i]=0;
            end
            if(note_on)begin
                // Empty slot, matching retrigger, oldest released history.
                // An all-held overflow remains a genuine observable loss.
                for(k=0;k<SLOT_COUNT;k=k+1)begin
                    if(allocate_slot[k])begin
                        valid_d[k]=1;held_d[k]=1;
                        note_d[k]=performance_data.note_number;
                        source_d[k]=performance_data.source_id;
                        channel_d[k]=performance_data.channel;
                        top_d[k]=GEOM_WIDTH'(JUDGE_Y);
                        end_d[k]=GEOM_WIDTH'(MAX_GEOM);
                        velocity_d[k]=performance_data.velocity;
                    end
                end
                if(!( |allocate_slot) && drops_d!=32'hffffffff)drops_d=drops_d+1'b1;
            end
        end
    end
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_q<=0;held_q<=0;drops_q<=0;desync_pending_q<=0;desync_latched<=0;
            key_down<=0;live_valid<=0;live_note_number<=0;live_y<=0;
            live_end_y<=0;live_held<=0;live_velocity<=0;visual_slot_drop_count<=0;
            for(j=0;j<SLOT_COUNT;j=j+1)begin
                note_q[j]<=0;source_q[j]<=0;channel_q[j]<=0;
                top_q[j]<=0;end_q[j]<=0;velocity_q[j]<=0;
            end
        end else if(flush)begin
            valid_q<=0;held_q<=0;drops_q<=0;desync_pending_q<=0;desync_latched<=0;
            key_down<=0;live_valid<=0;live_note_number<=0;live_y<=0;
            live_end_y<=0;live_held<=0;live_velocity<=0;visual_slot_drop_count<=0;
            for(j=0;j<SLOT_COUNT;j=j+1)begin
                note_q[j]<=0;source_q[j]<=0;channel_q[j]<=0;
                top_q[j]<=0;end_q[j]<=0;velocity_q[j]<=0;
            end
        end else begin
            valid_q<=valid_d;held_q<=held_d;drops_q<=drops_d;desync_pending_q<=desync_pending_d;
            for(j=0;j<SLOT_COUNT;j=j+1)begin
                note_q[j]<=note_d[j];source_q[j]<=source_d[j];channel_q[j]<=channel_d[j];
                top_q[j]<=top_d[j];end_q[j]<=end_d[j];velocity_q[j]<=velocity_d[j];
            end
            if(frame_start)begin
                if(video_desync || desync_pending_q || desync_latched)begin
                    key_down<=0;live_valid<=0;live_note_number<=0;live_y<=0;
                    live_end_y<=0;live_held<=0;live_velocity<=0;
                    desync_pending_q<=0;desync_latched<=1;
                end else begin
                    key_down<=snapshot_keys;live_valid<=valid_q;live_held<=held_q;
                    for(j=0;j<SLOT_COUNT;j=j+1)begin
                        live_note_number[j*7+:7]<=note_q[j];
                        live_y[j*Y_WIDTH+:Y_WIDTH]<=top_q[j];
                        live_end_y[j*Y_WIDTH+:Y_WIDTH]<=end_q[j];
                        live_velocity[j*10+:10]<=velocity_q[j];
                    end
                end
                visual_slot_drop_count<=drops_q;
            end
        end
    end
`ifndef SYNTHESIS
    initial begin
        if(SLOT_COUNT<1 || SLOT_COUNT>32 || Y_WIDTH<1 || Y_WIDTH>30 ||
            JUDGE_Y<0 || JUDGE_Y+10 >= (64'd1<<Y_WIDTH) ||
            RISE_STEP<1 || RISE_STEP >= (64'd1<<Y_WIDTH))
            $fatal(1,"invalid duration-bar geometry");
    end
`endif
endmodule
