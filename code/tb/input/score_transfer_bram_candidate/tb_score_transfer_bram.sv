// T057 physical UART harness. No private DUT storage read; decoded TX and
// public synchronous rd_req/rd_event are independent capture evidence.
`timescale 1ns/1ps
module tb_score_transfer_bram;
    logic clk=0, rst_n=0, rx=1;
    wire tx, rd_valid, committed_valid, commit_pulse;
    logic rd_req=0;
    logic [8:0] rd_index=0;
    wire [63:0] rd_event;
    wire [9:0] count;
    wire [31:0] score_id;
    wire [7:0] last_error;
    always #12.5 clk=~clk;
    score_transfer_bram_candidate dut(.clk(clk),.rst_n(rst_n),.uart_rx_i(rx),.uart_tx_o(tx),
        .rd_req(rd_req),.rd_index(rd_index),.rd_valid(rd_valid),.rd_event(rd_event),
        .committed_valid(committed_valid),.committed_count(count),
        .committed_score_id(score_id),.commit_pulse(commit_pulse),.last_error(last_error));
    localparam real BIT_NS=1000000000.0/115200.0;
    integer fd, plan_fd, oracle_fd, current_case=0, packets=0, pulses=0, cases=0;
    longint unsigned system_cycles=0;
    integer n, size, before_packets, cycles, ret, i;
    reg [7:0] value, serial_value;
    string plan_path, capture_path, oracle_path, operation;
    reg [63:0] truth[0:511], next_truth[0:511], wanted;
    integer truth_count=0, next_count=0, oracle_case, oracle_pulses, oracle_sid;
    integer public_checks=0, invalid_checks=0, commit_reads=0, concurrent_checks=0;
    integer copy_reads=0, verify_reads=0, uart_reads=0;
    integer run_index=0, scan_index=0, oracle_ret;
    reg concurrent_read=0, want_valid, commit_read_hold=0;
    // Public oracle uses only PC plan documents and observed publication pulses.
    // No DUT bank/memory/VERIFY state is read to calculate expected data.
    always @(negedge clk) if (concurrent_read) begin
        rd_req=1;
        rd_index=commit_read_hold ? 0 : scan_index[8:0];
        scan_index=(scan_index+1)%512;
    end
    always @(posedge clk) begin
        want_valid=rst_n && rd_req && rd_index<truth_count;
        if (want_valid) wanted=truth[rd_index];
        #1;
        if (rd_valid !== want_valid) $fatal(1,"RAM_PUBLIC_LATENCY_OR_VALID");
        if (want_valid) begin
            if (rd_event !== wanted) $fatal(1,"RAM_PUBLIC_DATA_OR_BANK");
            public_checks=public_checks+1;
            if (concurrent_read) concurrent_checks=concurrent_checks+1;
            // State is coverage only, never a source of expected data.
            if (dut.state==6) copy_reads=copy_reads+1;
            if (dut.state==11) verify_reads=verify_reads+1;
            if (dut.state==13) uart_reads=uart_reads+1;
        end else if (rd_req) invalid_checks=invalid_checks+1;
        if (!rst_n) begin
            truth_count=0;
            if (rd_event !== 0) $fatal(1,"RAM_RESET_MASK");
        end else if (commit_pulse) begin
            if (oracle_pulses!=pulses+1 || next_count==0)
                $fatal(1,"RAM_UNEXPECTED_COMMIT");
            if (want_valid) commit_reads=commit_reads+1;
            truth_count=next_count;
            for (run_index=0;run_index<512;run_index=run_index+1)
                truth[run_index]=next_truth[run_index];
        end
    end
    byte decoded[0:141];
    integer decoded_pos=0, decoded_size=0, b;
    always @(posedge clk) begin
        system_cycles=system_cycles+1;
        if (rst_n && commit_pulse) pulses=pulses+1;
    end

    // TX sampling from real pin transitions, not transmitter shifter/handshake.
    initial forever begin
        @(negedge tx);
        if (rst_n) begin
            #(BIT_NS*1.5);
            serial_value=0;
            for (b=0;b<8;b=b+1) begin
                serial_value[b]=tx;
                #(BIT_NS);
            end
            if (tx!==1) $fatal(1,"TX stop bit invalid");
            decoded[decoded_pos]=serial_value;
            decoded_pos=decoded_pos+1;
            if (decoded_pos==12) decoded_size=14+{decoded[11],decoded[10]};
            if (decoded_pos>141 || decoded_size>142) $fatal(1,"TX frame exceeds bound");
            if (decoded_pos==decoded_size && decoded_size!=0) begin
                $fwrite(fd,"TX %0d ",current_case);
                for (n=0;n<decoded_size;n=n+1) $fwrite(fd,"%02x",decoded[n]);
                $fwrite(fd," %0d\n",system_cycles);
                packets=packets+1; decoded_pos=0; decoded_size=0;
            end
        end
    end

    task automatic send_byte(input [7:0] data);
        integer k;
        begin
            rx=0; #(BIT_NS);
            for (k=0;k<8;k=k+1) begin rx=data[k]; #(BIT_NS); end
            rx=1; #(BIT_NS);
        end
    endtask

    task automatic snapshot;
        integer idx;
        begin
            @(negedge clk);
            $fwrite(fd,"META %0d %0d %0d %0d %0d %0d\n",current_case,
                committed_valid,count,score_id,pulses,last_error);
            for (idx=0;idx<count && committed_valid && operation=="Q";idx=idx+1) begin
                rd_index=idx; rd_req=1;
                @(posedge clk); #1;
                if (rd_valid!==1) $fatal(1,"public read missing");
                $fwrite(fd,"EVENT %0d %0d %016x\n",current_case,idx,rd_event);
                @(negedge clk); rd_req=0;
            end
            // Verify out-of-range never gives a valid event (512 has no invalid
            // 9-bit index, so this check applies when count<512).
            if (count<512) begin
                rd_req=1; rd_index=count;
                @(posedge clk); #1;
                if (rd_valid!==0) $fatal(1,"invalid public read accepted");
                @(negedge clk); rd_req=0;
            end
        end
    endtask

    initial begin
        if (!$value$plusargs("PLAN=%s",plan_path) || !$value$plusargs("CAPTURE=%s",capture_path) ||
            !$value$plusargs("ORACLE=%s",oracle_path))
            $fatal(1,"missing PLAN/CAPTURE");
        fd=$fopen(capture_path,"w"); plan_fd=$fopen(plan_path,"r"); oracle_fd=$fopen(oracle_path,"r");
        if (!fd || !plan_fd || !oracle_fd) $fatal(1,"file missing");
        $fwrite(fd,"START 40000000 115200\n");
        repeat(10) @(negedge clk); rst_n=1;
        while (!$feof(plan_fd)) begin
            ret=$fscanf(plan_fd,"%s %d %d",operation,current_case,size);
            if (ret!=3) begin
                if (!$feof(plan_fd)) $fatal(1,"malformed plan");
            end else begin
                oracle_ret=$fscanf(oracle_fd,"%d %d %d %d",oracle_case,next_count,oracle_pulses,oracle_sid);
                if (oracle_ret!=4 || oracle_case!=current_case) $fatal(1,"oracle case identity");
                for (i=0;i<next_count;i=i+1) begin
                    oracle_ret=$fscanf(oracle_fd,"%h",next_truth[i]);
                    if (oracle_ret!=1) $fatal(1,"oracle event missing");
                end
                cases=cases+1; before_packets=packets; commit_read_hold=0;
                $fwrite(fd,"CASE %0d %s %0d\n",current_case,operation,system_cycles);
                if (operation=="S" || operation=="T") begin
                    concurrent_read=1;
                    $fwrite(fd,"RX %0d ",current_case);
                    for (i=0;i<size;i=i+1) begin
                        ret=$fscanf(plan_fd,"%h",value);
                        if (ret!=1) $fatal(1,"missing plan byte");
                        if (i==3 && value==3) commit_read_hold=1;
                        $fwrite(fd,"%02x",value); send_byte(value);
                    end
                    $fwrite(fd,"\n");
                    concurrent_read=1;
                    cycles=0;
                    while (packets==before_packets && cycles<2000000) begin
                        @(negedge clk); cycles=cycles+1;
                    end
                    if (packets==before_packets) $fatal(1,"response timeout, never a negative PASS");
                    #(BIT_NS);
                end else if (operation=="R") begin
                    rst_n=0; repeat(10) @(negedge clk); rst_n=1;
                    pulses=0; decoded_pos=0; decoded_size=0;
                end else if (operation=="W") begin
                    repeat(size) @(negedge clk);
                    if (packets!=before_packets) $fatal(1,"unexpected reply during idle");
                end else if (operation=="I") begin
                    repeat(size) @(negedge clk);
                    cycles=0;
                    while (packets==before_packets && cycles<2000000) begin
                        @(negedge clk); cycles=cycles+1;
                    end
                    if (packets!=before_packets+1) $fatal(1,"missing/duplicate session timeout reply");
                    #(BIT_NS);
                end else if (operation!="Q") $fatal(1,"unknown plan operation");
                @(negedge clk); concurrent_read=0; rd_req=0;
                snapshot();
            end
        end
        $fwrite(fd,"END %0d %0d\n",cases,packets);
        $display("RAM_CHECKS public=%0d concurrent=%0d commit_old=%0d invalid=%0d copy=%0d verify=%0d uart=%0d",
            public_checks,concurrent_checks,commit_reads,invalid_checks,copy_reads,verify_reads,uart_reads);
        if (public_checks<1000 || concurrent_checks<1000 || commit_reads<2 || invalid_checks==0 ||
            copy_reads==0 || verify_reads==0 || uart_reads==0)
            $fatal(1,"RAM_COVERAGE_MISSING");
        $fclose(fd); $fclose(plan_fd); $fclose(oracle_fd);
        $display("HARNESS COMPLETE cases=%0d packets=%0d (checker decides PASS)",cases,packets);
        $finish;
    end
    initial begin #(64'd12000000000); $fatal(1,"global simulation timeout"); end
endmodule
