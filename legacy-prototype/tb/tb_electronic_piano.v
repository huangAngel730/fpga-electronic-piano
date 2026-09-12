`timescale 1ns / 1ps

module tb_electronic_piano;
    localparam integer CLK_FREQ_HZ = 1_000_000;
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    reg [7:0] keys_n = 8'hFF;
    wire audio_out;
    wire [7:0] note_led;

    always #500 clk = ~clk;

    electronic_piano_top #(
        .CLK_FREQ_HZ(CLK_FREQ_HZ), .DEBOUNCE_MS(1)
    ) dut (
        .clk(clk), .rst_n(rst_n), .keys_n(keys_n),
        .audio_out(audio_out), .note_led(note_led)
    );

    initial begin
        $dumpfile("electronic_piano.vcd");
        $dumpvars(0, tb_electronic_piano);
        #5_000 rst_n = 1'b1;
        #2_000 keys_n[0] = 1'b0;
        #20_000_000;
        if (note_led != 8'h01) $error("C4 key was not selected");
        keys_n = 8'hFF;
        #2_000_000 keys_n[5] = 1'b0;
        #10_000_000;
        if (note_led != 8'h20) $error("A4 key was not selected");
        keys_n[7] = 1'b0;
        #10_000_000;
        if (note_led != 8'h80) $error("High-note priority failed");
        keys_n = 8'hFF;
        #2_000_000 $finish;
    end
endmodule
