// Independent B1 opaque-context bank, NOT a sound engine.
// Single clk; rst_n asynchronously asserts. clear is a LOCAL synchronous reset.
// Each physical context bank has at most one read and one write per clock.
// Results write the inactive bank; only publish swaps ownership atomically.
module m2_polyphony_statebank #(
    parameter integer N = 4,
    parameter integer CW = 75,
    parameter integer SW = $clog2(N)
) (
    input wire clk, rst_n, clear,
    input wire cfg_we,
    input wire [SW-1:0] cfg_slot,
    input wire [39:0] cfg_identity,
    input wire [1:0] cfg_flags,
    input wire [CW-1:0] cfg_context,
    input wire ctl_we,
    input wire [7:0] ctl_identity,
    input wire [28:0] ctl_value,
    input wire ctl_pedal,
    output wire initialized,
    input wire rd_en,
    input wire [SW-1:0] rd_slot,
    output reg rd_valid,
    output reg [39:0] rd_identity,
    output reg [1:0] rd_flags,
    output reg [CW-1:0] rd_context,
    output reg [28:0] rd_control,
    output reg rd_pedal,
    input wire result_we,
    input wire [SW-1:0] result_slot,
    input wire [CW-1:0] result_context,
    input wire publish
);
    reg [CW-1:0] context_a [0:N-1];
    reg [CW-1:0] context_b [0:N-1];
    reg [39:0] identities [0:N-1];
    reg [1:0] flags [0:N-1];
    reg [28:0] controls [0:255];
    reg [255:0] controls_valid, pedals;
    reg [N-1:0] configured;
    reg live_bank;
    assign initialized = &configured;
    // Invalid entries read zero. RAM payloads themselves need no reset loop.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            configured <= 0;
            controls_valid <= 0;
            pedals <= 0;
            live_bank <= 0;
            rd_valid <= 0;
            rd_identity <= 0;
            rd_flags <= 0;
            rd_context <= 0;
            rd_control <= 0;
            rd_pedal <= 0;
        end else if (clear) begin
            configured <= 0;
            controls_valid <= 0;
            pedals <= 0;
            live_bank <= 0;
            rd_valid <= 0;
            rd_identity <= 0;
            rd_flags <= 0;
            rd_context <= 0;
            rd_control <= 0;
            rd_pedal <= 0;
        end else begin
            rd_valid <= rd_en;
            if (cfg_we) begin
                configured[cfg_slot] <= 1;
                identities[cfg_slot] <= cfg_identity;
                flags[cfg_slot] <= cfg_flags;
                if (live_bank) context_b[cfg_slot] <= cfg_context;
                else context_a[cfg_slot] <= cfg_context;
            end
            if (ctl_we) begin
                controls[ctl_identity] <= ctl_value;
                controls_valid[ctl_identity] <= 1;
                pedals[ctl_identity] <= ctl_pedal;
            end
            if (rd_en) begin
                rd_identity <= configured[rd_slot] ? identities[rd_slot] : 40'b0;
                rd_flags <= configured[rd_slot] ? flags[rd_slot] : 2'b0;
                rd_context <= !configured[rd_slot] ? {CW{1'b0}} :
                              (live_bank ? context_b[rd_slot] : context_a[rd_slot]);
                rd_control <= (configured[rd_slot] && controls_valid[identities[rd_slot][39:32]]) ?
                              controls[identities[rd_slot][39:32]] : 29'b0;
                rd_pedal <= configured[rd_slot] && pedals[identities[rd_slot][39:32]];
            end
            if (result_we) begin
                if (live_bank) context_a[result_slot] <= result_context;
                else context_b[result_slot] <= result_context;
            end
            if (publish) live_bank <= !live_bank;
        end
    end
endmodule
