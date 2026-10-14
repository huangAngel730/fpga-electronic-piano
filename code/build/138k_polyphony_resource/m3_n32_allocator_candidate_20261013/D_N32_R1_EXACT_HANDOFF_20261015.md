# N32-D 精确 N32/R1 工程交接

日期：2026-10-15
状态：`PREPARED_L0_L1_ONLY`；D 只完成工程准备，未执行综合、PnR、STA 或设备操作。
范围：供 M2 做资源准入和后续受控执行核定；完整 T061 仍为 PARTIAL。
通信状态：待用户转发，尚未送达。

## 1. 冻结工程身份

- 目录：`prepared/N32_R1_20261014_R02/`
- schema／状态：`N32_D_PREPARE_V1`／`PREPARED_NOT_EXECUTED`
- 器件：`GW5AST-138C`，`GW5AST-LV138PG484AC1/I0`，index `gw5ast138c-007`
- 顶层：`m3_n32_resource`
- 工程 manifest：`9367dae17e2ff066c39a169f98673905954485a33ec0d19553f4675cc2dc639b`
- GPRJ：`8cfa1ec3e3af8fa0b94e6b437d59522656a3b6d90832ff543011fc4425f47b8c`
- SDC：`31fed021207a7d23a88380795d05c92086494350bdf26bfb41e8f1d519fbffac`
- Tcl：`ab297d10bb64798c16b15c1923b2372ed9baa59b3572737cada83d91a155fe67`
- D R02 ZIP：`256551be862a5945b51350dfe155699fe1400470d6b7d2a66c079701c3e621e5`
- D R02 MANIFEST：`d21e69b816303308ad057380b8d9e491fb2713fcf51486232cb8e55156225323`
- D R02 seal：`bdcc3ce5e3ecc08cd5986fbdda5b04fcfe0b225a4dff1c585d4ff0550ceaa456`

封存记录为 125 个成员、0 次 EDA 调用。既有 44 项仅为软件／静态准备检查，不能替代综合或物理时序结果。

## 2. 顶层与 wrapper 的关系

- D 资源顶层 `m3_n32_resource.sv`：SHA256
  `a7d193a27994a218fa6961b7eae66be29e648b9df2a2470d436982f063ecbb3f`。
  它固定例化 `b_n32_event_audio_prom #(.N(32), .RESPONSE(1))`，公开 event、sample、result、
  左右 PCM、`late`、准确 `clipped`、取消／复位和公开读口；注入固定关闭。
- B 隔离仿真 wrapper `code/rtl/common/m3_n32_allocator_candidate_20261013/B/b_n32_r1_wrapper.sv`：
  SHA256 `c7776858b508cc9069d5a36f1fcedb3348ab5648be6a84120fc1589f3cd33000`。
  它公开逐槽／控制观察量并承载仿真变异宏，只用于 B 隔离验证，**不在 D 的 19 个综合 HDL 输入中**。
- 因而 B wrapper 的仿真结论不能冒充 D 顶层已经执行；D 顶层也没有改动公共生产顶层。

## 3. 精确 HDL／include／ROM 输入

以下 SHA 均取自冻结工程 manifest；顺序即 GPRJ 的 HDL 顺序。

