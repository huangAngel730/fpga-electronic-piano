`timescale 1ns/1ps
// C9 paired-lane static successor. Compile each lane in an isolated universe.
// External pins only; public C9 wire connections. No private hierarchy.
module tb_c9_original;
    reg sys_clk_50m=0,reference_40m=0;
    always #10 sys_clk_50m=~sys_clk_50m;
    always #12.5 reference_40m=~reference_40m;
    wire rst_n,midi_rx,unused_ready;
    wire [12:0] pins;
    integer fd,event_fd=0,companion_fd=0,cycle=0;
    integer start_compare=1200,stop_cycle=12000000;
    real event_time_ps,finish_time_ps;
    string trace_path,event_path,companions_path;

    midi_public_port_driver #(.EVENT_LOG("driver_events.log")) driver(
        .clk(reference_40m),.sys_rst_n(rst_n),.midi_rx(midi_rx),
        .event_ready(unused_ready),.event_valid(1'b0),.event_data(64'b0));
    m2_138k_pro_fourvoice_candidate_top dut(
        .sys_clk_50m(sys_clk_50m),
        .sys_rst_n(rst_n),
        .key_n(2'b11),
        .midi_rx(midi_rx),
        .i2s_bclk(pins[0]),
        .i2s_lrck(pins[1]),
        .i2s_din(pins[2]),
        .pa_en(pins[3]),
        .uart_tx(pins[4]),
        .tmds_clk_p(pins[5]),
        .tmds_clk_n(pins[6]),
        .tmds_data_p(pins[9:7]),
        .tmds_data_n(pins[12:10])
    );
    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"TRACE_REQUIRED");
        if(!$value$plusargs("EVENTS=%s",event_path)) $fatal(1,"EVENTS_REQUIRED");
        fd=$fopen(trace_path,"w");event_fd=$fopen(event_path,"w");
        if(!fd || !event_fd) $fatal(1,"CAPTURE_OPEN");
        $fwrite(fd,"cycle,time_ps,rst_n,midi_rx,key_n,pins\n");
        $fwrite(event_fd,"time_ps,pins\n");

    end
    always @(pins) begin
        event_time_ps=$realtime*1000.0;
        if(event_fd) $fstrobe(event_fd,"%0.0f,%013b",event_time_ps,pins);
    end
    always @(posedge reference_40m) begin
        cycle=cycle+1;
        if(cycle==start_compare) begin
            event_time_ps=$realtime*1000.0;
            $fstrobe(event_fd,"%0.0f,%013b",event_time_ps,pins);
        end
        $fwrite(fd,"%0d,%0.0f,%b,%b,11,%013b\n",cycle,$realtime*1000.0,rst_n,midi_rx,pins);

        if(cycle==stop_cycle) begin
            finish_time_ps=$realtime*1000.0;
            #0.001;
            $fflush(fd);$fclose(fd);$fflush(event_fd);$fclose(event_fd);event_fd=0;
            $display("LANE_END lane=original cycle=%0d time_ps=%0.0f",cycle,finish_time_ps);
            $finish;
        end
    end
endmodule
