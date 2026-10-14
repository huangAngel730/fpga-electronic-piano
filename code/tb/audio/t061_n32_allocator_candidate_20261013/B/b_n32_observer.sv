`timescale 1ns/1ps
module b_n32_observer (
    input wire clk, rst_n, cancel, aborted,
    input wire result_valid, result_ready, publish,
    input wire [31:0] result_id,
    input wire signed [23:0] left, right,
    input wire late, clipped
);
    integer cycle=0;
    logic held=0;
    logic [81:0] held_payload;
    wire [81:0] payload={result_id,left,right,late,clipped};

    always @(posedge clk) begin
        cycle=cycle+1;
        if(!rst_n) begin
            held=0;
        end else begin
            if(held && !cancel && !aborted &&
               (!result_valid || payload!==held_payload))
                $fatal(1,"N32_B_CLIPPED_HOLD_CHANGED");
            if((result_valid || publish) && !cancel && !aborted)
                $display("K %0d %0d %0d %0d %h %0d %0d %0d %0d",
                    cycle,result_valid,result_ready,publish,result_id,left,right,late,clipped);
            held=result_valid && !result_ready && !cancel && !aborted;
            held_payload=payload;
        end
    end
endmodule
