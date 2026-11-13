// Tagged N-slot ownership scheduler. Opaque descriptor, NOT persistent DSP state.
// Identity = {source4, channel4, generation32}; tag = {request32, identity40, slotSW}.
// rst_n is a WHOLE old-work-domain reset. soft_reset cannot reset external work
// and therefore cannot bypass a drain fence or its latched timeout.
module m2_polyphony_scheduler #(
    parameter integer N = 4,
    parameter integer CW = 75,
    parameter integer SW = $clog2(N),
    parameter integer TW = 72+SW,
    parameter integer DRAIN_LIMIT = N+12,
    parameter integer FRAME_LIMIT = 833
) (
    input wire clk, rst_n, cancel, soft_reset,
    input wire cfg_valid,
    output wire cfg_ready,
    input wire [SW-1:0] cfg_slot,
    input wire [39:0] cfg_identity,
    input wire [1:0] cfg_flags,
    input wire [CW-1:0] cfg_context,
    input wire ctl_valid,
    output wire ctl_ready,
    input wire [7:0] ctl_identity,
    input wire [28:0] ctl_value,
    input wire ctl_pedal,
    input wire begin_valid,
    output wire begin_ready,
    input wire [31:0] begin_request,
    output wire req_valid,
    input wire req_ready,
    output reg [TW-1:0] req_tag,
    output reg [CW-1:0] req_context,
    output reg [1:0] req_flags,
    output reg [28:0] req_control,
    output reg req_pedal,
    input wire res_valid,
    output wire res_ready,
    input wire [TW-1:0] res_tag,
    input wire [CW-1:0] res_context,
    output wire res_accepted,
    output wire commit_valid,
    input wire commit_ready,
    output wire [31:0] commit_request,
    output reg deadline_missed,
    input wire rom_empty, engine_empty, result_empty,
    output wire busy, draining, drain_fault,
    input wire read_valid,
    output wire read_ready,
    input wire [SW-1:0] read_slot,
    output wire read_out_valid,
    output wire [CW-1:0] read_context
);
    localparam IDLE=0, READ=1, CAPTURE=2, OFFER=3, WAIT_RESULTS=4,
               HOLD=5, DRAIN=6, FAULT=7;
    reg [2:0] state;
    reg [SW-1:0] slot;
    reg [31:0] request_id;
    reg [N-1:0] issued, completed;
    reg [TW-1:0] issued_tags [0:N-1];
    reg [31:0] drain_cycles, frame_cycles;
    wire allowed = rst_n && !cancel && !soft_reset;
    wire active = state==READ || state==CAPTURE || state==OFFER || state==WAIT_RESULTS;
    wire initialized, bank_rd_valid;
    wire [39:0] bank_identity;
    wire [1:0] bank_flags;
    wire [CW-1:0] bank_context;
    wire [28:0] bank_control;
    wire bank_pedal;
    wire [SW-1:0] result_slot = res_tag[SW-1:0];
    wire result_tag_equal = res_tag == issued_tags[result_slot];
    wire tag_match = result_tag_equal;
    assign busy = state != IDLE;
    assign draining = state==DRAIN || state==FAULT;
    assign drain_fault = state==FAULT;
    // Control > configuration > frame > readback. No simultaneous bank read/write
    // of live state is allowed, so read-during-write semantics are not assumed.
    assign ctl_ready = state==IDLE && allowed;
    assign cfg_ready = state==IDLE && allowed && !ctl_valid;
    assign begin_ready = state==IDLE && allowed && initialized && !ctl_valid && !cfg_valid;
    assign read_ready = state==IDLE && allowed && !ctl_valid && !cfg_valid && !begin_valid;
    assign req_valid = state==OFFER && allowed;
    assign res_ready = rst_n;
    assign res_accepted = allowed && active && res_valid && issued[result_slot] &&
                          !completed[result_slot] && tag_match;
    assign commit_valid = state==HOLD && allowed;
    assign commit_request = request_id;
    assign read_out_valid = bank_rd_valid && state==IDLE;
    assign read_context = bank_context;
    wire publish = commit_valid && commit_ready;
    m2_polyphony_statebank #(.N(N), .CW(CW), .SW(SW)) bank (
        .clk(clk), .rst_n(rst_n), .clear(soft_reset),
        .cfg_we(cfg_valid && cfg_ready), .cfg_slot(cfg_slot), .cfg_identity(cfg_identity),
        .cfg_flags(cfg_flags), .cfg_context(cfg_context),
        .ctl_we(ctl_valid && ctl_ready), .ctl_identity(ctl_identity), .ctl_value(ctl_value),
        .ctl_pedal(ctl_pedal), .initialized(initialized),
        .rd_en((state==READ && allowed) || (read_valid && read_ready)),
        .rd_slot(state==IDLE ? read_slot : slot), .rd_valid(bank_rd_valid),
        .rd_identity(bank_identity), .rd_flags(bank_flags), .rd_context(bank_context),
        .rd_control(bank_control), .rd_pedal(bank_pedal),
        .result_we(res_accepted), .result_slot(result_slot), .result_context(res_context),
        .publish(publish)
    );
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            slot <= 0;
            request_id <= 0;
            issued <= 0;
            completed <= 0;
            drain_cycles <= 0;
            frame_cycles <= 0;
            deadline_missed <= 0;
            req_tag <= 0;
            req_context <= 0;
            req_flags <= 0;
            req_control <= 0;
            req_pedal <= 0;
        end else begin
            if (active || state==HOLD) begin
                if (frame_cycles < FRAME_LIMIT) frame_cycles <= frame_cycles + 1;
                if (frame_cycles == FRAME_LIMIT-1) deadline_missed <= 1;
            end
            // Drain progresses despite repeated cancel/local reset. Timeout is
            // fail-closed until the entire old-work domain is physically reset.
            if (state==FAULT) begin
                state <= FAULT;
            end else if (state==DRAIN) begin
                if (rom_empty && engine_empty && result_empty) begin
                    state <= IDLE;
                    drain_cycles <= 0;
                end else if (drain_cycles == DRAIN_LIMIT-1) begin
                    state <= FAULT;
                end else drain_cycles <= drain_cycles + 1;
            end else if (cancel || soft_reset) begin
                state <= (|issued) ? DRAIN : IDLE;
                issued <= 0;
                completed <= 0;
                drain_cycles <= 0;
            end else begin
                if (res_accepted) completed[result_slot] <= 1;
                case (state)
                    IDLE: if (begin_valid && begin_ready) begin
                        request_id <= begin_request;
                        issued <= 0;
                        completed <= 0;
                        slot <= 0;
                        frame_cycles <= 0;
                        deadline_missed <= 0;
                        state <= READ;
                    end
                    READ: state <= CAPTURE;
                    CAPTURE: if (bank_rd_valid) begin
                        req_tag <= {request_id, bank_identity, slot};
                        req_context <= bank_context;
                        req_flags <= bank_flags;
                        req_control <= bank_control;
                        req_pedal <= bank_pedal;
                        state <= OFFER;
                    end
                    OFFER: if (req_ready) begin
                        issued[slot] <= 1;
                        issued_tags[slot] <= req_tag;
                        if (slot==N-1) state <= WAIT_RESULTS;
                        else begin slot <= slot+1'b1; state <= READ; end
                    end
                    WAIT_RESULTS: begin
                        if (&completed && &issued) state <= HOLD;
                    end
                    HOLD: if (publish) begin
                        state <= DRAIN;
                        issued <= 0;
                        completed <= 0;
                        drain_cycles <= 0;
                    end
                    default: state <= FAULT;
                endcase
            end
        end
    end
endmodule
