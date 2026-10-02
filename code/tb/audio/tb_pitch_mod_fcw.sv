// Self-checking TB for pitch_mod_fcw.sv  (M2 V0143 防假绿修正版, 2026-10-02)
//
// 修正内容：
//   1. 检查向量数量 >= 62273，防空文件/截断
//   2. 检查 fcw_out 无 X/Z，防 LUT 未初始化
//   3. 检查 malformed 行数，空向量必须失败
//
// Run (Icarus):  iverilog -g2012 -o tb.vvp tb_pitch_mod_fcw.sv pitch_mod_fcw.sv
//                vvp tb.vvp +VECTORS=<...>/pitch_mod_vectors.txt
//                +OCT_PATH=... +SUB_PATH=... +LFO_PATH=...

`timescale 1ns/1ps

module tb_pitch_mod_fcw;
    logic               clk = 0;
    logic               rst_n = 0;
    logic               sample_enable = 0;
    logic               note_on = 0;
    logic signed [11:0] bend = 0;
    logic [11:0]        modulation = 0;
    logic [4:0]         pitch_range = 2;
    logic [31:0]        base_fcw = 0;
    logic [31:0]        fcw_out;
    logic               fcw_valid;

    integer fvec, r, errors, samples, malformed;
    integer v_base, v_bend, v_range, v_mod, v_note_on, v_expect;
    string vec_path, oct_path, sub_path, lfo_path;

    // M2 V0147: 防空向量/截断，同步新增饱和场景后的总数
    localparam int MIN_VECTORS = 62279;

    pitch_mod_fcw dut (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_enable(sample_enable),
        .note_on(note_on), .bend(bend), .modulation(modulation),
        .pitch_range(pitch_range), .base_fcw(base_fcw),
        .fcw_out(fcw_out), .fcw_valid(fcw_valid)
    );

    always #10 clk = ~clk;   // 50 MHz

    task drive_sample(input integer b, input integer bd, input integer rg,
                      input integer md, input integer no, input integer exp);
        begin
            @(negedge clk);
            base_fcw    = b[31:0];
            bend        = bd[11:0];
            pitch_range = rg[4:0];
            modulation  = md[11:0];
            note_on     = no[0];
            sample_enable = 1;
            @(posedge clk);
            @(negedge clk);
            sample_enable = 0;
            note_on = 0;
            #1;
            samples = samples + 1;
            // M2 V0143: 检查 X/Z，防 LUT 未初始化
            if (^fcw_out === 1'bx) begin
                $display("FAIL: sample %0d fcw_out contains X/Z", samples);
                $fatal(1, "fcw_out X/Z detected (LUT uninitialized?)");
            end
            if (fcw_out !== exp[31:0]) begin
                if (errors < 10)
                    $display("FAIL: sample %0d base=%08x bend=%0d rng=%0d mod=%0d no=%0d got=%08x exp=%08x",
                             samples, b, bd, rg, md, no, fcw_out, exp);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        errors = 0; samples = 0; malformed = 0;
        if (!$value$plusargs("VECTORS=%s", vec_path)) begin
            $display("FAIL: +VECTORS=<path> is required");
            $fatal(1, "missing VECTORS");
        end
        if (!$value$plusargs("OCT_PATH=%s", oct_path)) begin
            $display("FAIL: +OCT_PATH=<path> is required");
            $fatal(1, "missing OCT_PATH");
        end
        if (!$value$plusargs("SUB_PATH=%s", sub_path)) begin
            $display("FAIL: +SUB_PATH=<path> is required");
            $fatal(1, "missing SUB_PATH");
        end
        if (!$value$plusargs("LFO_PATH=%s", lfo_path)) begin
            $display("FAIL: +LFO_PATH=<path> is required");
            $fatal(1, "missing LFO_PATH");
        end

        fvec = $fopen(vec_path, "r");
        if (fvec == 0) begin
            $display("FAIL: cannot open %s", vec_path);
            $fatal(1, "cannot open vectors");
        end

        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk);

        // check 1: reset state
        if (fcw_out !== 32'd0) begin
            $display("FAIL: reset did not clear fcw_out (%08x)", fcw_out);
            errors = errors + 1;
        end

        // check 2..N: every golden vector, sample by sample
        while (!$feof(fvec)) begin
            r = $fscanf(fvec, "%h %h %h %h %d %h\n",
                        v_base, v_bend, v_range, v_mod, v_note_on, v_expect);
            if (r == 6) begin
                if (^{v_base,v_bend,v_range,v_mod,v_note_on,v_expect} === 1'bx)
                    $fatal(1,"unknown vector field near sample %0d",samples);
                drive_sample(v_base, v_bend, v_range, v_mod, v_note_on, v_expect);
            end else if (r != -1) begin
                $display("FAIL: malformed vector line near sample %0d", samples);
                $fatal(1,"malformed vector: parsing did not advance");
            end
        end
        $fclose(fvec);

        // M2 V0143: 检查向量数量下限，防空文件/截断
        if (samples != MIN_VECTORS) begin
            $display("FAIL: only %0d vectors, expected exactly %0d", samples, MIN_VECTORS);
            $fatal(1, "vector count mismatch (empty, truncated or extra file?)");
        end
        if (malformed > 0) begin
            $display("FAIL: %0d malformed lines", malformed);
            $fatal(1, "malformed vector file");
        end

        // check N+1: async reset clears the LFO and the output
        rst_n = 0;
        @(negedge clk);
        #1;
        if (fcw_out !== 32'd0) begin
            $display("FAIL: async reset did not clear fcw_out");
            errors = errors + 1;
        end
        rst_n = 1;

        if (errors == 0) begin
            $display("PASS: tb_pitch_mod_fcw (%0d samples matched golden model)",
                     samples);
            $finish;
        end
        $fatal(1, "FAIL: tb_pitch_mod_fcw %0d/%0d samples mismatched",
               errors, samples);
    end
endmodule
