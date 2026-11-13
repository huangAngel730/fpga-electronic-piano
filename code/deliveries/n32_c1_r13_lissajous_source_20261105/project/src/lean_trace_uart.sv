// Diagnostic-only tap. All inputs sampled PRE_NBA on clk; no audio ready/control.
// Synchronous active-low reset clears control/pointers, never the RAM contents.
// Eight short synchronous-read stage queues serialize into a shared RAM FIFO.
// Full stage queues drop diagnostic records only. Sequence counts every attempt.
// UART packet/CRC are serialized in registers; CRC takes one bit per clk.
`timescale 1ns/1ps
module lean_trace_uart #(
    parameter integer CLK_HZ = 40_000_000,
    parameter integer BAUD = 115_200,
    parameter integer FIFO_DEPTH = 512,
    parameter integer STAGE_DEPTH = 16,
    parameter integer REPORT_CYCLES = CLK_HZ,
    parameter logic [31:0] COUNTER_MAX = 32'hffffffff
)(
    input wire clk, rst_n,
    input wire [7:0] capture_valid,
    input wire [1023:0] capture_payload,
    output wire tx,
    output wire [255:0] dropped
);
    // Native09 diagnostic boundary: all eight event valids and all payload
    // fields are captured together, unconditionally, PRE_NBA. The entire
    // diagnostic machine including its synchronous reset runs one clk later.
    // Therefore UART bits, timestamps, sequence/drop/full decisions and all
    // status outputs equal the previous implementation delayed exactly1clk.
    // No signal from this observer feeds the real audio ready/data path.
    logic trace_rst_n;
    logic[7:0]captured_valid_q;
    logic[1023:0]captured_payload_q;
    wire[1031:0]trace_capture_raw={capture_valid,capture_payload};
    wire[1031:0]trace_capture_held;
    for(genvar cap_bit=0;cap_bit<1032;cap_bit=cap_bit+1)begin:g_input_capture_hold
        (* syn_keep=1, syn_dont_touch=1 *) wire[2:0]chain;
        assign chain[0]=trace_capture_raw[cap_bit];
        for(genvar cap_stage=0;cap_stage<2;cap_stage=cap_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2))u_identity(
                .I0(chain[cap_stage]),.F(chain[cap_stage+1]));
        end
        assign trace_capture_held[cap_bit]=chain[2];
    end
    // The data FFs need no reset: delayed reset prevents their use until the
    // original synchronous-reset edge has reached the diagnostic machine.
    // Supply >=2 reset clock edges at startup, as the production reset does.
    always_ff @(posedge clk)begin
        trace_rst_n<=rst_n;
        {captured_valid_q,captured_payload_q}<=trace_capture_held;
    end

    localparam integer AW = $clog2(FIFO_DEPTH);
    localparam integer CW = $clog2(FIFO_DEPTH+1);
    // No reset on memory read register or contents: supports synchronous RAM.
    logic [215:0] memory [0:FIFO_DEPTH-1];
    logic [215:0] read_data;
    logic [AW-1:0] wr_ptr, rd_ptr;
    logic [CW-1:0] count;
    logic [47:0] timestamp;
    logic [7:0] pending;
    wire [207:0] stage_read_data [0:7];
    logic [31:0] stage_seq [0:7];
    logic [31:0] drop_count [0:7];
    logic [2:0] scan;
    logic mux_valid;
    logic [215:0] mux_data;
    logic arb_wait;
    logic [2:0] selected;
    // BEGIN TRACE_SELECTED_HOLD_R03
    // One transparent consumer branch for both header and RAM read index.
    // Six kept identity LUTs; no new state, clock, enable or protocol cycle.
    (* syn_keep=1, syn_preserve=1, syn_dont_touch=1 *) wire [2:0] selected_hold_l0, selected_hold_l1;
    generate for(genvar si=0;si<3;si=si+1)begin:g_trace_selected_hold
        (* syn_keep=1, syn_preserve=1, syn_dont_touch=1 *)
        LUT1 #(.INIT(2'h2)) u_hold_0(.I0(selected[si]),.F(selected_hold_l0[si]));
        (* syn_keep=1, syn_preserve=1, syn_dont_touch=1 *)
        LUT1 #(.INIT(2'h2)) u_hold_1(.I0(selected_hold_l0[si]),.F(selected_hold_l1[si]));
    end endgenerate
    // END TRACE_SELECTED_HOLD_R03
    wire grab = !mux_valid && !arb_wait && pending[scan];
    wire push = mux_valid && count < FIFO_DEPTH;

    // BEGIN TRACE_HOLD_R05_MAIN
    // Consumer-side two-LUT identity chains; no registers/latency/enable change.
    (* syn_keep=1, syn_dont_touch=1 *) wire [AW-1:0] trace_wr_addr_l0, trace_wr_addr_l1;
    (* syn_keep=1, syn_dont_touch=1 *) wire [AW-1:0] trace_rd_addr_l0, trace_rd_addr_l1;
    (* syn_keep=1, syn_dont_touch=1 *) wire [215:0] trace_write_data_l0, trace_write_data_l1;
    generate for(genvar hb=0;hb<AW;hb=hb+1)begin:g_trace_main_address_hold
        LUT1 #(.INIT(2'h2)) u_wr_hold_0(.I0(wr_ptr[hb]),.F(trace_wr_addr_l0[hb]));
        LUT1 #(.INIT(2'h2)) u_wr_hold_1(.I0(trace_wr_addr_l0[hb]),.F(trace_wr_addr_l1[hb]));
        LUT1 #(.INIT(2'h2)) u_rd_hold_0(.I0(rd_ptr[hb]),.F(trace_rd_addr_l0[hb]));
        LUT1 #(.INIT(2'h2)) u_rd_hold_1(.I0(trace_rd_addr_l0[hb]),.F(trace_rd_addr_l1[hb]));
    end
    for(genvar hd=0;hd<216;hd=hd+1)begin:g_trace_main_data_hold
        LUT1 #(.INIT(2'h2)) u_data_hold_0(.I0(mux_data[hd]),.F(trace_write_data_l0[hd]));
        LUT1 #(.INIT(2'h2)) u_data_hold_1(.I0(trace_write_data_l0[hd]),.F(trace_write_data_l1[hd]));
    end endgenerate
    // END TRACE_HOLD_R05_MAIN

    typedef enum logic [2:0] {IDLE, READ_WAIT, PREP, SEND, CRC_STEP} state_t;
    state_t state;
    wire pop = state == IDLE && count != 0;
    logic [255:0] body_shift;
    logic [5:0] byte_index;
    logic [7:0] byte_data;
    logic [15:0] crc;
    // Native09 CRC4 -> byte_data4/D Hold repair. Preserve the existing mux,
    // PREP capture edge and UART/CRC schedule; pad all8 data-consumer bits.
    logic[7:0]next_byte;
    wire[7:0]byte_data_capture;
    always_comb begin
        case(byte_index)
            0:next_byte=8'ha5;
            1:next_byte=8'h5a;
            34:next_byte=crc[7:0];
            35:next_byte=crc[15:8];
            default:next_byte=body_shift[7:0];
        endcase
    end
    for(genvar byte_bit=0;byte_bit<8;byte_bit=byte_bit+1)begin:g_byte_capture_hold
        (* syn_keep=1, syn_dont_touch=1 *)wire[2:0]chain;
        assign chain[0]=next_byte[byte_bit];
        for(genvar byte_stage=0;byte_stage<2;byte_stage=byte_stage+1)begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *)LUT1 #(.INIT(2'h2))u_identity(
                .I0(chain[byte_stage]),.F(chain[byte_stage+1]));
        end
        assign byte_data_capture[byte_bit]=chain[2];
    end
    logic [3:0] crc_steps;
    wire byte_ready;
    wire byte_valid = state == SEND;
    logic [31:0] report_count;
    logic [7:0] stat_due;
    logic [2:0] stat_scan;
    wire report_tick = report_count == REPORT_CYCLES-1;
    wire start_stat = state == IDLE && count == 0 && stat_due[stat_scan];

    genvar g;
    generate for(g=0;g<8;g=g+1)begin:g_capture
        localparam integer SW = $clog2(STAGE_DEPTH);
        localparam integer SCW = $clog2(STAGE_DEPTH+1);
        // Separate synchronous read/write ports, no memory/reset loop.
        logic [207:0] stage_memory [0:STAGE_DEPTH-1];
        logic [207:0] stage_read_reg;
        logic [SW-1:0] write_pointer, read_pointer;
        logic [SCW-1:0] stage_count;
        wire stage_pop = grab && scan==g;
        wire stage_write = captured_valid_q[g] && stage_count<STAGE_DEPTH;
        assign pending[g] = stage_count!=0;
        assign stage_read_data[g] = stage_read_reg;
        assign dropped[g*32+:32] = drop_count[g];
        // R13 PROPOSAL ONLY: split late capture enable from registered-state D.
        // stage_pop uses only existing registered queue/arbiter state.
        // stage_write is late; it appears only in this native CE expression.
        (* syn_keep=1, syn_dont_touch=1 *) wire [SCW-1:0] stage_count_plus = stage_count + 1'b1;
        (* syn_keep=1, syn_dont_touch=1 *) wire [SCW-1:0] stage_count_minus = stage_count - 1'b1;
        (* syn_keep=1, syn_dont_touch=1 *) wire [SCW-1:0] stage_count_data = stage_pop ? stage_count_minus : stage_count_plus;
        wire stage_count_update = stage_write ^ stage_pop;
        always_ff @(posedge clk) begin
            if(!trace_rst_n) stage_count <= '0;
            else if(stage_count_update) stage_count <= stage_count_data;
        end
        // BEGIN TRACE_HOLD_R05_STAGE
        // Preserve synchronous RAM structure; all write word/address bits held.
        wire [207:0] trace_stage_write_raw = {stage_seq[g],timestamp,captured_payload_q[g*128+:128]};
        (* syn_keep=1, syn_dont_touch=1 *) wire [SW-1:0] trace_stage_wr_addr_l0, trace_stage_wr_addr_l1;
        (* syn_keep=1, syn_dont_touch=1 *) wire [SW-1:0] trace_stage_rd_addr_l0, trace_stage_rd_addr_l1;
        (* syn_keep=1, syn_dont_touch=1 *) wire [207:0] trace_stage_data_l0, trace_stage_data_l1;
        for(genvar sa=0;sa<SW;sa=sa+1)begin:g_trace_stage_address_hold
            LUT1 #(.INIT(2'h2)) u_wr_hold_0(.I0(write_pointer[sa]),.F(trace_stage_wr_addr_l0[sa]));
            LUT1 #(.INIT(2'h2)) u_wr_hold_1(.I0(trace_stage_wr_addr_l0[sa]),.F(trace_stage_wr_addr_l1[sa]));
            LUT1 #(.INIT(2'h2)) u_rd_hold_0(.I0(read_pointer[sa]),.F(trace_stage_rd_addr_l0[sa]));
            LUT1 #(.INIT(2'h2)) u_rd_hold_1(.I0(trace_stage_rd_addr_l0[sa]),.F(trace_stage_rd_addr_l1[sa]));
        end
        for(genvar sd=0;sd<208;sd=sd+1)begin:g_trace_stage_data_hold
            LUT1 #(.INIT(2'h2)) u_data_hold_0(.I0(trace_stage_write_raw[sd]),.F(trace_stage_data_l0[sd]));
            LUT1 #(.INIT(2'h2)) u_data_hold_1(.I0(trace_stage_data_l0[sd]),.F(trace_stage_data_l1[sd]));
        end
        // END TRACE_HOLD_R05_STAGE
        always_ff @(posedge clk)begin
            if(trace_rst_n)begin
                if(stage_write)stage_memory[trace_stage_wr_addr_l1]<=trace_stage_data_l1;
                if(stage_pop)stage_read_reg<=stage_memory[trace_stage_rd_addr_l1];
            end
        end
        always_ff @(posedge clk)begin
            if(!trace_rst_n)begin
                stage_seq[g]<=0;drop_count[g]<=0;
                write_pointer<=0;read_pointer<=0;
            end else begin
                if(captured_valid_q[g])begin
                    stage_seq[g]<=stage_seq[g]+32'd1;
                    if(!stage_write && drop_count[g]!=COUNTER_MAX)
                        drop_count[g]<=drop_count[g]+32'd1;
                end
                if(stage_write)write_pointer<=write_pointer+1'b1;
                if(stage_pop)read_pointer<=read_pointer+1'b1;
            end
        end
    end endgenerate

    // Synchronous per-stage read -> registered selection -> shared RAM.
    // During mux busy/read cycles scan holds to preserve round-robin service.
    always_ff @(posedge clk)begin
        if(!trace_rst_n)begin
            scan<=0;mux_valid<=0;timestamp<=0;arb_wait<=0;selected<=0;
        end else begin
            timestamp<=timestamp+48'd1;
            if(!mux_valid && !arb_wait)scan<=scan+3'd1;
            if(push)mux_valid<=0;
            if(grab)begin selected<=scan;arb_wait<=1;end
            if(arb_wait)begin
                mux_data<={5'd0,selected_hold_l1,stage_read_data[selected_hold_l1]};
                mux_valid<=1;arb_wait<=0;
            end
        end
    end
    always_ff @(posedge clk)begin
        if(trace_rst_n)begin
            if(push)memory[trace_wr_addr_l1]<=trace_write_data_l1;
            if(pop)read_data<=memory[trace_rd_addr_l1];
        end
    end
    always_ff @(posedge clk)begin
        if(!trace_rst_n)begin wr_ptr<=0;rd_ptr<=0;count<=0;end
        else begin
            if(push)wr_ptr<=wr_ptr+1'b1;
            if(pop)rd_ptr<=rd_ptr+1'b1;
            case({push,pop})
                2'b10:count<=count+1'b1;
                2'b01:count<=count-1'b1;
                default:begin end
            endcase
        end
    end

    always_ff @(posedge clk)begin
        if(!trace_rst_n)begin report_count<=0;stat_due<=0;end
        else begin
            if(start_stat)stat_due[stat_scan]<=0;
            if(report_tick)begin report_count<=0;stat_due<=8'hff;end
            else report_count<=report_count+32'd1;
        end
    end

    always_ff @(posedge clk)begin
        if(!trace_rst_n)begin
            state<=IDLE;stat_scan<=0;body_shift<=0;byte_index<=0;
            byte_data<=0;crc<=16'hffff;crc_steps<=0;
        end else case(state)
            IDLE:begin
                if(pop)state<=READ_WAIT;
                else if(start_stat)begin
                    body_shift<={128'd0,drop_count[stat_scan],timestamp,
                                 stage_seq[stat_scan],5'b10000,stat_scan,8'd1};
                    byte_index<=0;crc<=16'hffff;state<=PREP;
                    stat_scan<=stat_scan+3'd1;
                end else stat_scan<=stat_scan+3'd1;
            end
            READ_WAIT:begin
                body_shift<={read_data[127:0],drop_count[read_data[210:208]],
                             read_data[175:128],read_data[207:176],
                             read_data[215:208],8'd1};
                byte_index<=0;crc<=16'hffff;state<=PREP;
            end
            PREP:begin
                byte_data<=byte_data_capture;
                state<=SEND;
            end
            SEND:if(byte_ready)begin
                if(byte_index==35)state<=IDLE;
                else begin
                    byte_index<=byte_index+6'd1;
                    if(byte_index>=2 && byte_index<=33)begin
                        crc<=crc^{byte_data,8'd0};crc_steps<=8;
                        body_shift<={8'd0,body_shift[255:8]};state<=CRC_STEP;
                    end else state<=PREP;
                end
            end
            CRC_STEP:begin
                crc<=crc[15] ? (crc<<1)^16'h1021 : crc<<1;
                crc_steps<=crc_steps-1'b1;
                if(crc_steps==1)state<=PREP;
            end
            default:state<=IDLE;
        endcase
    end
    uart_tx #(.CLK_HZ(CLK_HZ),.BAUD(BAUD)) u_tx(
        .clk(clk),.rst_n(trace_rst_n),.tx_data(byte_data),.tx_valid(byte_valid),
        .tx_ready(byte_ready),.tx(tx));
    // synthesis translate_off
    initial begin
        if(FIFO_DEPTH<2 || (FIFO_DEPTH&(FIFO_DEPTH-1))!=0)
            $fatal(1,"FIFO_DEPTH must be power of two >=2");
        if(STAGE_DEPTH<2 || (STAGE_DEPTH&(STAGE_DEPTH-1))!=0)
            $fatal(1,"STAGE_DEPTH must be power of two >=2");
        if(REPORT_CYCLES<1 || CLK_HZ<BAUD*2 || COUNTER_MAX==0)
            $fatal(1,"invalid timing/counter parameters");
    end
    // synthesis translate_on
endmodule
