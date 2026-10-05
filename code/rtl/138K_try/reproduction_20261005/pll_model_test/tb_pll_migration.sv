`timescale 1ns/1ps
module tb_pll_migration;
  reg clk = 1'b0;
  always #10 clk = ~clk;
  wire locked, serial_clk, pixel_clk;
  TMDS_PLL dut (.lock(locked), .clkout0(serial_clk), .clkout1(pixel_clk), .clkin(clk));
  integer serial_checks = 0;
  integer pixel_checks = 0;
  integer phase_checks = 0;
  real previous_serial, previous_pixel, last_serial;
  real delta;
  reg checking = 1'b0;
  initial begin
    #100000;
    $fatal(1, "PLL vendor-model timeout/no lock");
  end
  always @(posedge serial_clk) last_serial = $realtime;
  initial begin
    wait (locked === 1'b1);
    repeat (4) @(posedge pixel_clk);
    checking = 1'b1;
    fork
      begin
        @(posedge serial_clk);
        previous_serial = $realtime;
        repeat (500) begin
          @(posedge serial_clk);
          delta = $realtime - previous_serial;
          if (delta < 7.995 || delta > 8.005)
            $fatal(1, "125 MHz serial period mismatch: %f", delta);
          if (locked !== 1'b1) $fatal(1, "Unexpected lock loss");
          previous_serial = $realtime;
          serial_checks = serial_checks + 1;
        end
      end
      begin
        @(posedge pixel_clk);
        previous_pixel = $realtime;
        repeat (100) begin
          @(posedge pixel_clk);
          if (($realtime - previous_pixel) < 39.995 || ($realtime - previous_pixel) > 40.005)
            $fatal(1, "25 MHz pixel period mismatch: %f", $realtime - previous_pixel);
          previous_pixel = $realtime;
          pixel_checks = pixel_checks + 1;
          #0.001;
          if (($realtime - last_serial) > 0.005)
            $fatal(1, "Pixel/serial zero-phase relationship mismatch");
          phase_checks = phase_checks + 1;
        end
      end
    join
    $display("PASS PLL migration vendor model: serial=%0d pixel=%0d phase=%0d; NOT silicon-lock proof", serial_checks, pixel_checks, phase_checks);
    $finish;
  end
endmodule