| 类别 | 冻结工程相对路径 | SHA256 |
|---|---|---|
| HDL | `sources/audio_defs_pkg.sv` | `833076283882bae79af3f54c40e6cd6ae4a9ff5638a90e4f0afc3e2b3861d064` |
| HDL | `sources/sustain_control_contract_pkg.sv` | `329d855dea5885cbcd97e5c8ab75c5283bbb15db33cab3460bde637be7b207a2` |
| HDL | `sources/note_pitch.sv` | `9a86ebea3041f73d8624c0dc9a32844ef13c448b46d911d39f94ebb39ee88e69` |
| HDL | `sources/b1_statebank.sv` | `9ab598affbd317dedb5bdd7e099335ad1f60e3c84ed115f6669d52b3966521ed` |
| HDL | `sources/b1_scheduler.sv` | `e11c2fb7e4c80160d42b44948003863892435050e27e47afc6e61ad6d5b78c9d` |
| HDL | `sources/m3_balanced_voice_allocator.sv` | `51472b796c9cd883e0fd07ec304559c249fd055929b64a96d53aad5af5b2ce99` |
| HDL | `sources/b2c_sustain_controller.sv` | `ebb942402e190c136a6ff0d2fd751cabdbf34a83be75bf7953360f0d8534a2d5` |
| HDL | `sources/b_n32_event_router.sv` | `10f1fef4cb133a831081e6a14acb7292d47f491e65ed164fe65720acbea0936f` |
| HDL | `sources/b2d_control_snapshot.sv` | `9cb23b971d243e1dcf43d2acf0445239f1f26b2f0edc51476ce6a0d5c5d450fd` |
| HDL | `sources/m2_prom_gain.sv` | `5321b6e854ad5be02f78f7e82c8ba311ddce72c28ce7ca72323a9ef84adc17b0` |
| HDL | `sources/m2_prom_oct.sv` | `2f5d8e901eba60634ae2daa40d29e0c074520e2f7fb5111f00882f5c30874b5b` |
| HDL | `sources/m2_prom_sub.sv` | `b683d5d49834632e3413a3038ea5b8f5c79c7c783a7cfe47e8c8f8cb124d9c23` |
| HDL | `sources/m2_prom_lfo.sv` | `f5684f760ed41a7ac86284e36ade73bbaa36e0b48dde2c765203843c29283fee` |
| HDL | `sources/m2_prom_wave.sv` | `fa606e6e05ed36ad9b880f19684a0b7859262e56c9a104df30bef59d8b04f909` |
| HDL | `sources/m2_adsr_piano_prom.sv` | `d8918defedb1d9bd14a21903d5bc955a815f5064860ed948fa1f38e585e06087` |
| HDL | `sources/m2_pitch_mod_prom.sv` | `190cf8a854563ab64cdd1afe16da40a8f061613636b6f3183c28eb8272c33b50` |
| HDL | `sources/m2_b2_backend_prom.sv` | `6727971f60c5aadab9985641035ec5ff8ad284f1e06adcfd9e58f78cf74d6953` |
| HDL | `sources/b_n32_event_audio_prom.sv` | `3012fc17def3f431f34061355ea172b7ecd17ac6f6a8913d2c8d518e32f647d3` |
| HDL/top | `sources/m3_n32_resource.sv` | `a7d193a27994a218fa6961b7eae66be29e648b9df2a2470d436982f063ecbb3f` |
| include | `include/sine_table.svh` | `969fc7d1036e359fc55c3b0ca18eaf3c8a123a146ed95c32a81e52ee10519cca` |
| include | `include/sustain_controller_ports.svh` | `8c51459cd47a7e21609cc02780a93af7d6be0fd5bf2d2278edda92e8a7ef486d` |
| ROM | `rom/velocity_gain_rom.mem` | `1bc0fd4430884604224a20620368afa50805b4efbf57d9703cae7a09132ffe64` |
| ROM | `rom/piano_band_4x256_8191.mem` | `c117230f43c7efce36be445f851140d3155aa2a35e71ea8a41f529ea2b5d32a1` |
| ROM | `rom/oct_ratio_q16.mem` | `65185caf2722c98cd5406ecff0819f8b011cbbe6a5b9ae1974d3a03f4cf15fbd` |
| ROM | `rom/sub_ratio_q16.mem` | `9530577dfbc9b901d83abaa1a6f1c929241f7c092b5fc556b106b0c8bffc984e` |
| ROM | `rom/lfo_sine_q15.mem` | `6f68f32afdf43cb8cbe6ff7bf4db155282d8ebf8783b94ebf690a5cd0d137060` |

## 4. 40 MHz、复位与约束口径

唯一 SDC 内容为：

```tcl
create_clock -name sys_clk -period 25.000 [get_ports {clk}]
set_clock_uncertainty -setup 1.000 [get_clocks {sys_clk}]
set_clock_uncertainty -hold 0.650 [get_clocks {sys_clk}]
```

- 单时钟 `clk`，周期 25 ns，即 40 MHz；保护口径为 Setup 1.000 ns、Hold 0.650 ns。
- 顶层和业务模块使用低有效 `rst_n`；业务时序块可见 `posedge clk or negedge rst_n`，即异步断言。
- 顶层注释要求上游同步释放，但 D 顶层没有内置 reset synchronizer；复位释放来源、恢复／移除检查及
  reset 高扇出均仍需 M2 在实际集成网表中核定。
- D 没有 CST、板级引脚或 I/O Bank 电压约束，也没有 false path／multicycle 例外。
- `run_synthesis_only.tcl` 只打开上述 GPRJ、指定同一 top／include 并调用 `run syn`；它未被执行。

## 5. M2 后续资源准入待核项

1. 先按上述 manifest、GPRJ、SDC、top 和工具／机器身份确认唯一受控输入；不得把旧 N32、旧 RAM、
   模块 STA 或其他组合的资源／时序数字套到本工程。
2. 如放行综合，先确认 19 个 HDL、2 个 include、5 个 ROM 的实际读取集合与顺序，且 wrapper、TB、
   变异宏、`prim_sim.v` 不进入综合。
3. 资源报告仍为 UNKNOWN；综合、技术映射、PnR、40 MHz Setup/Hold、Recovery/Removal 均未执行。
4. 无 CST；正式接入前需映射旧板级草案中尚未对应的新组合时序端点，并独立核实际网表。D 不提供
   引脚、跨时钟或板级 I/O 签收依据。
5. D R02 当时只绑定 A、B 和 C 的分段证据。后来的 C_FULL R02（ZIP
   `15372b95e41463ce6dc459269cf5a60134bda1f7434f41ffc50f9ac2e74d0c9e`）没有自动重绑、重签或改写
   D 的 manifest；若 M2 要以 C_FULL 为资源准入依据，应另建明确后继，不能回填 D 历史原件。
6. 本交接不恢复任何已消费执行许可，不授权重试、换工具、提高超时、PnR、STA、安装、下载、烧录或接线。

结论：D 的精确输入和约束传递已可审计，但仅是“可审核、未执行”的资源工程准备。下一步由 M2 做
资源准入判断；如发现具体源码／接口问题，再按精确反馈进行定点返修。
