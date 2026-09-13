# 早期原型归档（已冻结）

本目录是 2026-09 的厂商无关 Verilog 八键原型，已冻结，仅作历史参考，不要在这里新增或修改文件。

```text
docs/   早期硬件笔记
rtl/    原型顶层、按键去抖、音源
tb/     原型自检 testbench
```

正式规范见 `code/docs/协作入口.md`，正式开发一律进 `code/`。

注意：`rtl/` 和 `tb/` 里的文件仍被 `.github/workflows/rtl-smoke.yml` 当作每次推送的冒烟回归使用，改动路径会影响 CI，不要删除或改名。

## 本地复现

在仓库根目录先激活工具链，再编译运行：

```powershell
. .\code\scripts\enter_fpga_env.ps1
iverilog -g2012 -Wall -o tb_proto.vvp legacy-prototype/rtl/electronic_piano_top.v legacy-prototype/rtl/key_debounce.v legacy-prototype/rtl/tone_generator.v legacy-prototype/tb/tb_electronic_piano.v
vvp tb_proto.vvp
```

期望输出含 `$finish called` 且不含 `ERROR:`。若不激活环境直接调用，iverilog 会因缺少 DLL 报 `0xC0000139`。实测记录见 `code/docs/验证记录.md` 的 V0003。

早期原型没有留下约束文件。本项目使用高云 Gowin 工具链，约束使用 `.cst`（引脚与电平）和 `.sdc`（时序），由 M2 负责，正式位置是 `code/constraints/`。不使用 Xilinx Vivado 的 `.xdc`，也不使用 Intel Quartus 的 `.qsf`。