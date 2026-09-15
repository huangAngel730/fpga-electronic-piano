// 将去抖后的按键边沿转换为统一的 64 位演奏事件。
// 当前默认两路按键：MIDI 60（中央 C）和 MIDI 62（D），可通过参数扩展。
module button_event_converter #(
    parameter integer BUTTON_COUNT       = 2,
    parameter integer LOCAL_FIFO_DEPTH   = 4,
    parameter integer BASE_NOTE_NUMBER   = 60,
    parameter integer NOTE_STEP          = 2,
    parameter logic [3:0] SOURCE_ID       = 4'd0,
    parameter logic [3:0] CHANNEL         = 4'd0,
    parameter logic [9:0] NOTE_ON_VELOCITY = 10'd512
) (
    input  logic                                  clk,
    input  logic                                  rst_n,
    input  logic [BUTTON_COUNT-1:0]               button_press_pulse,
    input  logic [BUTTON_COUNT-1:0]               button_release_pulse,
    input  logic                                  event_ready,
    output logic                                  event_valid,
    output audio_defs_pkg::performance_event_t    event_data,
    output logic [31:0]                           overflow_count
);

    import audio_defs_pkg::*;

    localparam integer FIFO_COUNT_WIDTH =
        (LOCAL_FIFO_DEPTH <= 1) ? 1 : $clog2(LOCAL_FIFO_DEPTH + 1);

    performance_event_t fifo_mem      [0:LOCAL_FIFO_DEPTH-1];
    performance_event_t fifo_mem_next [0:LOCAL_FIFO_DEPTH-1];

    logic [FIFO_COUNT_WIDTH-1:0] fifo_count;
    logic [FIFO_COUNT_WIDTH-1:0] fifo_count_next;
    logic [31:0]                 overflow_increment;

    integer comb_fifo_index;
    integer comb_button_index;
    integer seq_fifo_index;

    // 根据按键编号生成完整事件。未使用的公共字段明确清零。
    function automatic performance_event_t make_note_event(
        input logic [2:0] event_type_value,
        input integer     key_index
    );
        performance_event_t new_event;
        integer             note_value;
        begin
            note_value              = BASE_NOTE_NUMBER + (key_index * NOTE_STEP);
            new_event               = '0;
            new_event.event_type    = event_type_value;
            new_event.source_id     = SOURCE_ID;
            new_event.channel       = CHANNEL;
            new_event.note_number   = note_value[6:0];
            new_event.velocity      =
                (event_type_value == EVENT_NOTE_ON) ? NOTE_ON_VELOCITY : 10'd0;
            make_note_event         = new_event;
        end
    endfunction

    // 输出只由已寄存的 FIFO 头部决定，不形成 ready-valid 组合环路。
    always_comb begin
        event_valid = (fifo_count != {FIFO_COUNT_WIDTH{1'b0}});
        event_data  = '0;
        if (event_valid) begin
            event_data = fifo_mem[0];
        end
    end

    // 先移除已握手事件，再按按键编号从小到大加入本拍的新事件。
    // 因为输入脉冲不能反压，本地 FIFO 满时记录溢出，禁止静默丢失。
    always_comb begin
        fifo_count_next    = fifo_count;
        overflow_increment = 32'd0;

        for (comb_fifo_index = 0; comb_fifo_index < LOCAL_FIFO_DEPTH; comb_fifo_index = comb_fifo_index + 1) begin
            fifo_mem_next[comb_fifo_index] = fifo_mem[comb_fifo_index];
        end

        if (event_valid && event_ready) begin
            for (comb_fifo_index = 0; comb_fifo_index < LOCAL_FIFO_DEPTH - 1; comb_fifo_index = comb_fifo_index + 1) begin
                fifo_mem_next[comb_fifo_index] = fifo_mem[comb_fifo_index + 1];
            end
            fifo_mem_next[LOCAL_FIFO_DEPTH - 1] = '0;
            fifo_count_next = fifo_count - 1'b1;
        end

        for (comb_button_index = 0; comb_button_index < BUTTON_COUNT; comb_button_index = comb_button_index + 1) begin
            if (button_press_pulse[comb_button_index]) begin
                if (fifo_count_next < LOCAL_FIFO_DEPTH) begin
                    fifo_mem_next[fifo_count_next] =
                        make_note_event(EVENT_NOTE_ON, comb_button_index);
                    fifo_count_next = fifo_count_next + 1'b1;
                end else begin
                    overflow_increment = overflow_increment + 32'd1;
                end
            end

            if (button_release_pulse[comb_button_index]) begin
                if (fifo_count_next < LOCAL_FIFO_DEPTH) begin
                    fifo_mem_next[fifo_count_next] =
                        make_note_event(EVENT_NOTE_OFF, comb_button_index);
                    fifo_count_next = fifo_count_next + 1'b1;
                end else begin
                    overflow_increment = overflow_increment + 32'd1;
                end
            end
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            fifo_count     <= {FIFO_COUNT_WIDTH{1'b0}};
            overflow_count <= 32'd0;
            for (seq_fifo_index = 0; seq_fifo_index < LOCAL_FIFO_DEPTH; seq_fifo_index = seq_fifo_index + 1) begin
                fifo_mem[seq_fifo_index] <= '0;
            end
        end else begin
            fifo_count <= fifo_count_next;
            for (seq_fifo_index = 0; seq_fifo_index < LOCAL_FIFO_DEPTH; seq_fifo_index = seq_fifo_index + 1) begin
                fifo_mem[seq_fifo_index] <= fifo_mem_next[seq_fifo_index];
            end

            // 溢出计数采用饱和方式，避免计数器回绕后掩盖历史错误。
            if (overflow_increment != 32'd0) begin
                if (overflow_count >= (32'hFFFF_FFFF - overflow_increment)) begin
                    overflow_count <= 32'hFFFF_FFFF;
                end else begin
                    overflow_count <= overflow_count + overflow_increment;
                end
            end
        end
    end

endmodule
