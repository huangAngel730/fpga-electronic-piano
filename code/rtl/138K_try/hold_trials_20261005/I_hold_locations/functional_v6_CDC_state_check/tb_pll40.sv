`timescale 1ns/1ps
module tb_pll40;
    reg ref_clk=0;
    always #10 ref_clk=~ref_clk;
    wire lock,serial_clk,pixel_clk,core_clk;
    TMDS_PLL dut(.clkin(ref_clk),.lock(lock),.clkout0(serial_clk),.clkout1(pixel_clk),.clkout2(core_clk));
    realtime a,b;
    integer serial_edges=0,pixel_edges=0,core_edges=0;
    always @(posedge serial_clk) if(lock)serial_edges++;
    always @(posedge pixel_clk) if(lock)pixel_edges++;
    always @(posedge core_clk) if(lock)core_edges++;
    initial begin
        wait(lock===1'b1);
        repeat(4)@(posedge core_clk);
        a=$realtime;@(posedge core_clk);b=$realtime;
        if(b-a<24.999 || b-a>25.001)$fatal(1,"core clock period mismatch %f",b-a);
        @(posedge pixel_clk);a=$realtime;@(posedge pixel_clk);b=$realtime;
        if(b-a<39.999 || b-a>40.001)$fatal(1,"pixel period changed %f",b-a);
        @(posedge serial_clk);a=$realtime;@(posedge serial_clk);b=$realtime;
        if(b-a<7.999 || b-a>8.001)$fatal(1,"serial period changed %f",b-a);
        #10000;
        if(core_edges<400 || pixel_edges<250 || serial_edges<1250)$fatal(1,"empty PLL clock evidence");
        $display("PASS vendor PLL model: real ref50 core40 pixel25 serial125 MHz edges=%0d/%0d/%0d",core_edges,pixel_edges,serial_edges);
        $finish;
    end
    initial begin #100000;$fatal(1,"PLL lock/clock timeout");end
endmodule
