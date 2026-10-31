// Runtime, bounded-interval anchor; no phase-zero fixture or binary frame CDC.
// 40 MHz core, 25 MHz pixel, H800/V525: 672000 core cycles/frame.
// One unit of the 4032 phase numerator is 500/3 core cycles.
// Frame mailbox delivery is conservatively bounded at 2..8 core cycles;
// 48 additional cycles cover NCO endpoint drift/jitter for <=2^24-1 ticks.
// Valid only if *every* instant in that interval has the same ceiling phase.
module pro_visual_anchor (
    input wire core_clk, rst_n, sample_tick,
    input wire [31:0] global_tick,
    input wire [31:0] frame_snapshot,
    input wire frame_snapshot_valid, frame_snapshot_pulse,
    output reg [31:0] anchor_frame, anchor_tick,
    output reg [11:0] anchor_phase,
    output reg anchor_valid
);
    reg [20:0] age;
    reg seen;
    // Exact running quotient/remainder of 3*age by 500. Updating by three
    // replaces two long combinational constant dividers with a 9-bit sum.
    // If 3*age=500*q+r, r in 0..499, then
    // ceil((3*age-138)/500)=q+(r>138),
    // ceil((3*age+168)/500)=q+1+(r>332).
    // Both bounds are identical iff r is in 139..332, with phase=q+1.
    reg [11:0] phase_quotient;
    reg [8:0] phase_remainder;
    wire [9:0] remainder_step = {1'b0,phase_remainder} + 10'd3;
    always @(posedge core_clk or negedge rst_n) begin
        if (!rst_n) begin
            age <= 0;
            seen <= 0;
            phase_quotient <= 0;
            phase_remainder <= 0;
            anchor_frame <= 0;
            anchor_tick <= 0;
            anchor_phase <= 0;
            anchor_valid <= 0;
        end else begin
            // A one-cycle publication prevents START from latching the previous
            // tick's tuple on the next sample edge before this tuple updates.
            anchor_valid <= 0;
            if (frame_snapshot_valid && frame_snapshot_pulse) begin
                age <= 0;
                seen <= 1;
                phase_quotient <= 0;
                phase_remainder <= 0;
                // Do not mix the previous age with a newly arrived frame.
                anchor_valid <= 0;
            end else if (seen) begin
                if (age < 21'd672256) begin
                    age <= age + 1'b1;
                    if(remainder_step >= 10'd500) begin
                        phase_remainder <= 9'(remainder_step - 10'd500);
                        phase_quotient <= phase_quotient + 1'b1;
                    end else phase_remainder <= remainder_step[8:0];
                end
                else anchor_valid <= 0;
            end
            if (sample_tick && !frame_snapshot_pulse) begin
                anchor_valid <= 0;
                if (seen && frame_snapshot_valid && age >= 21'd48 &&
                    age < 21'd671940 && phase_remainder > 9'd138 &&
                    phase_remainder <= 9'd332 && phase_quotient < 12'd4031 &&
                    global_tick != 32'hffffffff &&
                    frame_snapshot < 32'hffffff80) begin
                    anchor_tick <= global_tick + 1'b1;
                    anchor_frame <= frame_snapshot;
                    anchor_phase <= phase_quotient + 1'b1;
                    anchor_valid <= 1;
                end
            end
        end
    end
endmodule
