// -----------------------------------------------------------------------------
// midi_event_parser.sv
// 把 MIDI 字节流转换成项目统一的 64 位演奏事件。
//
// 支持：Note On/Off、CC64、Program Change、Pitch Bend/CC1、Velocity=0、Running Status、
// F8..FF 实时字节穿插、System Common/SysEx 跳过、本地事件 FIFO，以及
// Pitch/CC1 的1kHz合并与离散事件有界公平调度。
//
// 本模块只接收已经解码的 UART 字节，不绑定实体引脚，也不产生派生时钟。
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module midi_event_parser #(
    parameter integer     LOCAL_FIFO_DEPTH = 8,
    parameter logic [3:0] SOURCE_ID         = 4'd0,
    parameter integer     CLK_HZ           = 50_000_000,
    parameter integer     MAX_DISCRETE_BURST = 8
) (
    input  logic                               clk,
    input  logic                               rst_n,
    input  logic [7:0]                         midi_byte,
    input  logic                               midi_byte_valid,
    input  logic                               midi_byte_error,
    input  logic                               event_ready,
    output logic                               event_valid,
    output audio_defs_pkg::performance_event_t event_data,
    output logic [15:0]                        event_fifo_level,
    output logic [15:0]                        event_fifo_high_watermark,
    output logic [31:0]                        event_fifo_overflow_count,
    output logic [31:0]                        parser_error_count
);

    import audio_defs_pkg::*;

    localparam integer FIFO_COUNT_WIDTH =
        (LOCAL_FIFO_DEPTH <= 1) ? 1 : $clog2(LOCAL_FIFO_DEPTH + 1);

    performance_event_t fifo_mem      [0:LOCAL_FIFO_DEPTH-1];
    performance_event_t fifo_mem_next [0:LOCAL_FIFO_DEPTH-1];

    logic [FIFO_COUNT_WIDTH-1:0] fifo_count;
    logic [FIFO_COUNT_WIDTH-1:0] fifo_count_next;

    // Running Status 只保存 80..EF 的通道状态字节。
    logic [7:0] running_status;
    logic [6:0] first_data_byte;
    logic       channel_data_pending;

    // 第一版不把 System Common 转成事件，但必须吃完规定的数据字节，
    // 否则后面的 Note 消息会发生错位。
    logic [1:0] system_data_remaining;
    logic       sysex_active;

    logic               parsed_event_valid;
    performance_event_t parsed_event_data;
    logic               parser_error_pulse;
    logic               fifo_overflow_pulse;

    // SOURCE_ID is fixed per parser. These are transport pending slots, not
    // the system's accepted source/channel performance-control state table.
    localparam integer CONTROL_INTERVAL = (CLK_HZ + 999) / 1000;
    localparam integer RATE_WIDTH = (CONTROL_INTERVAL <= 1) ? 1 :
                                   $clog2(CONTROL_INTERVAL);
    localparam integer BURST_COUNT_WIDTH = (MAX_DISCRETE_BURST <= 1) ? 1 :
                                           $clog2(MAX_DISCRETE_BURST + 1);
    logic [RATE_WIDTH-1:0] control_cooldown;
    logic [BURST_COUNT_WIDTH-1:0] discrete_burst_count;
    logic [31:0] control_pending;
    logic [11:0] pending_value [0:31];
    logic [15:0] mod_sent_valid;
    logic [11:0] mod_sent_value [0:15];
    logic control_locked;
    logic [4:0] locked_index, round_robin_index;
    performance_event_t locked_event;
    wire parsed_control = parsed_event_valid &&
        ((parsed_event_data.event_type == EVENT_PITCH_BEND &&
          parsed_event_data.control_id == CTRL_PITCH_BEND) ||
         (parsed_event_data.event_type == EVENT_CONTROL_CHANGE &&
          parsed_event_data.control_id == CTRL_MODULATION));
    wire [4:0] parsed_control_index = {parsed_event_data.channel,
                                    parsed_event_data.control_id == CTRL_MODULATION};
    wire parsed_discrete = parsed_event_valid && !parsed_control;
    logic selected_valid;
    logic [4:0] selected_index;
    logic [11:0] selected_value;
    logic parsed_control_keep_pending;
    logic grant_control;
    wire discrete_handshake = !control_locked &&
        (fifo_count != {FIFO_COUNT_WIDTH{1'b0}}) && event_ready;
    wire burst_limit_reached = (MAX_DISCRETE_BURST <= 1) ||
        (discrete_burst_count >= (MAX_DISCRETE_BURST - 1));
    integer control_reset;

    // ISOLATED M2 candidate: register the first three RR candidates.
    // No current byte or ready enters the preparation tree. Its snapshot is
    // one cycle old; at most one previous parsed update needs repair. A grant
    // changes RR/pending while locked, and the lock supplies the refresh cycle.
    // Additional register boundary: rotation -> priority tree. The register
    // anticipates the SAME edge's pending/RR update, so it equals the current
    // registered-state rotation after every edge, not a stale extra cycle.
    wire [31:0] lookahead_pending_next;
    wire [4:0] lookahead_rr_next = grant_control ? selected_index+5'd1 : round_robin_index;
    logic [31:0] lookahead_rr_pending;
    for(genvar slot=0;slot<32;slot++) begin:g_lookahead_pending
        wire clear_slot = grant_control && selected_index==5'(slot);
        assign lookahead_pending_next[slot] = parsed_control && parsed_control_index==5'(slot) ?
            (parsed_control_keep_pending && !clear_slot) :
            (control_pending[slot] && !clear_slot);
    end
    always_ff @(posedge clk) begin
        if(!rst_n) lookahead_rr_pending<='0;
        else lookahead_rr_pending <=
            32'({lookahead_pending_next,lookahead_pending_next} >> lookahead_rr_next);
    end
    wire [31:0] prepare_rr_pending = lookahead_rr_pending;
    wire [2:0] prep_valid [1:63];
    wire [4:0] prep_rank0 [1:63], prep_rank1 [1:63], prep_rank2 [1:63];
    generate
        for(genvar leaf=0;leaf<32;leaf=leaf+1) begin:g_prepare_leaf
            assign prep_valid[32+leaf] = {2'b00,prepare_rr_pending[leaf]};
            assign prep_rank0[32+leaf] = 5'(leaf);
            assign prep_rank1[32+leaf] = '0;
            assign prep_rank2[32+leaf] = '0;
        end
        for(genvar node=1;node<32;node=node+1) begin:g_prepare_node
            wire a0=prep_valid[2*node][0], a1=prep_valid[2*node][1], a2=prep_valid[2*node][2];
            wire b0=prep_valid[2*node+1][0], b1=prep_valid[2*node+1][1], b2=prep_valid[2*node+1][2];
            assign prep_valid[node][0]=a0||b0;
            assign prep_valid[node][1]=a1||(a0&&b0)||b1;
            assign prep_valid[node][2]=a2||(a1&&b0)||(a0&&b1)||b2;
            assign prep_rank0[node]=a0?prep_rank0[2*node]:prep_rank0[2*node+1];
            assign prep_rank1[node]=a1?prep_rank1[2*node]:(a0?prep_rank0[2*node+1]:prep_rank1[2*node+1]);
            assign prep_rank2[node]=a2?prep_rank2[2*node]:(a1?prep_rank0[2*node+1]:(a0?prep_rank1[2*node+1]:prep_rank2[2*node+1]));
        end
    endgenerate
    logic [2:0] prepared_valid;
    logic [4:0] prepared_rank0,prepared_rank1,prepared_rank2;
    logic [4:0] prepared_index0,prepared_index1,prepared_index2;
    logic [11:0] prepared_value0,prepared_value1,prepared_value2;
    logic [11:0] previous_value;
    logic previous_update, previous_keep;
    logic [4:0] previous_index;
    wire [4:0] previous_rank=previous_index-round_robin_index;
    logic first_prepared_valid,second_prepared_valid;
    logic [4:0] first_prepared_rank,second_prepared_rank;
    logic [4:0] old_first_index,old_second_index;
    always_comb begin
        first_prepared_valid=prepared_valid[0];
        second_prepared_valid=prepared_valid[1];
        first_prepared_rank=prepared_rank0;
        second_prepared_rank=prepared_rank1;
        old_first_index=prepared_index0;
        old_second_index=prepared_index1;
        if(previous_update) begin
            if(previous_keep) begin
                if(!prepared_valid[0] || previous_rank<=prepared_rank0) begin
                    first_prepared_valid=1'b1;
                    first_prepared_rank=previous_rank;
                    old_first_index=previous_index;
                    if(previous_index!=prepared_index0 || !prepared_valid[0]) begin
                        second_prepared_valid=prepared_valid[0];
                        second_prepared_rank=prepared_rank0;
                        old_second_index=prepared_index0;
                    end
                end else if(!prepared_valid[1] || previous_rank<=prepared_rank1) begin
                    second_prepared_valid=1'b1;
                    second_prepared_rank=previous_rank;
                    old_second_index=previous_index;
                end
            end else if(prepared_valid[0] && previous_index==prepared_index0) begin
                first_prepared_valid=prepared_valid[1];
                first_prepared_rank=prepared_rank1;
                old_first_index=prepared_index1;
                second_prepared_valid=prepared_valid[2];
                second_prepared_rank=prepared_rank2;
                old_second_index=prepared_index2;
            end else if(prepared_valid[1] && previous_index==prepared_index1) begin
                second_prepared_valid=prepared_valid[2];
                second_prepared_rank=prepared_rank2;
                old_second_index=prepared_index2;
            end
        end
    end
    wire [11:0] old_first_value = previous_update && old_first_index==previous_index ?
        previous_value : old_first_index==prepared_index0 ? prepared_value0 :
        old_first_index==prepared_index1 ? prepared_value1 : prepared_value2;
    wire [11:0] old_second_value = previous_update && old_second_index==previous_index ?
        previous_value : old_second_index==prepared_index0 ? prepared_value0 :
        old_second_index==prepared_index1 ? prepared_value1 : prepared_value2;
    wire [4:0] parsed_control_rank = parsed_control_index - round_robin_index;
    // Preparation is speculative: this changes no public event latency/state.
    always_ff @(posedge clk) begin
        if(!rst_n) begin
            prepared_valid<='0;
            prepared_rank0<='0;prepared_rank1<='0;prepared_rank2<='0;
            prepared_index0<='0;prepared_index1<='0;prepared_index2<='0;
            prepared_value0<='0;prepared_value1<='0;prepared_value2<='0;
            previous_value<='0;
            previous_update<=1'b0;previous_keep<=1'b0;previous_index<='0;
        end else begin
            prepared_valid<=prep_valid[1];
            prepared_rank0<=prep_rank0[1];prepared_rank1<=prep_rank1[1];prepared_rank2<=prep_rank2[1];
            prepared_index0<=round_robin_index+prep_rank0[1];
            prepared_index1<=round_robin_index+prep_rank1[1];
            prepared_index2<=round_robin_index+prep_rank2[1];
            prepared_value0<=pending_value[5'(round_robin_index+prep_rank0[1])];
            prepared_value1<=pending_value[5'(round_robin_index+prep_rank1[1])];
            prepared_value2<=pending_value[5'(round_robin_index+prep_rank2[1])];
            previous_value<=parsed_event_data.control_value;
            previous_update<=parsed_control;
            previous_index<=parsed_control_index;
            previous_keep<=parsed_control_keep_pending &&
                !(grant_control && parsed_control_index==selected_index);
        end
    end

    integer comb_fifo_index;
    integer seq_fifo_index;

    // Cn（音色切换）和 Dn（通道压力）只有一个数据字节，其余通道消息为两个。
    function automatic logic channel_message_has_one_data_byte(
        input logic [3:0] status_high_nibble
    );
        begin
            channel_message_has_one_data_byte =
                (status_high_nibble == 4'hC) ||
                (status_high_nibble == 4'hD);
        end
    endfunction

    function automatic logic is_realtime_status(
        input logic [7:0] status_byte
    );
        begin
            is_realtime_status = (status_byte >= 8'hF8);
        end
    endfunction

    function automatic logic [1:0] system_common_data_bytes(
        input logic [7:0] status_byte
    );
        begin
            case (status_byte)
                8'hF1: system_common_data_bytes = 2'd1;
                8'hF2: system_common_data_bytes = 2'd2;
                8'hF3: system_common_data_bytes = 2'd1;
                default: system_common_data_bytes = 2'd0;
            endcase
        end
    endfunction

    // 收齐通道消息的数据字节后生成事件，使用冻结公共映射/编号。
    // Program Change保留原始程序号；CC原始编号不能直接用作公共control_id。
    always_comb begin
        parsed_event_valid = 1'b0;
        parsed_event_data  = '0;

        if (midi_byte_valid && !midi_byte_error && !sysex_active &&
            !midi_byte[7] && (system_data_remaining == 2'd0) &&
            running_status[7]) begin
            if (running_status[7:4] == 4'hC) begin
                parsed_event_valid = 1'b1;
                parsed_event_data.event_type = EVENT_CONTROL_CHANGE;
                parsed_event_data.source_id = SOURCE_ID;
                parsed_event_data.channel = running_status[3:0];
                parsed_event_data.control_id = CTRL_VOICE_SELECT;
                parsed_event_data.control_value = {5'd0, midi_byte[6:0]};
            end else if (!channel_message_has_one_data_byte(running_status[7:4]) &&
                         channel_data_pending &&
                         ((running_status[7:4] == 4'h8) ||
                          (running_status[7:4] == 4'h9))) begin
                parsed_event_valid = 1'b1;
                parsed_event_data  = audio_defs_pkg::make_note_event(
                    running_status[7:4] == 4'h9,
                    SOURCE_ID,
                    running_status[3:0],
                    first_data_byte,
                    audio_defs_pkg::midi_velocity_to_10bit(midi_byte[6:0])
                );
            end else if (!channel_message_has_one_data_byte(running_status[7:4]) &&
                         channel_data_pending &&
                         (running_status[7:4] == 4'hB) &&
                         (first_data_byte == 7'h40)) begin
                parsed_event_valid = 1'b1;
                parsed_event_data = audio_defs_pkg::make_sustain_event(
                    SOURCE_ID, running_status[3:0], midi_byte[6:0]
                );
            end else if (!channel_message_has_one_data_byte(running_status[7:4]) &&
                         channel_data_pending &&
                         running_status[7:4] == 4'hE) begin
                parsed_event_valid = 1'b1;
                parsed_event_data.event_type = EVENT_PITCH_BEND;
                parsed_event_data.source_id = SOURCE_ID;
                parsed_event_data.channel = running_status[3:0];
                parsed_event_data.control_id = CTRL_PITCH_BEND;
                parsed_event_data.control_value = midi_bend_to_12bit(
                    {midi_byte[6:0], first_data_byte});
            end else if (!channel_message_has_one_data_byte(running_status[7:4]) &&
                         channel_data_pending &&
                         (running_status[7:4] == 4'hB) &&
                         (first_data_byte == 7'h01)) begin
                parsed_event_valid = 1'b1;
                parsed_event_data.event_type = EVENT_CONTROL_CHANGE;
                parsed_event_data.source_id = SOURCE_ID;
                parsed_event_data.channel = running_status[3:0];
                parsed_event_data.control_id = CTRL_MODULATION;
                parsed_event_data.control_value = midi_cc_to_12bit(midi_byte[6:0]);
            end
        end
    end

    // 无状态的数据、被新状态打断的残缺消息、SysEx 内异常状态都会记一次解析错误。
    always_comb begin
        parser_error_pulse = 1'b0;

        if (midi_byte_valid && !midi_byte_error && !is_realtime_status(midi_byte)) begin
            if (sysex_active) begin
                if (midi_byte[7] && (midi_byte != 8'hF7)) begin
                    parser_error_pulse = 1'b1;
                end
            end else if (midi_byte[7]) begin
                if (channel_data_pending || (system_data_remaining != 2'd0)) begin
                    parser_error_pulse = 1'b1;
                end
            end else if ((system_data_remaining == 2'd0) && !running_status[7]) begin
                parser_error_pulse = 1'b1;
            end
        end
    end

    // 解析状态。坏 UART 帧会清除未完成上下文，避免坏字节被当成音符或力度。
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            running_status       <= 8'd0;
            first_data_byte      <= 7'd0;
            channel_data_pending <= 1'b0;
            system_data_remaining <= 2'd0;
            sysex_active         <= 1'b0;
            parser_error_count   <= 32'd0;
        end else begin
            if (parser_error_pulse && (parser_error_count != 32'hFFFF_FFFF)) begin
                parser_error_count <= parser_error_count + 32'd1;
            end

            if (midi_byte_valid) begin
                if (midi_byte_error) begin
                    running_status        <= 8'd0;
                    first_data_byte       <= 7'd0;
                    channel_data_pending  <= 1'b0;
                    system_data_remaining <= 2'd0;
                    sysex_active          <= 1'b0;
                end else if (is_realtime_status(midi_byte)) begin
                    // 实时字节可以夹在任意位置，不清除 Running Status 和半条消息。
                end else if (sysex_active) begin
                    if (midi_byte == 8'hF7) begin
                        sysex_active <= 1'b0;
                    end else if (midi_byte[7]) begin
                        // SysEx 中出现异常状态时退出 SysEx，并用新状态重新同步。
                        sysex_active          <= (midi_byte == 8'hF0);
                        running_status        <=
                            (midi_byte[7:4] <= 4'hE) ? midi_byte : 8'd0;
                        channel_data_pending  <= 1'b0;
                        system_data_remaining <=
                            (midi_byte[7:4] == 4'hF) ?
                            system_common_data_bytes(midi_byte) : 2'd0;
                    end
                end else if (midi_byte[7]) begin
                    channel_data_pending <= 1'b0;
                    first_data_byte      <= 7'd0;

                    if (midi_byte[7:4] <= 4'hE) begin
                        running_status        <= midi_byte;
                        system_data_remaining <= 2'd0;
                    end else begin
                        running_status        <= 8'd0;
                        system_data_remaining <= system_common_data_bytes(midi_byte);
                        if (midi_byte == 8'hF0) begin
                            sysex_active <= 1'b1;
                        end
                    end
                end else if (system_data_remaining != 2'd0) begin
                    system_data_remaining <= system_data_remaining - 2'd1;
                end else if (running_status[7]) begin
                    if (channel_message_has_one_data_byte(running_status[7:4])) begin
                        channel_data_pending <= 1'b0;
                    end else if (!channel_data_pending) begin
                        first_data_byte      <= midi_byte[6:0];
                        channel_data_pending <= 1'b1;
                    end else begin
                        channel_data_pending <= 1'b0;
                    end
                end
            end
        end
    end

    // FIFO 输出只依赖寄存状态，因此反压时 event_valid 和 event_data 保持稳定。
    always_comb begin
        event_valid      = control_locked || (fifo_count != {FIFO_COUNT_WIDTH{1'b0}});
        event_data       = '0;
        event_fifo_level = fifo_count;
        if (control_locked) begin
            event_data = locked_event;
        end else if (event_valid) begin
            event_data = fifo_mem[0];
        end
    end

    // 先移除已握手事件，再加入本拍新事件；同拍出队和入队不会误报溢出。
    always_comb begin
        fifo_count_next = fifo_count;
        fifo_overflow_pulse = 1'b0;
        for (comb_fifo_index = 0; comb_fifo_index < LOCAL_FIFO_DEPTH;
             comb_fifo_index = comb_fifo_index + 1) begin
            fifo_mem_next[comb_fifo_index] = fifo_mem[comb_fifo_index];
        end

        if (!control_locked && event_valid && event_ready) begin
            for (comb_fifo_index = 0; comb_fifo_index < LOCAL_FIFO_DEPTH - 1;
                 comb_fifo_index = comb_fifo_index + 1) begin
                fifo_mem_next[comb_fifo_index] = fifo_mem[comb_fifo_index + 1];
            end
            fifo_mem_next[LOCAL_FIFO_DEPTH - 1] = '0;
            fifo_count_next = fifo_count - 1'b1;
        end

        if (parsed_discrete) begin
            if (fifo_count_next < LOCAL_FIFO_DEPTH) begin
                fifo_mem_next[fifo_count_next] = parsed_event_data;
                fifo_count_next = fifo_count_next + 1'b1;
            end else begin
                fifo_overflow_pulse = 1'b1;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            fifo_count                    <= {FIFO_COUNT_WIDTH{1'b0}};
            event_fifo_high_watermark     <= 16'd0;
            event_fifo_overflow_count     <= 32'd0;
            for (seq_fifo_index = 0; seq_fifo_index < LOCAL_FIFO_DEPTH;
                 seq_fifo_index = seq_fifo_index + 1) begin
                fifo_mem[seq_fifo_index] <= '0;
            end
        end else begin
            fifo_count <= fifo_count_next;
            for (seq_fifo_index = 0; seq_fifo_index < LOCAL_FIFO_DEPTH;
                 seq_fifo_index = seq_fifo_index + 1) begin
                fifo_mem[seq_fifo_index] <= fifo_mem_next[seq_fifo_index];
            end

            if (fifo_count_next > event_fifo_high_watermark) begin
                event_fifo_high_watermark <= fifo_count_next;
            end

            if (fifo_overflow_pulse &&
                (event_fifo_overflow_count != 32'hFFFF_FFFF)) begin
                event_fifo_overflow_count <= event_fifo_overflow_count + 32'd1;
            end
        end
    end

    // Apply the current byte before arbitration. This prevents an update to the
    // selected slot from being deferred forever by a continuous byte stream.
    // A CC1 update that returns to the accepted/in-flight value cancels the
    // unsent excursion before it can consume a grant.
    always_comb begin
        parsed_control_keep_pending = 1'b0;
        if (parsed_control) begin
            parsed_control_keep_pending = !(
                parsed_control_index[0] &&
                ((control_locked && locked_index == parsed_control_index) ?
                 (locked_event.control_value == parsed_event_data.control_value) :
                 (mod_sent_valid[parsed_control_index[4:1]] &&
                  mod_sent_value[parsed_control_index[4:1]] ==
                      parsed_event_data.control_value)));
        end

        selected_valid = 1'b0;
        selected_index = '0;
        selected_value = '0;
        if (first_prepared_valid) begin
            selected_valid = 1'b1;
            selected_index = old_first_index;
            selected_value = old_first_value;
        end
        // One byte can change only one slot. Insertion/newest-value capture
        // competes with the old first; cancellation of that first falls back
        // to the old second. Other updates cannot change the winner.
        if (parsed_control) begin
            if (parsed_control_keep_pending &&
                (!first_prepared_valid ||
                 parsed_control_rank < first_prepared_rank)) begin
                selected_valid = 1'b1;
                selected_index = parsed_control_index;
                selected_value = parsed_event_data.control_value;
            end else if (!parsed_control_keep_pending && first_prepared_valid &&
                         parsed_control_index == old_first_index) begin
                selected_valid = second_prepared_valid;
                selected_index = second_prepared_valid ? old_second_index : 5'd0;
                selected_value = second_prepared_valid ? old_second_value : 12'd0;
            end
        end

        // A discrete event already presented to the receiver is never
        // pre-empted. The continuous grant is locked on the same edge as the
        // Nth successful discrete handshake, so the next presented event is
        // the control and the bound cannot slip by one event.
        grant_control = !control_locked && (control_cooldown == 0) &&
            selected_valid &&
            (((fifo_count == 0) && !parsed_discrete) ||
             (discrete_handshake && burst_limit_reached));
    end

    // At most one locked control event; only unpresented slots may be merged.
    // Rate is measured from successful handshakes, so a stalled event cannot
    // accumulate emission credits or produce a post-stall control burst. When
    // an eligible control is waiting, at most MAX_DISCRETE_BURST successful
    // discrete handshakes may pass before one continuous-control opportunity.
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            control_cooldown <= '0;
            discrete_burst_count <= '0;
            control_pending <= '0;
            mod_sent_valid <= '0;
            control_locked <= 1'b0;
            locked_index <= '0;
            locked_event <= '0;
            round_robin_index <= '0;
            for (control_reset = 0; control_reset < 32; control_reset = control_reset + 1)
                pending_value[control_reset] <= '0;
            for (control_reset = 0; control_reset < 16; control_reset = control_reset + 1)
                mod_sent_value[control_reset] <= '0;
        end else begin
            if (control_cooldown != 0)
                control_cooldown <= control_cooldown - 1'b1;
            if (control_locked && event_ready) begin
                control_locked <= 1'b0;
                locked_event <= '0;
                control_cooldown <= RATE_WIDTH'(CONTROL_INTERVAL - 1);
                discrete_burst_count <= '0;
                if (locked_index[0]) begin
                    mod_sent_valid[locked_index[4:1]] <= 1'b1;
                    mod_sent_value[locked_index[4:1]] <= locked_event.control_value;
                end
            end
            if (!control_locked) begin
                if ((control_cooldown != 0) || !selected_valid) begin
                    discrete_burst_count <= '0;
                end else if (discrete_handshake && !burst_limit_reached) begin
                    discrete_burst_count <= discrete_burst_count + 1'b1;
                end
            end
            if (grant_control) begin
                control_locked <= 1'b1;
                locked_index <= selected_index;
                locked_event <= '0;
                locked_event.event_type <= selected_index[0] ?
                    EVENT_CONTROL_CHANGE : EVENT_PITCH_BEND;
                locked_event.source_id <= SOURCE_ID;
                locked_event.channel <= selected_index[4:1];
                locked_event.control_id <= selected_index[0] ?
                    CTRL_MODULATION : CTRL_PITCH_BEND;
                locked_event.control_value <= selected_value;
                control_pending[selected_index] <= 1'b0;
                round_robin_index <= selected_index + 5'd1;
            end
            if (parsed_control) begin
                pending_value[parsed_control_index] <= parsed_event_data.control_value;
                // Compare against the same-item in-flight value when present;
                // otherwise the last acknowledged CC1. Reverting an unsent
                // change cancels it without erasing the immutable in-flight event.
                if (grant_control && parsed_control_index == selected_index) begin
                    // The just-arrived newest value was captured by the lock.
                    control_pending[parsed_control_index] <= 1'b0;
                end else if (parsed_control_index[0] &&
                    ((control_locked && locked_index == parsed_control_index) ?
                     (locked_event.control_value == parsed_event_data.control_value) :
                     (mod_sent_valid[parsed_control_index[4:1]] &&
                      mod_sent_value[parsed_control_index[4:1]] ==
                          parsed_event_data.control_value))) begin
                    control_pending[parsed_control_index] <= 1'b0;
                end else begin
                    control_pending[parsed_control_index] <= 1'b1;
                end
            end
        end
    end

endmodule
