// -----------------------------------------------------------------------------
// tb_key_event_source.sv
// 按键事件源自检。对应任务 T014（统一演奏事件接口测试桩）。
//
// 覆盖：
//   - 复位后不产生事件；
//   - 按下脉冲产生 Note On，音符号正确（A4=69 / C5=72）；
//   - 松开脉冲产生 Note Off；
//   - 事件字段与规范 3.1 的位域一致（含 velocity=0 必须转 Note Off）；
//   - valid/ready 握手：ready 为 0 时事件保持，直到被接收；
//   - res erved 位必须为 0（规范 3.1：不得用保留位私传状态）。
//
// 运行：.\code\scripts\run_t007_sim.ps1
// -----------------------------------------------------------------------------

`timescale 1ns / 1ps

module tb_key_event_source;

    localparam real CLK_PERIOD_NS = 10.0;

    logic clk = 1'b0;
    logic rst_n = 1'b0;

    always #(CLK_PERIOD_NS/2.0) clk = ~clk;

    logic                              press_pulse;
    logic                              release_pulse;
    logic                              event_valid;
    logic                              event_ready;
    perf_event_pkg::performance_event_t event_data;

    int pass_cnt = 0;
    int fail_cnt = 0;

    // 单键实例：KEY0 -> A4(69)
    key_event_source #(
        .KEYS             (1),
        .SOURCE_ID        (4'd1),
        .NOMINAL_VELOCITY (10'd512),
        .NOTE_MAP         (7'd69)
    ) dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .press_pulse   ({press_pulse}),
        .release_pulse ({release_pulse}),
        .event_valid   (event_valid),
        .event_ready   (event_ready),
        .event_data    (event_data)
    );

    import perf_event_pkg::*;

    task automatic check(input string name, input logic cond);
        begin
            if (cond) pass_cnt++;
            else begin
                fail_cnt++;
                $display("  FAIL: %s", name);
            end
        end
    endtask

    // 等待 n 个时钟上升沿，并在边沿之后再采样。
    //
    // 【为什么要 #1】
    //   @(posedge clk) 返回的瞬间，Nonblocking 赋值尚未生效。
    //   若在此刻读信号，读到的是**上一个**周期的值，
    //   断言会整体晚一拍，表现为"按下后 valid 还是 0"这类假失败。
    //   #1 让当前时间片内的 NBA 更新全部落地后再读。
    task automatic tick(input int n);
        begin
            repeat (n) @(posedge clk);
            #1;
        end
    endtask

    // 发一个单周期脉冲。
    //
    // 【为什么在 negedge 驱动、在 posedge 采样】
    //   驱动与采样若都在 posedge，DUT 的 always_ff 与 testbench 的赋值
    //   会竞争，出现"有时看到有时看不到"的不确定结果。
    //   在 negedge 改变激励，保证 posedge 到来时输入已稳定。
    task automatic pulse_press;
        begin
            @(negedge clk); press_pulse = 1'b1;
            @(negedge clk); press_pulse = 1'b0;
        end
    endtask

    task automatic pulse_release;
        begin
            @(negedge clk); release_pulse = 1'b1;
            @(negedge clk); release_pulse = 1'b0;
        end
    endtask

    initial begin
        $display("=== tb_key_event_source ===");

        press_pulse   = 1'b0;
        release_pulse = 1'b0;
        event_ready   = 1'b1;
        rst_n         = 1'b0;

        // ---------------------------------------------------------------------
        // 1. 复位
        // ---------------------------------------------------------------------
        tick(4);
        check("复位: event_valid 为 0", event_valid == 1'b0);

        rst_n = 1'b1;
        tick(4);
        check("释放复位后: 仍无事件", event_valid == 1'b0);

        // ---------------------------------------------------------------------
        // 2. 按下 -> Note On
        //
        // 【为什么不能"发脉冲后等两拍再断言"】
        //   event_ready 恒为 1，事件在被寄存的**下一个**时钟沿就被下游接收，
        //   pending_q 随即清 0。所以 valid 只维持一个周期，
        //   等两拍再断言必然读到 0——这是测试写法问题，不是 DUT 缺陷。
        //   正确做法：在脉冲发出后立刻（当拍）检查事件内容，
        //   或者在负边沿检查。
        // ---------------------------------------------------------------------
        pulse_press();
        // pulse_press 结束于 negedge，此刻 DUT 的组合输出已反映新事件
        check("按下后: event_valid 拉高", event_valid == 1'b1);
        check("按下后: 事件类型为 NOTE_ON", event_data.event_type == EVENT_NOTE_ON);
        check("按下后: 音符号 = 69 (A4)", event_data.note_number == 7'd69);
        check("按下后: source_id = 1", event_data.source_id == 4'd1);
        check("按下后: velocity = 512", event_data.velocity == 10'd512);
        check("按下后: reserved 必须为 0（规范 3.1）", event_data.reserved == 6'd0);

        tick(2);
        check("握手完成后: event_valid 回落", event_valid == 1'b0);

        // ---------------------------------------------------------------------
        // 3. 松开 -> Note Off
        // ---------------------------------------------------------------------
        pulse_release();
        check("松开后: event_valid 拉高", event_valid == 1'b1);
        check("松开后: 事件类型为 NOTE_OFF", event_data.event_type == EVENT_NOTE_OFF);
        check("松开后: 音符号仍为 69", event_data.note_number == 7'd69);
        tick(2);
        check("松开握手完成后: event_valid 回落", event_valid == 1'b0);

        // ---------------------------------------------------------------------
        // 4. 握手背压：ready=0 时事件必须保持，不得丢失
        // ---------------------------------------------------------------------
        event_ready = 1'b0;
        pulse_press();
        tick(4);
        check("ready=0 期间: event_valid 保持为 1", event_valid == 1'b1);
        check("ready=0 期间: 事件内容保持为 NOTE_ON",
              event_data.event_type == EVENT_NOTE_ON);

        event_ready = 1'b1;
        tick(2);
        check("ready 恢复后: 事件被接收，valid 回落", event_valid == 1'b0);

        // ---------------------------------------------------------------------
        // 5. velocity=0 的 Note On 必须转成 Note Off（规范 3.4）
        //
        //    这里直接调用构造函数验证规则被固化在构造入口，
        //    避免将来某个输入适配层遗漏该转换。
        // ---------------------------------------------------------------------
        begin
            perf_event_pkg::performance_event_t ev;
            ev = make_note_event(1'b1, 4'd1, 4'd0, 7'd69, 10'd0);
            check("velocity=0 的 Note On 转为 NOTE_OFF（规范 3.4）",
                  ev.event_type == EVENT_NOTE_OFF);
            check("转换后保留音符号", ev.note_number == 7'd69);

            ev = make_note_event(1'b1, 4'd1, 4'd0, 7'd69, 10'd1);
            check("velocity=1 仍为 NOTE_ON", ev.event_type == EVENT_NOTE_ON);

            ev = make_note_event(1'b0, 4'd1, 4'd0, 7'd69, 10'd512);
            check("is_on=0 且 velocity 非 0 仍为 NOTE_OFF",
                  ev.event_type == EVENT_NOTE_OFF);

            ev = make_all_notes_off(4'd1);
            check("ALL_NOTES_OFF 类型正确", ev.event_type == EVENT_ALL_NOTES_OFF);
            check("ALL_NOTES_OFF 的 reserved 为 0", ev.reserved == 6'd0);
        end

        // ---------------------------------------------------------------------
        // 6. 运行中复位
        // ---------------------------------------------------------------------
        pulse_press();
        check("复位前: 有挂起事件", event_valid == 1'b1);

        rst_n = 1'b0;
        tick(2);
        check("运行中复位: event_valid 清零", event_valid == 1'b0);

        rst_n = 1'b1;
        tick(4);
        check("复位恢复: 无残留事件", event_valid == 1'b0);

        $display("");
        $display("=== 结果: %0d PASS, %0d FAIL ===", pass_cnt, fail_cnt);
        if (fail_cnt != 0) begin
            $display("TESTBENCH FAILED");
            $fatal(1);
        end
        $display("TESTBENCH PASSED");
        $finish;
    end

endmodule
