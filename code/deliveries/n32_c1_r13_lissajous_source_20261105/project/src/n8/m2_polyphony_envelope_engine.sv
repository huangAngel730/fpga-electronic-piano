// Shared N=4/8/16/32 dual-timbre envelope engine.
//
// One arithmetic datapath and one state-memory port are time-multiplexed over
// all voices. The complete per-voice state is packed into block RAM. Only the
// public envelope/state mirrors remain as registers, removing the wide dynamic
// muxes produced by independently indexed register arrays.
`timescale 1ns/1ps

module m2_polyphony_envelope_engine #(
    parameter integer N = 32,
    parameter integer SW = $clog2(N),
    parameter PIANO_VELOCITY_ROM_FILE = "rom/velocity_gain_rom.mem",
    parameter ORGAN_VELOCITY_ROM_FILE = "rom/organ_velocity_gain_1024.mem"
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  event_start,
    input  wire [N-1:0]          note_on,
    input  wire [N-1:0]          note_off,
    input  wire [N*10-1:0]       velocity,
    input  wire [N-1:0]          timbres,
    input  wire                  sample_start,
    output logic                 busy,
    output logic                 done,
    output wire [N*16-1:0]       live_envelopes,
    output wire [N*3-1:0]        live_states
);
    localparam logic [2:0] ENV_IDLE    = 3'd0;
    localparam logic [2:0] ENV_ATTACK  = 3'd1;
    localparam logic [2:0] ENV_DECAY   = 3'd2;
    localparam logic [2:0] ENV_SUSTAIN = 3'd3;
    localparam logic [2:0] ENV_RELEASE = 3'd4;

    localparam integer PIANO_ATTACK_SAMPLES  = 240;
    localparam integer PIANO_DECAY_SAMPLES   = 4800;
    localparam integer PIANO_RELEASE_SAMPLES = 4800;
    localparam logic signed [25:0] ATTACK_RECIP_Q32 = 26'sd17895697;
    localparam logic signed [25:0] LONG_RECIP_Q32   = 26'sd894785;
    localparam logic [13:0] SUSTAIN_RATE_Q32 = 14'd13422;
    localparam logic [31:0] LEVEL_MAX_Q16 = 32'h7fff0000;

    localparam logic [3:0] ENG_INIT          = 4'd0;
    localparam logic [3:0] ENG_IDLE          = 4'd1;
    localparam logic [3:0] LOAD_WAIT         = 4'd2;
    localparam logic [3:0] LOAD_STATE        = 4'd3;
    localparam logic [3:0] EVENT_SCAN        = 4'd4;
    localparam logic [3:0] EVENT_ROM_WAIT    = 4'd5;
    localparam logic [3:0] EVENT_ON_PREP     = 4'd6;
    localparam logic [3:0] EVENT_ON_STEP     = 4'd7;
    localparam logic [3:0] EVENT_OFF_PREP    = 4'd8;
    localparam logic [3:0] EVENT_OFF_STEP    = 4'd9;
    localparam logic [3:0] SAMPLE_SCAN       = 4'd10;
    localparam logic [3:0] SAMPLE_DECAY_PREP = 4'd11;
    localparam logic [3:0] SAMPLE_DECAY_SET  = 4'd12;
    localparam logic [3:0] SAMPLE_SUS_PREP   = 4'd13;
    localparam logic [3:0] SAMPLE_SUS_SET    = 4'd14;
    localparam logic [3:0] COMMIT_STATE      = 4'd15;

    localparam integer PACKED_W = 146;
    localparam integer ELAPSED_LSB = 0;
    localparam integer STEP_LSB = 13;
    localparam integer SUSTAIN_LSB = 46;
    localparam integer PEAK_LSB = 78;
    localparam integer LEVEL_LSB = 110;
    localparam integer STATE_LSB = 142;
    localparam integer TIMBRE_BIT = 145;

    logic [3:0] engine_state;
    logic [SW-1:0] cursor;
    logic operation_is_event;
    logic [N-1:0] event_on_q, event_off_q, event_timbre_q;
    logic [N*10-1:0] event_velocity_q;

    // GowinSynthesis maps this synchronous, non-reset memory to BSRAM.
    (* ram_style = "block" *) logic [PACKED_W-1:0] state_mem [0:N-1];
    logic [SW-1:0] mem_read_addr;
    logic [PACKED_W-1:0] mem_read_data;
    wire mem_write_enable = (engine_state == ENG_INIT) ||
                            (engine_state == COMMIT_STATE);
    wire [SW-1:0] mem_write_addr = cursor;

    logic work_timbre;
    logic [2:0] work_state;
    logic [31:0] work_level;
    logic [31:0] work_peak;
    logic [31:0] work_sustain;
    logic signed [32:0] work_step;
    logic [12:0] work_elapsed;

    wire [PACKED_W-1:0] packed_work = {
        work_timbre, work_state, work_level, work_peak, work_sustain,
        work_step, work_elapsed
    };
    wire [PACKED_W-1:0] mem_write_data =
        (engine_state == ENG_INIT) ? {PACKED_W{1'b0}} : packed_work;

    // Single-port synchronous RAM. Reset never drives the array itself.
    always_ff @(posedge clk) begin
        if (mem_write_enable)
            state_mem[mem_write_addr] <= mem_write_data;
        else
            mem_read_data <= state_mem[mem_read_addr];
    end

    logic [15:0] live_envelope_q [0:N-1];
    logic [2:0] live_state_q [0:N-1];
    for (genvar g=0;g<N;g=g+1) begin : g_outputs
        assign live_envelopes[16*g+:16] = live_envelope_q[g];
        assign live_states[3*g+:3] = live_state_q[g];
    end

    logic [9:0] rom_addr;
    logic [15:0] piano_rom_dout, organ_rom_dout;
    logic [15:0] piano_gain_rom [0:1023];
    logic [15:0] organ_gain_rom [0:1023];
    logic [31:0] event_start_level;
    logic event_selected_timbre;
    logic signed [58:0] product_q;
    logic [44:0] sustain_product_q;

    wire [31:0] selected_gain_q16 = event_selected_timbre ?
        {organ_rom_dout,16'd0} : {piano_rom_dout,16'd0};
    wire signed [32:0] quotient_q16 =
        {{6{product_q[58]}},product_q[58:32]};
    wire [31:0] piano_sustain_calc =
        (({16'd0,piano_rom_dout} * 32'd13108) >> 15) << 16;

    // synthesis translate_off
    string piano_rom_path, organ_rom_path;
    integer rom_index;
    // synthesis translate_on
    initial begin
        // synthesis translate_off
        if ($value$plusargs("VELOCITY_ROM_PATH=%s", piano_rom_path)) begin
            $readmemh(piano_rom_path, piano_gain_rom);
        end else begin
            piano_rom_path = PIANO_VELOCITY_ROM_FILE;
        // synthesis translate_on
            $readmemh(PIANO_VELOCITY_ROM_FILE, piano_gain_rom);
        // synthesis translate_off
        end
        if ($value$plusargs("ORGAN_VELOCITY_ROM_PATH=%s", organ_rom_path)) begin
            $readmemh(organ_rom_path, organ_gain_rom);
        end else begin
            organ_rom_path = ORGAN_VELOCITY_ROM_FILE;
        // synthesis translate_on
            $readmemh(ORGAN_VELOCITY_ROM_FILE, organ_gain_rom);
        // synthesis translate_off
        end
        for (rom_index=0;rom_index<1024;rom_index=rom_index+1) begin
            if (^piano_gain_rom[rom_index] === 1'bx)
                $fatal(1,"Missing Piano velocity ROM word %0d",rom_index);
            if (^organ_gain_rom[rom_index] === 1'bx)
                $fatal(1,"Missing Organ velocity ROM word %0d",rom_index);
        end
        // synthesis translate_on
    end

    always_ff @(posedge clk) begin
        piano_rom_dout <= piano_gain_rom[rom_addr];
        organ_rom_dout <= organ_gain_rom[rom_addr];
    end

    function automatic [31:0] organ_attack_level(
        input [31:0] old_level,
        input signed [32:0] old_step,
        input [31:0] target
    );
        logic signed [32:0] next_value;
        begin
            next_value = $signed({1'b0,old_level}) + old_step;
            if ((old_step < 33'sd0) &&
                (next_value < $signed({1'b0,target})))
                organ_attack_level = target;
            else if ((old_step >= 33'sd0) &&
                     (next_value > $signed({1'b0,target})))
                organ_attack_level = target;
            else if (next_value < 33'sd0)
                organ_attack_level = 32'd0;
            else if (next_value > $signed({1'b0,LEVEL_MAX_Q16}))
                organ_attack_level = LEVEL_MAX_Q16;
            else
                organ_attack_level = next_value[31:0];
        end
    endfunction

    task automatic finish_cursor;
        begin
            if (cursor == N-1) begin
                cursor <= {SW{1'b0}};
                engine_state <= ENG_IDLE;
                busy <= 1'b0;
                done <= 1'b1;
            end else begin
                cursor <= cursor + 1'b1;
                mem_read_addr <= cursor + 1'b1;
                engine_state <= LOAD_WAIT;
            end
        end
    endtask

    integer i;
    logic signed [32:0] next_level;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            engine_state <= ENG_INIT;
            cursor <= {SW{1'b0}};
            mem_read_addr <= {SW{1'b0}};
            operation_is_event <= 1'b0;
            event_on_q <= {N{1'b0}};
            event_off_q <= {N{1'b0}};
            event_timbre_q <= {N{1'b0}};
            event_velocity_q <= {(N*10){1'b0}};
            work_timbre <= 1'b0;
            work_state <= ENV_IDLE;
            work_level <= 32'd0;
            work_peak <= 32'd0;
            work_sustain <= 32'd0;
            work_step <= 33'sd0;
            work_elapsed <= 13'd0;
            rom_addr <= 10'd0;
            event_start_level <= 32'd0;
            event_selected_timbre <= 1'b0;
            product_q <= 59'sd0;
            sustain_product_q <= 45'd0;
            busy <= 1'b1;
            done <= 1'b0;
            next_level <= 33'sd0;
            for (i=0;i<N;i=i+1) begin
                live_envelope_q[i] <= 16'd0;
                live_state_q[i] <= ENV_IDLE;
            end
        end else begin
            done <= 1'b0;
            case (engine_state)
                ENG_INIT: begin
                    live_envelope_q[cursor] <= 16'd0;
                    live_state_q[cursor] <= ENV_IDLE;
                    if (cursor == N-1) begin
                        cursor <= {SW{1'b0}};
                        engine_state <= ENG_IDLE;
                        busy <= 1'b0;
                    end else begin
                        cursor <= cursor + 1'b1;
                    end
                end

                ENG_IDLE: begin
                    if (event_start) begin
                        event_on_q <= note_on;
                        event_off_q <= note_off;
                        event_timbre_q <= timbres;
                        event_velocity_q <= velocity;
                        operation_is_event <= 1'b1;
                        cursor <= {SW{1'b0}};
                        mem_read_addr <= {SW{1'b0}};
                        busy <= 1'b1;
                        engine_state <= LOAD_WAIT;
                    end else if (sample_start) begin
                        operation_is_event <= 1'b0;
                        cursor <= {SW{1'b0}};
                        mem_read_addr <= {SW{1'b0}};
                        busy <= 1'b1;
                        engine_state <= LOAD_WAIT;
                    end
                end

                LOAD_WAIT: engine_state <= LOAD_STATE;

                LOAD_STATE: begin
                    work_elapsed <= mem_read_data[ELAPSED_LSB+:13];
                    work_step <= mem_read_data[STEP_LSB+:33];
                    work_sustain <= mem_read_data[SUSTAIN_LSB+:32];
                    work_peak <= mem_read_data[PEAK_LSB+:32];
                    work_level <= mem_read_data[LEVEL_LSB+:32];
                    work_state <= mem_read_data[STATE_LSB+:3];
                    work_timbre <= mem_read_data[TIMBRE_BIT];
                    engine_state <= operation_is_event ? EVENT_SCAN : SAMPLE_SCAN;
                end

                EVENT_SCAN: begin
                    if (event_on_q[cursor]) begin
                        rom_addr <= event_velocity_q[10*cursor+:10];
                        event_start_level <= work_level;
                        event_selected_timbre <= event_timbre_q[cursor];
                        engine_state <= EVENT_ROM_WAIT;
                    end else if (event_off_q[cursor] &&
                                 work_state != ENV_IDLE) begin
                        event_start_level <= work_level;
                        event_selected_timbre <= work_timbre;
                        engine_state <= EVENT_OFF_PREP;
                    end else begin
                        finish_cursor();
                    end
                end

                EVENT_ROM_WAIT: engine_state <= EVENT_ON_PREP;

                EVENT_ON_PREP: begin
                    work_peak <= selected_gain_q16;
                    work_timbre <= event_selected_timbre;
                    work_elapsed <= 13'd0;
                    work_state <= ENV_ATTACK;
                    if (event_selected_timbre) begin
                        work_sustain <= selected_gain_q16;
                        work_step <=
                            ($signed({1'b0,selected_gain_q16}) -
                             $signed({1'b0,event_start_level})) >>> 7;
                        engine_state <= COMMIT_STATE;
                    end else begin
                        product_q <=
                            ($signed({1'b0,selected_gain_q16}) -
                             $signed({1'b0,event_start_level})) *
                            ATTACK_RECIP_Q32;
                        work_sustain <= piano_sustain_calc;
                        engine_state <= EVENT_ON_STEP;
                    end
                end

                EVENT_ON_STEP: begin
                    work_step <= quotient_q16;
                    engine_state <= COMMIT_STATE;
                end

                EVENT_OFF_PREP: begin
                    work_elapsed <= 13'd0;
                    if (event_start_level == 32'd0) begin
                        work_level <= 32'd0;
                        work_step <= 33'sd0;
                        work_state <= ENV_IDLE;
                        engine_state <= COMMIT_STATE;
                    end else if (event_selected_timbre) begin
                        work_step <=
                            (-$signed({1'b0,event_start_level})) >>> 10;
                        work_state <= ENV_RELEASE;
                        engine_state <= COMMIT_STATE;
                    end else begin
                        product_q <=
                            (-$signed({1'b0,event_start_level})) *
                            LONG_RECIP_Q32;
                        work_state <= ENV_RELEASE;
                        engine_state <= EVENT_OFF_STEP;
                    end
                end

                EVENT_OFF_STEP: begin
                    work_step <= quotient_q16;
                    engine_state <= COMMIT_STATE;
                end

                SAMPLE_SCAN: begin
                    if (work_timbre) begin
                        case (work_state)
                            ENV_ATTACK: begin
                                if (work_elapsed == 13'd127) begin
                                    work_level <= work_peak;
                                    work_step <= 33'sd0;
                                    work_elapsed <= 13'd0;
                                    work_state <= ENV_SUSTAIN;
                                end else begin
                                    work_level <= organ_attack_level(
                                        work_level,work_step,work_peak);
                                    work_elapsed <= work_elapsed + 1'b1;
                                end
                                engine_state <= COMMIT_STATE;
                            end
                            ENV_SUSTAIN: begin
                                work_level <= work_peak;
                                engine_state <= COMMIT_STATE;
                            end
                            ENV_RELEASE: begin
                                next_level = $signed({1'b0,work_level}) +
                                             work_step;
                                if (work_elapsed == 13'd1023) begin
                                    work_level <= 32'd0;
                                    work_step <= 33'sd0;
                                    work_elapsed <= 13'd0;
                                    work_state <= ENV_IDLE;
                                end else begin
                                    work_level <= next_level <= 0 ?
                                        32'd0 : next_level[31:0];
                                    work_elapsed <= work_elapsed + 1'b1;
                                end
                                engine_state <= COMMIT_STATE;
                            end
                            default: begin
                                if (work_level != 32'd0) begin
                                    work_level <= 32'd0;
                                    engine_state <= COMMIT_STATE;
                                end else begin
                                    finish_cursor();
                                end
                            end
                        endcase
                    end else begin
                        case (work_state)
                            ENV_ATTACK: begin
                                if (work_elapsed == PIANO_ATTACK_SAMPLES-1) begin
                                    product_q <=
                                        ($signed({1'b0,work_sustain}) -
                                         $signed({1'b0,work_peak})) *
                                        LONG_RECIP_Q32;
                                    engine_state <= SAMPLE_DECAY_PREP;
                                end else begin
                                    next_level =
                                        $signed({1'b0,work_level}) + work_step;
                                    work_level <= next_level[31:0];
                                    work_elapsed <= work_elapsed + 1'b1;
                                    engine_state <= COMMIT_STATE;
                                end
                            end
                            ENV_DECAY: begin
                                if (work_elapsed == PIANO_DECAY_SAMPLES) begin
                                    work_level <= work_sustain;
                                    work_elapsed <= 13'd0;
                                    work_state <= ENV_SUSTAIN;
                                end else begin
                                    next_level =
                                        $signed({1'b0,work_level}) + work_step;
                                    work_level <= next_level[31:0];
                                    work_elapsed <= work_elapsed + 1'b1;
                                end
                                engine_state <= COMMIT_STATE;
                            end
                            ENV_SUSTAIN: begin
                                if (work_level < 32'd65536) begin
                                    work_level <= 32'd0;
                                    work_state <= ENV_IDLE;
                                    engine_state <= COMMIT_STATE;
                                end else begin
                                    sustain_product_q <=
                                        work_level[30:0] * SUSTAIN_RATE_Q32;
                                    engine_state <= SAMPLE_SUS_PREP;
                                end
                            end
                            ENV_RELEASE: begin
                                next_level =
                                    $signed({1'b0,work_level}) + work_step;
                                if (work_elapsed == PIANO_RELEASE_SAMPLES-1) begin
                                    work_level <= 32'd0;
                                    work_elapsed <= 13'd0;
                                    work_state <= ENV_IDLE;
                                end else begin
                                    work_level <= next_level <= 0 ?
                                        32'd0 : next_level[31:0];
                                    work_elapsed <= work_elapsed + 1'b1;
                                end
                                engine_state <= COMMIT_STATE;
                            end
                            default: begin
                                if (work_level != 32'd0) begin
                                    work_level <= 32'd0;
                                    engine_state <= COMMIT_STATE;
                                end else begin
                                    finish_cursor();
                                end
                            end
                        endcase
                    end
                end

                SAMPLE_DECAY_PREP: engine_state <= SAMPLE_DECAY_SET;

                SAMPLE_DECAY_SET: begin
                    work_level <= work_peak;
                    work_step <= quotient_q16;
                    work_elapsed <= 13'd0;
                    work_state <= ENV_DECAY;
                    engine_state <= COMMIT_STATE;
                end

                SAMPLE_SUS_PREP: engine_state <= SAMPLE_SUS_SET;

                SAMPLE_SUS_SET: begin
                    work_level <= work_level -
                        ({1'b0,sustain_product_q} >> 32);
                    engine_state <= COMMIT_STATE;
                end

                COMMIT_STATE: begin
                    live_envelope_q[cursor] <= work_level[31:16];
                    live_state_q[cursor] <= work_state;
                    finish_cursor();
                end

                default: begin
                    engine_state <= ENG_INIT;
                    cursor <= {SW{1'b0}};
                    busy <= 1'b1;
                end
            endcase
        end
    end

    // synthesis translate_off
    initial begin
        if (!(N==4 || N==8 || N==16 || N==32))
            $fatal(1,"POLY_N_NOT_SUPPORTED");
        if (SW != $clog2(N))
            $fatal(1,"POLY_BAD_SLOT_WIDTH");
    end
    always @(posedge clk) begin
        if (rst_n && event_start && busy)
            $fatal(1,"Envelope event_start while busy");
        if (rst_n && sample_start && busy)
            $fatal(1,"Envelope sample_start while busy");
        if (rst_n && event_start && sample_start)
            $fatal(1,"Envelope event and sample start collided");
    end
    // synthesis translate_on
endmodule
