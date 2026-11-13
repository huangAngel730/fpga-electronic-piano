`timescale 1ns/1ps
module k4_spectrum_reset_sync (
    input wire clk,async_rst_n,
    output wire reset_done
);
    (* async_reg="true" *) reg [1:0] release_pipe;
    always @(posedge clk or negedge async_rst_n) begin
        if(!async_rst_n) release_pipe<=0;
        else release_pipe<={release_pipe[0],1'b1};
    end
    assign reset_done=release_pipe[1];
endmodule
