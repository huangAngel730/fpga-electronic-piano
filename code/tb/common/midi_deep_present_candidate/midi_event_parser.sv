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
    logic discrete_presented;
    wire discrete_handshake = discrete_presented && !control_locked && event_ready;
    wire burst_limit_reached = (MAX_DISCRETE_BURST <= 1) ||
        (discrete_burst_count >= (MAX_DISCRETE_BURST - 1));
    integer control_reset;

    // Candidate only: reserve before presenting a new FIFO head. The copied
    // head is NOT popped until real external consumption; capacity stays D.
    performance_event_t presented_event;
    logic selection_busy;
    logic [1:0] recent_count;
    logic [4:0] recent_index [0:1];
    logic [31:0] eligible_mask;
    wire selector_ready, selector_valid;
    wire [3:0] snapshot_valid;
    wire [19:0] snapshot_indices;
    wire head_boundary = !control_locked &&
        (!discrete_presented || discrete_handshake);
    wire reserve_control = head_boundary && !selection_busy &&
        (control_cooldown == 0) && (|eligible_mask) &&
        ((fifo_count_next == 0) ||
         (discrete_burst_count >= MAX_DISCRETE_BURST) ||
         (discrete_handshake && burst_limit_reached));
    wire start_selection = reserve_control && selector_ready;
    control_snapshot_top4 u_deep_selector(
        .clk(clk),.rst_n(rst_n),.request_valid(start_selection),
        .request_ready(selector_ready),.request_mask(eligible_mask),
        .request_rr(round_robin_index),.result_valid(selector_valid),
        .result_ready(selection_busy),.winner_valid(snapshot_valid),
        .winner_indices(snapshot_indices));
    // At most three post-capture updates precede the E+3 lock. Four old
    // winners plus the two recorded updates and current update suffice to
    // recover EXACT live RR priority, without global-epoch retries.
    logic [6:0] repair_valid;
    logic [4:0] repair_index [0:6];
    logic [4:0] repair_rank [0:6];
    logic tree_valid [1:15];
    logic [4:0] tree_rank [1:15],tree_index [1:15];
    always_comb begin
        for(integer k=0;k<7;k++)begin
            repair_valid[k]=0;repair_index[k]=0;repair_rank[k]=0;
        end
        for(integer k=0;k<4;k++)begin
            repair_index[k]=snapshot_indices[5*k+:5];
            repair_valid[k]=snapshot_valid[k] && eligible_mask[repair_index[k]];
        end
        for(integer k=0;k<2;k++)begin
            repair_index[4+k]=recent_index[k];
            repair_valid[4+k]=(k<recent_count) && eligible_mask[recent_index[k]];
        end
        repair_index[6]=parsed_control_index;
        repair_valid[6]=parsed_control && parsed_control_keep_pending;
        for(integer k=0;k<7;k++)repair_rank[k]=repair_index[k]-round_robin_index;
        for(integer k=0;k<8;k++)begin
            tree_valid[8+k]=k<7?repair_valid[k]:1'b0;
            tree_rank[8+k]=k<7?repair_rank[k]:5'd0;
            tree_index[8+k]=k<7?repair_index[k]:5'd0;
        end
        for(integer n=7;n>=1;n--)begin
            tree_valid[n]=tree_valid[2*n] || tree_valid[2*n+1];
            if(tree_valid[2*n] && (!tree_valid[2*n+1] || tree_rank[2*n]<=tree_rank[2*n+1]))begin
                tree_rank[n]=tree_rank[2*n];tree_index[n]=tree_index[2*n];
            end else begin tree_rank[n]=tree_rank[2*n+1];tree_index[n]=tree_index[2*n+1];end
        end
    end
    always_ff @(posedge clk)begin
        if(!rst_n)begin
            discrete_presented<=0;presented_event<='0;selection_busy<=0;
            recent_count<=0;recent_index[0]<=0;recent_index[1]<=0;
        end else begin
            if(discrete_handshake)begin discrete_presented<=0;presented_event<='0;end
            if(start_selection)begin selection_busy<=1;recent_count<=0;end
            else if(selection_busy && selector_valid)begin selection_busy<=0;recent_count<=0;end
            else if(selection_busy && parsed_control && recent_count<2)begin
                recent_index[recent_count]<=parsed_control_index;recent_count<=recent_count+1'b1;
            end
            if((!discrete_presented || discrete_handshake) &&
               (!control_locked || event_ready) && !selection_busy &&
               !start_selection && fifo_count_next!=0)begin
                discrete_presented<=1;presented_event<=fifo_mem_next[0];
            end
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
        event_valid      = control_locked || discrete_presented;
        event_data       = '0;
        event_fifo_level = fifo_count;
        if (control_locked) begin
            event_data = locked_event;
        end else if (event_valid) begin
            event_data = presented_event;
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

        if (discrete_handshake) begin
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

        eligible_mask = control_pending;
        if(parsed_control)eligible_mask[parsed_control_index]=parsed_control_keep_pending;
        selected_valid = selector_valid && selection_busy && tree_valid[1];
        selected_index = tree_index[1];
        selected_value = pending_value[selected_index];
        if(parsed_control && parsed_control_index==selected_index)
            selected_value=parsed_event_data.control_value;
        grant_control = !control_locked && selected_valid;
    end

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
            if(!control_locked && !selection_busy)begin
                if(control_cooldown!=0 || !(|eligible_mask))discrete_burst_count<='0;
                else if(discrete_handshake && discrete_burst_count<MAX_DISCRETE_BURST)
                    discrete_burst_count<=discrete_burst_count+1'b1;
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
