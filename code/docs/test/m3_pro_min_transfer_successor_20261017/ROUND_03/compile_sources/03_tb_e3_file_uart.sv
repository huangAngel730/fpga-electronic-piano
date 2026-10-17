// New real-file transport harness. Frozen T057 receiver/UART are read-only.
// 40MHz, synchronous active-low reset; original UART 115200 8N1 pin signaling.
// SESSION_TIMEOUT=50ms is explicitly an isolated parameter coverage test.
`timescale 1ns/1ps
module tb_e3_file_uart;
    logic clk=0, rst_n=0, rx=1, rd_req=0;
    logic [8:0] rd_index=0;
    wire tx, rd_valid, committed_valid, commit_pulse;
    wire [63:0] rd_event;
    wire [9:0] count;
    wire [31:0] score_id;
    wire [7:0] last_error;
    always #12.5 clk=~clk;
    score_transfer_candidate #(.SESSION_TIMEOUT(2000000)) dut(
        .clk(clk), .rst_n(rst_n), .uart_rx_i(rx), .uart_tx_o(tx),
        .rd_req(rd_req), .rd_index(rd_index), .rd_valid(rd_valid), .rd_event(rd_event),
        .committed_valid(committed_valid), .committed_count(count),
        .committed_score_id(score_id), .commit_pulse(commit_pulse), .last_error(last_error));
    localparam real BIT_NS=1000000000.0/115200.0;
    integer fd, plan_fd, current_case=0, packets=0, pulses=0, cases=0;
    longint unsigned cycles=0;
    integer n, size, before_packets, waited, ret, i;
    reg [7:0] value, serial_value;
    string plan_path, capture_path, operation;
    reg [7:0] decoded[0:141];
    integer decoded_pos=0, decoded_size=0, b;
    always @(posedge clk) begin
        cycles=cycles+1;
        if (rst_n && commit_pulse) pulses=pulses+1;
    end
    initial forever begin
        @(negedge tx);
        if (rst_n) begin
            #(BIT_NS*1.5);
            serial_value=0;
            for (b=0;b<8;b=b+1) begin
                if (tx!==0 && tx!==1) $fatal(1,"unknown TX bit");
                serial_value[b]=tx;
                #(BIT_NS);
            end
            if (tx!==1) $fatal(1,"TX stop bit invalid");
            $fwrite(fd,"BYTE OUT %0d %0d %02x\n",current_case,cycles,serial_value);
            decoded[decoded_pos]=serial_value;
            decoded_pos=decoded_pos+1;
            if (decoded_pos==12) decoded_size=14+{decoded[11],decoded[10]};
            if (decoded_pos>141 || decoded_size>142) $fatal(1,"TX frame exceeds bound");
            if (decoded_pos==decoded_size && decoded_size!=0) begin
                $fwrite(fd,"TX %0d ",current_case);
                for (n=0;n<decoded_size;n=n+1) $fwrite(fd,"%02x",decoded[n]);
                $fwrite(fd," %0d\n",cycles);
                packets=packets+1; decoded_pos=0; decoded_size=0;
            end
        end
    end
    task automatic send_byte(input [7:0] data);
        integer k;
        begin
            rx=0; #(BIT_NS);
            for (k=0;k<8;k=k+1) begin rx=data[k]; #(BIT_NS); end
            rx=1; #(BIT_NS/2);
            $fwrite(fd,"BYTE IN %0d %0d %02x\n",current_case,cycles,data);
            #(BIT_NS/2);
        end
    endtask
    task automatic snapshot;
        integer idx;
        begin
            @(negedge clk);
            $fwrite(fd,"META %0d %0d %0d %0d %0d %0d\n",current_case,
                committed_valid,count,score_id,pulses,last_error);
            if (operation=="Q") begin
                for (idx=0; idx<count && committed_valid && idx<512; idx=idx+1) begin
                    rd_index=idx; rd_req=1;
                    @(posedge clk); #1;
                    if (rd_valid!==1 || (^rd_event)===1'bx) $fatal(1,"public read missing/unknown");
                    $fwrite(fd,"EVENT %0d %0d %016x\n",current_case,idx,rd_event);
                    @(negedge clk); rd_req=0;
                end
                if (count<512) begin
                    rd_req=1; rd_index=count;
                    @(posedge clk); #1;
                    if (rd_valid!==0) $fatal(1,"out of range accepted");
                    @(negedge clk); rd_req=0;
                end
            end
        end
    endtask
    initial begin
        if (!$value$plusargs("PLAN=%s",plan_path) || !$value$plusargs("CAPTURE=%s",capture_path))
            $fatal(1,"missing PLAN/CAPTURE");
        fd=$fopen(capture_path,"w"); plan_fd=$fopen(plan_path,"r");
        if (!fd || !plan_fd) $fatal(1,"file missing");
        $fwrite(fd,"START 40000000 115200 800000 2000000\n");
        repeat(10) @(negedge clk); rst_n=1;
        while (!$feof(plan_fd)) begin
            ret=$fscanf(plan_fd,"%s %d %d",operation,current_case,size);
            if (ret!=3) begin
                if (!$feof(plan_fd)) $fatal(1,"malformed plan");
            end else begin
                cases=cases+1; before_packets=packets;
                $fwrite(fd,"CASE %0d %s %0d\n",current_case,operation,cycles);
                if (operation=="S" || operation=="T") begin
                    for (i=0;i<size;i=i+1) begin
                        ret=$fscanf(plan_fd,"%h",value);
                        if (ret!=1) $fatal(1,"missing plan byte");
                        send_byte(value);
                    end
                    waited=0;
                    while (packets==before_packets && waited<3000000) begin
                        @(negedge clk); waited=waited+1;
                    end
                    if (packets!=before_packets+1) $fatal(1,"missing/duplicate response is not negative PASS");
                    #(BIT_NS);
                end else if (operation=="R") begin
                    rst_n=0; repeat(10) @(negedge clk); rst_n=1;
                    pulses=0; decoded_pos=0; decoded_size=0;
                end else if (operation=="W") begin
                    repeat(size) @(negedge clk);
                    if (packets!=before_packets) $fatal(1,"unexpected idle reply");
                end else if (operation=="I") begin
                    repeat(size) @(negedge clk);
                    waited=0;
                    while (packets==before_packets && waited<3000000) begin
                        @(negedge clk); waited=waited+1;
                    end
                    if (packets!=before_packets+1) $fatal(1,"timeout reply missing/duplicate");
                    #(BIT_NS);
                end else if (operation!="Q") $fatal(1,"unknown plan operation");
                snapshot();
            end
        end
        $fwrite(fd,"END %0d %0d %0d\n",cases,packets,cycles);
        $fclose(fd); $fclose(plan_fd);
        $display("E3 HARNESS COMPLETE cases=%0d packets=%0d",cases,packets);
        $finish;
    end
    initial begin #(64'd2000000000); $fatal(1,"global simulation timeout"); end
endmodule
