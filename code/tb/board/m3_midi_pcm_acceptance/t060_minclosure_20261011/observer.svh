// Read-only pre-NBA view; single task called by the TB's sole capture process.
wire [127:0] observed_dds_phase,observed_lfo_phase,observed_env_level;
wire [15:0] observed_env_state;
for(genvar lane=0;lane<4;lane++)begin:g_observation
    assign observed_dds_phase[32*lane+:32]=u_bank.g_lane[lane].g_piano.u_dds.phase_acc;
    assign observed_lfo_phase[32*lane+:32]=u_bank.u_pitch_mod.g_lane[lane].u_control.lfo_phase;
    assign observed_env_level[32*lane+:32]=u_bank.g_lane[lane].u_envelope.level_q16;
    assign observed_env_state[4*lane+:4]=u_bank.g_lane[lane].u_envelope.state;
end
task automatic observe_edge;
    $fdisplay(fd,{"{\"tag\":\"EDGE\",\"cycle\":%0d,\"epoch\":%0d,",
        "\"event_valid\":%0d,\"event\":%0d,\"event_ready\":%0d,",
        "\"frame\":%0d,\"consumer\":%0d,\"sample_req\":%0d,\"request_id\":%0d,",
        "\"phase\":%0d,\"router_state\":%0d,\"tick\":%0d,\"on\":%0d,\"off\":%0d,",
        "\"occupied\":%0d,\"releasing\":%0d,\"keys\":%0d,\"deferred\":%0d,\"pedal\":%0d,",
        "\"sources\":%0d,\"channels\":%0d,\"notes\":%0d,\"generations\":%0d,\"velocity\":%0d,",
        "\"release_done\":%0d,\"ctrl_accept\":%0d,\"math_accept\":%0d,",
        "\"bank_valid\":%0d,\"bank_ready\":%0d,\"bank_id\":%0d,\"bank_waves\":%0d,",
        "\"bank_envelopes\":%0d,\"bank_occupied\":%0d,",
        "\"pcm_valid\":%0d,\"pcm_ready\":%0d,\"pcm_id\":%0d,\"pcm_left\":%0d,\"pcm_right\":%0d,",
        "\"commit\":%0d,\"pending_valid\":%0d,\"play_left\":%0d,\"play_right\":%0d,",
        "\"dds_phase\":%0d,\"lfo_phase\":%0d,\"env_state\":%0d,\"env_level\":%0d}"},
        cycle,epoch,event_valid,event_data,event_ready,frame_tick,consumer_enable,sample_req,sample_req_id,
        u_bank.phase,u_bank.u_events.state,u_bank.lane_tick,u_bank.slot_note_on,u_bank.slot_note_off,
        u_bank.slot_occupied,u_bank.slot_releasing,u_bank.u_events.controller_keys,
        u_bank.u_events.controller_deferred,u_bank.u_events.u_sustain.pedal_down[16],
        u_bank.slot_sources,u_bank.slot_channels,u_bank.slot_notes,u_bank.slot_generations,u_bank.slot_velocity,
        u_bank.release_done,u_bank.control_request_valid && u_bank.control_request_ready,
        u_bank.u_pitch_mod.accepted,bank_valid,bank_ready,bank_id,bank_waves,bank_envelopes,bank_occupied,
        u_commit.pcm_valid,u_commit.pcm_ready,u_commit.pcm_req_id,$signed(u_commit.pcm_left),$signed(u_commit.pcm_right),
        actual_commit,pending_valid,$signed(play_left),$signed(play_right),observed_dds_phase,
        observed_lfo_phase,observed_env_state,observed_env_level);
endtask
