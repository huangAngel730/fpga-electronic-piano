"""Emit public-only TB source; this script never compiles or simulates HDL."""
import json
from prepare import DOC, TB, M2, identity, save


def main():
    data = json.loads((DOC / "PORT_MAP.json").read_text(encoding="utf-8"))
    ports = data["raw_ports"]

    def decl(name, spec, direction="input wire"):
        width = "" if spec["width"] == 1 else f"[{spec['width'] - 1}:0] "
        signed = "signed " if spec["signed"] else ""
        return f"{direction} {signed}{width}{name}"

    port_declarations = ",\n    ".join(decl(n, s) for n, s in ports.items())
    fmt = ('{"schema":"M3_R7A_RAW_CORE_ROW_V1","capture_id":"%s",'
           '"source_line":%0d,"cycle":%0d,"time_ps":%0d,"epoch":null,'
           '"epoch_reason":"BIND_FROM_INDEPENDENT_RESET_EDGES","finish":%0d,"ports":{')
    fmt += ",".join('"' + name + '":"%b"' for name in ports) + '}}\n'
    fmt = json.dumps(fmt)
    args = ",\n                ".join(ports)
    observer = '''`timescale 1ns/1ps
// Testbench-only, public ports only; no production feedback or private DSP.
module r7a_public_observer #(
    parameter string CAPTURE_ID = "",
    parameter string PLAN_STOP_ID = "",
    parameter string RAW_PATH = "RAW_CAPTURE.jsonl",
    parameter string RESET_PATH = "RESET_EDGES.jsonl",
    parameter string END_PATH = "END.json",
    parameter longint EXPECTED_FINISH_CORE_CYCLE = -1,
    parameter longint MAX_CORE_SAMPLES = 0
) (
    input wire sys_rst_n,
    input wire finish_requested,
    output logic capture_done = 1'b0,
    @PORT_DECLS@
);
    integer raw_fd=0, reset_fd=0, end_fd=0, probe;
    longint sample_cycle=0, source_line=0, reset_seq=0;

    function automatic longint now_ps();
        now_ps = longint'($realtime * 1000.0);
    endfunction

    function automatic bit safe_token(input string value);
        integer i, c;
        begin
            safe_token = value.len()>0;
            for (i=0; i<value.len(); i=i+1) begin
                c=value.getc(i);
                if (!((c>=48 && c<=57) || (c>=65 && c<=90) ||
                      (c>=97 && c<=122) || c==45 || c==95)) safe_token=0;
            end
        end
    endfunction

    task automatic reset_snapshot(input string kind);
        begin
            reset_seq=reset_seq+1;
            $fwrite(reset_fd, "{\\"schema\\":\\"M3_R7A_RESET_SNAPSHOT_V1\\",\\"capture_id\\":\\"%s\\",\\"edge_seq\\":%0d,\\"time_ps\\":%0d,\\"kind\\":\\"%s\\",\\"values\\":{\\"sys_rst_n\\":\\"%b\\",\\"obs_rst_n\\":\\"%b\\",\\"obs_pll_locked\\":\\"%b\\"}}\\n",
                    CAPTURE_ID, reset_seq, now_ps(), kind, sys_rst_n, obs_rst_n, obs_pll_locked);
        end
    endtask

    initial begin
        if (!safe_token(CAPTURE_ID) || !safe_token(PLAN_STOP_ID))
            $fatal(1,"CAPTURE_ID_AND_STOP_ID_REQUIRED_SAFE_ASCII");
        if (EXPECTED_FINISH_CORE_CYCLE<0 || MAX_CORE_SAMPLES<=EXPECTED_FINISH_CORE_CYCLE)
            $fatal(1,"FROZEN_CAPTURE_WINDOW_REQUIRED");
        probe=$fopen(RAW_PATH,"r"); if(probe) begin $fclose(probe); $fatal(1,"RAW_EXISTS"); end
        probe=$fopen(RESET_PATH,"r"); if(probe) begin $fclose(probe); $fatal(1,"RESET_EXISTS"); end
        probe=$fopen(END_PATH,"r"); if(probe) begin $fclose(probe); $fatal(1,"END_EXISTS"); end
        raw_fd=$fopen(RAW_PATH,"w"); reset_fd=$fopen(RESET_PATH,"w"); end_fd=$fopen(END_PATH,"w");
        if (!raw_fd || !reset_fd || !end_fd) $fatal(1,"CAPTURE_OPEN_FAILED");
        // Time-zero snapshot is actual initial signal state after initial
        // assignments; X is retained. It is not a fabricated reset edge.
        #0;
        reset_snapshot("INITIAL");
        forever begin
            @(sys_rst_n or obs_rst_n or obs_pll_locked);
            reset_snapshot("CHANGE");
        end
    end

    always @(posedge obs_core_clk) begin
        if (!capture_done) begin
            if (!raw_fd) $fatal(1,"CORE_EDGE_BEFORE_CAPTURE_OPEN");
            if (sample_cycle>=MAX_CORE_SAMPLES) $fatal(1,"CAPTURE_SAMPLE_LIMIT");
            if (obs_polyphonic_valid !== 1'b1) $fatal(1,"NOT_PUBLIC_POLYPHONIC_MODE");
            source_line=source_line+1;
            // No delay and no NBA await before any sampled public value.
            $fwrite(raw_fd, @RAW_FORMAT@,
                CAPTURE_ID, source_line, sample_cycle, now_ps(), finish_requested,
                @RAW_ARGS@);
            if (finish_requested === 1'b1) begin
                if (sample_cycle != EXPECTED_FINISH_CORE_CYCLE)
                    $fatal(1,"FINISH_NOT_AT_FROZEN_CORE_CYCLE");
                $fwrite(end_fd, "{\\"schema\\":\\"M3_R7A_END_V1\\",\\"capture_id\\":\\"%s\\",\\"plan_stop_id\\":\\"%s\\",\\"finish_cycle\\":%0d,\\"time_ps\\":%0d,\\"row_count\\":%0d,\\"reason\\":\\"PLANNED_WINDOW_END\\",\\"ledger_status\\":\\"NOT_CHECKED_R6_5_REQUIRED\\",\\"serial_tail_status\\":\\"UNKNOWN_R6_6_REQUIRED\\"}\\n",
                    CAPTURE_ID, PLAN_STOP_ID, sample_cycle, now_ps(), source_line);
                $display("MONITOR_END capture_id=%s cycle=%0d time_ps=%0d rows=%0d reason=PLANNED_WINDOW_END",
                    CAPTURE_ID, sample_cycle, now_ps(), source_line);
                $fclose(raw_fd); raw_fd=0; $fclose(end_fd); end_fd=0;
                capture_done=1'b1;
            end
            sample_cycle=sample_cycle+1;
        end
    end

    final begin
        if(raw_fd) $fclose(raw_fd);
        if(end_fd) $fclose(end_fd);
        if(reset_fd) $fclose(reset_fd);
    end
endmodule
'''
    observer = observer.replace("@PORT_DECLS@", port_declarations).replace("@RAW_FORMAT@", fmt).replace("@RAW_ARGS@", args)
    wires = ";\n    ".join(decl(n, s, "wire") for n, s in ports.items()) + ";"
    connect = ",\n        ".join(f".{n}({n})" for n in ports)
    dut_obs = ",\n        ".join(f".{n}({n})" for n in ports if n.startswith("obs_"))
    tb = '''`timescale 1ns/1ps
// Source-only integration TB. Execution requires separate M2 admission.
module tb_r7a_public_capture #(
    parameter string CAPTURE_ID="",
    parameter string PLAN_STOP_ID="",
    parameter string BYTE_PLAN="bytes.drv", RESET_PLAN="reset.drv", READY_PLAN="ready.drv",
    parameter longint STOP_DRIVER_CYCLE=0,
    parameter longint EXPECTED_FINISH_CORE_CYCLE=-1,
    parameter longint MAX_CORE_SAMPLES=0,
    parameter longint MAX_SIM_TIME_PS=0
);
    logic sys_clk_50m=0, driver_clk_40m=0, finish_requested=0;
    wire sys_rst_n, midi_rx, driver_ready_not_connected, capture_done;
    @WIRES@
    always #10 sys_clk_50m=~sys_clk_50m;
    // R6-2 plan uses this independent external stimulus timebase. Observed
    // core cycles remain the actual obs_core_clk count, not driver cycles.
    always #12.5 driver_clk_40m=~driver_clk_40m;

    midi_public_port_driver #(.CLK_HZ(40_000_000),.MIDI_BAUD(31_250),
        .BYTE_PLAN(BYTE_PLAN),.RESET_PLAN(RESET_PLAN),.READY_PLAN(READY_PLAN),
        .EVENT_LOG("driver_aux_not_authoritative.log")) u_driver (
        .clk(driver_clk_40m),.sys_rst_n(sys_rst_n),.midi_rx(midi_rx),
        .event_ready(driver_ready_not_connected),
        .event_valid(obs_event_valid && obs_event_ready),.event_data(obs_event_data));

    m2_138k_pro_fourvoice_observer_top_r06 dut (
        .sys_clk_50m(sys_clk_50m),.sys_rst_n(sys_rst_n),.key_n(2'b11),.midi_rx(midi_rx),
        .i2s_bclk(i2s_bclk),.i2s_lrck(i2s_lrck),.i2s_din(i2s_din),.pa_en(pa_en),.uart_tx(uart_tx),
        .tmds_clk_p(),.tmds_clk_n(),.tmds_data_p(),.tmds_data_n(),
        @DUT_OBS@);

    r7a_public_observer #(.CAPTURE_ID(CAPTURE_ID),.PLAN_STOP_ID(PLAN_STOP_ID),
        .EXPECTED_FINISH_CORE_CYCLE(EXPECTED_FINISH_CORE_CYCLE),.MAX_CORE_SAMPLES(MAX_CORE_SAMPLES)) u_capture (
        .sys_rst_n(sys_rst_n),.finish_requested(finish_requested),.capture_done(capture_done),
        @CONNECT@);

    initial begin
        if (STOP_DRIVER_CYCLE<=0 || MAX_SIM_TIME_PS<=0) $fatal(1,"FROZEN_STOP_AND_WATCHDOG_REQUIRED");
        repeat (STOP_DRIVER_CYCLE) @(posedge driver_clk_40m);
        @(negedge driver_clk_40m);
        // Stable before the next PRE_NBA core sample, including coincident clocks.
        @(negedge obs_core_clk); finish_requested=1;
        wait(capture_done);
        #1; $finish;
    end
    initial begin
        if (MAX_SIM_TIME_PS>0) begin
            #(MAX_SIM_TIME_PS/1000.0); $fatal(1,"CAPTURE_ABSOLUTE_WATCHDOG");
        end
    end
endmodule
'''
    tb = tb.replace("@WIRES@", wires).replace("@DUT_OBS@", dut_obs).replace("@CONNECT@", connect)
    TB.mkdir(parents=True, exist_ok=True)
    for name, text in (("r7a_public_observer.sv", observer), ("tb_r7a_public_capture.sv", tb)):
        with (TB / name).open("x", encoding="utf-8", newline="\n") as f:
            f.write(text)
    save(DOC / "SOURCE_ASSEMBLY.json", {"top": "tb_r7a_public_capture", "HDL_status": "NOT_RUN",
        "public_DUT": "m2_138k_pro_fourvoice_observer_top_r06",
        "base_source_replacement_plan": identity(M2 / "SOURCE_REPLACEMENTS_R06C3.json"),
        "rule": "Use SOURCE_REPLACEMENTS_R06C3.json ordered replacement closure; add unchanged R6-2 driver then observer then this TB. No old integration TB or duplicate modules.",
        "new_TB_sources": [identity(TB / name) for name in ("r7a_public_observer.sv", "tb_r7a_public_capture.sv")],
        "ready_plan_support": "UNSUPPORTED_ON_INTEGRATED_TOP; driver-ready is disconnected and auxiliary log not authoritative",
        "finish_request_phase": "DRIVER_STOP_THEN_CORE_NEGEDGE_STABLE_BEFORE_PRE_NBA",
        "required_window_parameters": ["CAPTURE_ID", "PLAN_STOP_ID", "STOP_DRIVER_CYCLE", "EXPECTED_FINISH_CORE_CYCLE", "MAX_CORE_SAMPLES", "MAX_SIM_TIME_PS"],
        "board_release_allowed": False})
    print("PUBLIC_CAPTURE_HDL_SOURCE_WRITTEN_NOT_COMPILED")


if __name__ == "__main__":
    main()
