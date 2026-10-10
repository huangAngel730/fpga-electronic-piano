// Interrupt real UART transactions at RAM lifecycle boundaries, then recover.
`timescale 1ns/1ps
module tb_score_bram_reset;
    reg clk=0, rst_n=0, rx=1, rd_req=1;
    reg [8:0] rd_index=0;
    wire tx, rd_valid, committed_valid, commit_pulse;
    wire [63:0] rd_event;
    wire [9:0] committed_count;
    wire [31:0] committed_score_id;
    wire [7:0] last_error;
    always #12.5 clk=~clk;
    score_transfer_bram_candidate dut(.*,.uart_rx_i(rx),.uart_tx_o(tx));
    localparam real BIT_NS=1000000000.0/115200.0;
    string path;
    integer fd, n, k, ret, length, phase, before_packets, packets=0, b, byte_pos=0, frame_size=0;
    integer armed=0, hit=0, reset_checks=0;
    reg [7:0] value, serial;
    byte reply[0:141];
    reg [63:0] golden[0:1];

    initial forever begin
        @(negedge tx);
        if (rst_n) begin
            #(BIT_NS*1.5); serial=0;
            for (b=0;b<8;b=b+1) begin serial[b]=tx; #(BIT_NS); end
            if (tx!==1) $fatal(1,"RESET_PROBE_UART_STOP");
            reply[byte_pos]=serial; byte_pos=byte_pos+1;
            if (byte_pos==12) frame_size=14+{reply[11],reply[10]};
            if (byte_pos==frame_size && frame_size>0) begin
                if (reply[3]!==8'h80 || reply[13]!==0) $fatal(1,"RESET_RECOVERY_NOT_ACK");
                packets=packets+1; byte_pos=0; frame_size=0;
            end
        end
    end
    task automatic send_byte(input [7:0] data);
        integer bit_index;
        begin
            rx=0; #(BIT_NS);
            for (bit_index=0;bit_index<8;bit_index=bit_index+1) begin rx=data[bit_index]; #(BIT_NS); end
            rx=1; #(BIT_NS);
        end
    endtask
    task automatic transaction(input integer expect_response);
        integer index, tries, start_packets;
        reg [7:0] data;
        begin
            ret=$fscanf(fd,"%d",length);
            if (ret!=1) $fatal(1,"RESET_PROBE_PLAN_LENGTH");
            start_packets=packets;
            for (index=0;index<length;index=index+1) begin
                ret=$fscanf(fd,"%h",data);
                if (ret!=1) $fatal(1,"RESET_PROBE_PLAN_BYTE");
                send_byte(data);
            end
            if (expect_response) begin
                tries=0;
                while (packets==start_packets && tries<500000) begin
                    @(negedge clk); tries=tries+1;
                end
                if (packets!=start_packets+1) $fatal(1,"RESET_PROBE_RESPONSE_TIMEOUT");
                #(BIT_NS);
            end else begin
                repeat(1000) @(negedge clk);
                if (packets!=start_packets || hit!=1) $fatal(1,"RESET_PROBE_NOT_HIT");
            end
        end
    endtask
    // Private state is used only to target reset placement, never as Golden.
    initial forever begin
        @(negedge clk);
        if (armed && ((phase==0 && dut.state==6 && dut.command==2) ||
                      (phase==1 && dut.state==11) ||
                      (phase==2 && dut.state==12) ||
                      (phase==3 && dut.state==7 && dut.verify_pos==dut.total_bytes) ||
                      (phase==4 && dut.state==14) ||
                      (phase==5 && dut.state==15) ||
                      (phase==6 && dut.state==17) ||
                      (phase==7 && dut.state==3 && dut.body_compare_pending))) begin
            armed=0; hit=1; rst_n=0;
            repeat(3) begin
                @(posedge clk); #1;
                if (committed_valid!==0 || committed_count!==0 || rd_valid!==0 ||
                    rd_event!==0 || commit_pulse!==0) $fatal(1,"RESET_RAM_VALID_LEAK");
                reset_checks=reset_checks+1;
            end
            @(negedge clk); rst_n=1; byte_pos=0; frame_size=0;
        end
    end
    task automatic verify_recovery;
        integer index;
        begin
            if (!committed_valid || committed_count!=2 || committed_score_id!=70)
                $fatal(1,"RESET_RECOVERY_META");
            for (index=0;index<2;index=index+1) begin
                @(negedge clk); rd_index=index;
                @(posedge clk); #1;
                if (rd_valid!==1 || rd_event!==golden[index]) $fatal(1,"RESET_RECOVERY_PUBLIC");
            end
        end
    endtask
    initial begin
        if (!$value$plusargs("PLAN=%s",path)) $fatal(1,"RESET_PROBE_MISSING_PLAN");
        fd=$fopen(path,"r"); if (!fd) $fatal(1,"RESET_PROBE_OPEN");
        ret=$fscanf(fd,"%h %h",golden[0],golden[1]);
        if (ret!=2) $fatal(1,"RESET_PROBE_GOLDEN");
        repeat(10) @(negedge clk); rst_n=1;
        for (phase=0;phase<8;phase=phase+1) begin
            // Publish two events so interruption must also invalidate old data.
            transaction(1); transaction(1); transaction(1); verify_recovery();
            transaction(1); // new BEGIN
            if (phase==0 || phase==6 || phase==7) begin armed=1; hit=0; transaction(0); end
            else if (phase==2 || phase==4 || phase==5) begin armed=1; hit=0; transaction(0); end
            else begin
                transaction(1); transaction(1);
                armed=1; hit=0; transaction(0);
            end
            if (committed_valid || rd_valid) $fatal(1,"RESET_POST_STALE_VALID");
            transaction(1); transaction(1); transaction(1); verify_recovery();
            $display("RESET_BOUNDARY_PASS phase=%0d",phase);
        end
        if (reset_checks!=24) $fatal(1,"RESET_PROBE_COVERAGE");
        $display("RESET_RECOVERY_COMPLETE checks=%0d",reset_checks); $finish;
    end
    initial begin #(64'd1000000000); $fatal(1,"RESET_PROBE_GLOBAL_TIMEOUT"); end
endmodule
