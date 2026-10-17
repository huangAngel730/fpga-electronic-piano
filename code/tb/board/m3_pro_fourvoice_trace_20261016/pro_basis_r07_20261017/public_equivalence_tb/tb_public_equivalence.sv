`timescale 1ns/1ps
// Source only: no HDL execution authorized. Both instances see identical inputs.
module tb_public_equivalence;
    reg sys_clk_50m=0, reference_40m=0;
    always #10 sys_clk_50m=~sys_clk_50m;
    always #12.5 reference_40m=~reference_40m;
    wire rst_n,midi_rx,unused_ready;
    wire [12:0] original_pins,observer_pins;
    integer fd,event_fd=0,cycle=0,stop_cycle=12000000,start_compare=1200;
    real event_time_ps;
    string bytes_path,reset_path,ready_path,trace_path,event_path;
    // R6-2 defaults use the frozen BYTE_PLAN/RESET_PLAN/READY_PLAN filenames.
    // They must be staged byte-identically in the execution cwd by assembly.py.
    midi_public_port_driver #(.EVENT_LOG("driver_events.log")) driver (
        .clk(reference_40m),.sys_rst_n(rst_n),.midi_rx(midi_rx),
        .event_ready(unused_ready),.event_valid(1'b0),.event_data(64'b0));
    m2_138k_pro_fourvoice_candidate_top original (
        .sys_clk_50m(sys_clk_50m),.sys_rst_n(rst_n),.key_n(2'b11),.midi_rx(midi_rx),
        .i2s_bclk(original_pins[0]),.i2s_lrck(original_pins[1]),.i2s_din(original_pins[2]),
        .pa_en(original_pins[3]),.uart_tx(original_pins[4]),
        .tmds_clk_p(original_pins[5]),.tmds_clk_n(original_pins[6]),
        .tmds_data_p(original_pins[9:7]),.tmds_data_n(original_pins[12:10]));
    m2_138k_pro_fourvoice_observer_top_r06 observer (
        .sys_clk_50m(sys_clk_50m),.sys_rst_n(rst_n),.key_n(2'b11),.midi_rx(midi_rx),
        .i2s_bclk(observer_pins[0]),.i2s_lrck(observer_pins[1]),.i2s_din(observer_pins[2]),
        .pa_en(observer_pins[3]),.uart_tx(observer_pins[4]),
        .tmds_clk_p(observer_pins[5]),.tmds_clk_n(observer_pins[6]),
        .tmds_data_p(observer_pins[9:7]),.tmds_data_n(observer_pins[12:10]));
    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"TRACE_REQUIRED");
        if(!$value$plusargs("EVENTS=%s",event_path)) $fatal(1,"EVENTS_REQUIRED");
        fd=$fopen(trace_path,"w");
        event_fd=$fopen(event_path,"w");
        if(!fd || !event_fd) $fatal(1,"TRACE_OPEN");
        $fwrite(fd,"cycle,time_ps,rst_n,midi_rx,key_n,original,observer\n");
        $fwrite(event_fd,"time_ps,original,observer\n");
    end
    // Postponed-region snapshots coalesce changes at the SAME simulation time.
    // No #delay: stable differences between 40MHz samples remain observable.
    always @(original_pins or observer_pins) begin
        event_time_ps=$realtime*1000.0;
        if(event_fd) $fstrobe(event_fd,"%0.0f,%013b,%013b",event_time_ps,original_pins,observer_pins);
    end
    always @(posedge reference_40m) begin
        cycle=cycle+1;
        if(cycle==start_compare) begin
            event_time_ps=$realtime*1000.0;
            $fstrobe(event_fd,"%0.0f,%013b,%013b",event_time_ps,original_pins,observer_pins);
        end
        $fwrite(fd,"%0d,%0.0f,%b,%b,11,%013b,%013b\n",cycle,$realtime*1000.0,rst_n,midi_rx,original_pins,observer_pins);
        if(cycle>=start_compare) begin
            if((^original_pins)===1'bx || (^observer_pins)===1'bx)
                $fatal(1,"FIRST_DIFF UNKNOWN_PUBLIC_OUTPUT cycle=%0d",cycle);
            if(original_pins!==observer_pins)
                $fatal(1,"FIRST_DIFF PUBLIC_OUTPUT cycle=%0d old=%b new=%b",cycle,original_pins,observer_pins);
        end
        if(cycle==stop_cycle) begin
            // Let final-edge NBA and postponed writes finish, then close.
            #0.001;
            $fflush(fd);$fclose(fd);
            $fflush(event_fd);$fclose(event_fd);event_fd=0;
            $display("EQUIV_EVENTS_END stop_ps=%0.0f",12500.0+(stop_cycle-1)*25000.0);
            $display("EQUIV_END cycle=%0d",cycle);
            $finish;
        end
    end
    // No hierarchical references: original obs_* are deliberately NOT_PUBLIC.
endmodule
