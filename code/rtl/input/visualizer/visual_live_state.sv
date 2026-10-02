// Video-domain physical-key-duration bars. Audio has no dependency on this
// bounded display state. All published geometry is a frame_start snapshot.
`timescale 1ns/1ps
module visual_live_state #(
    parameter integer SLOT_COUNT=8, Y_WIDTH=10, JUDGE_Y=400, RISE_STEP=4
) (
    input logic clk,rst_n,frame_start,performance_fire,
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
    output logic desync_latched
);
    import audio_defs_pkg::*;
    logic [SLOT_COUNT-1:0] valid_q,valid_d,held_q,held_d;
    logic [6:0] note_q[0:SLOT_COUNT-1],note_d[0:SLOT_COUNT-1];
    logic [3:0] source_q[0:SLOT_COUNT-1],source_d[0:SLOT_COUNT-1];
    logic [3:0] channel_q[0:SLOT_COUNT-1],channel_d[0:SLOT_COUNT-1];
    logic [Y_WIDTH-1:0] top_q[0:SLOT_COUNT-1],top_d[0:SLOT_COUNT-1];
    logic [Y_WIDTH-1:0] end_q[0:SLOT_COUNT-1],end_d[0:SLOT_COUNT-1];
    logic [9:0] velocity_q[0:SLOT_COUNT-1],velocity_d[0:SLOT_COUNT-1];
    logic [31:0] drops_q,drops_d;
    logic desync_pending_q,desync_pending_d;
    logic [127:0] snapshot_keys;
    integer i,j,free_slot,retrigger_slot;
    logic note_on,note_off,clear_event;
    always_comb begin
        valid_d=valid_q;held_d=held_q;drops_d=drops_q;
        desync_pending_d=desync_pending_q || video_desync;
        free_slot=-1;retrigger_slot=-1;
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
                top_d[i]=(top_q[i]<=RISE_STEP) ? Y_WIDTH'(0) : top_q[i]-Y_WIDTH'(RISE_STEP);
                if(!held_q[i])begin
                    end_d[i]=(end_q[i]<=RISE_STEP) ? Y_WIDTH'(0) : end_q[i]-Y_WIDTH'(RISE_STEP);
                    if(end_q[i]<=RISE_STEP)valid_d[i]=0;
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
                if(valid_d[i] && held_d[i] && note_d[i]==performance_data.note_number &&
                   source_d[i]==performance_data.source_id && channel_d[i]==performance_data.channel)begin
                    if(note_off)held_d[i]=0;
                    if(note_on)begin held_d[i]=0;retrigger_slot=i;end
                end
            end
            for(i=0;i<SLOT_COUNT;i=i+1)
                if(free_slot<0 && !valid_d[i])free_slot=i;
            if(note_on)begin
                if(free_slot<0 && retrigger_slot>=0)begin
                    free_slot=retrigger_slot;
                    if(drops_d!=32'hffffffff)drops_d=drops_d+1'b1;
                end
                if(free_slot>=0)begin
                    valid_d[free_slot]=1;held_d[free_slot]=1;
                    note_d[free_slot]=performance_data.note_number;
                    source_d[free_slot]=performance_data.source_id;
                    channel_d[free_slot]=performance_data.channel;
                    top_d[free_slot]=Y_WIDTH'(JUDGE_Y);
                    end_d[free_slot]=Y_WIDTH'(JUDGE_Y+10);
                    velocity_d[free_slot]=performance_data.velocity;
                end else if(drops_d!=32'hffffffff)drops_d=drops_d+1'b1;
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
        if(SLOT_COUNT<1 || SLOT_COUNT>8 || Y_WIDTH<1 || Y_WIDTH>30 ||
            JUDGE_Y<0 || JUDGE_Y+10 >= (64'd1<<Y_WIDTH) ||
            RISE_STEP<1 || RISE_STEP >= (64'd1<<Y_WIDTH))
            $fatal(1,"invalid duration-bar geometry");
    end
`endif
endmodule
