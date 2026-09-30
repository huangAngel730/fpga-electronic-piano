// Decode physical PT8211 channels at BCK rising edges; same WS contract as V1.7.
`timescale 1ns/1ps
module tb_t005_channel_probe;
    parameter ACTIVE_LEFT=1;
    logic sys_clk=0;always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
    t005_channel_probe dut(.sys_clk,.sys_rst_n,.key_n(2'b11),.midi_rx(1'b1),
                          .i2s_bclk,.i2s_lrck,.i2s_din,.pa_en,.uart_tx);
    logic seen=0,ws=0;
    logic [31:0] bits=0;
    integer count=0,halves=0,checks=0,peak=0,value,previous=0,crossings=0;
    always @(posedge i2s_bclk) if(sys_rst_n) begin
        if(!seen) begin seen=1;ws=i2s_lrck;end
        if(i2s_lrck!==ws) begin
            if(halves>=8) begin
                if(count!=32)$fatal(1,"WS interval %0d",count);
                value=$signed(bits[15:0]);
                if(ws==ACTIVE_LEFT) begin
                    if(value>peak)peak=value;
                    if(previous<0 && value>=0)crossings++;
                    previous=value;
                end else if(value!=0)$fatal(1,"Silent channel emitted %0d",value);
                checks++;
            end
            halves++;count=0;bits=0;ws=i2s_lrck;
        end
        bits={bits[30:0],i2s_din};count++;
        if(halves==1032) begin
            if(checks!=1024 || peak<8100 || peak>8193 || crossings<4 || crossings>5)
                $fatal(1,"Waveform checks=%0d peak=%0d crossings=%0d",checks,peak,crossings);
            $display("PASS T005 channel probe left=%0d physical_halves=%0d peak=%0d positive_crossings=%0d",ACTIVE_LEFT,checks,peak,crossings);
            $finish;
        end
    end
    initial begin
        #100;if(pa_en!==1)$fatal(1,"Amplifier enabled during reset");
        #100;sys_rst_n=1;
        #1000;if(pa_en!==0)$fatal(1,"Amplifier did not enable");
        #20_000_000;$fatal(1,"Timeout");
    end
endmodule