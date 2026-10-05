# 禁止烧录：138K 离线优化实验

本目录仅用于 V0171 完整四声部音频＋HDMI 工程的离线物理优化。
生成 fs/bin 不等于时序通过，也不代表能够上板。

- 不调用 Programmer，不写 SRAM/Flash，不修改驱动、系统 PATH 或许可证。
- 正式仓库、M2 原包及此前 reproduction/preparation/comparison 目录保持只读。
- 50/25/125 MHz，系统 Setup uncertainty 1.000 ns、Hold 0.550 ns不放宽。
- 不删除 CDC 后级、载荷或异步 Recovery/Removal 检查，不取消公共 FIFO 满队列旁路。
- RTL 仅移植文件路径，不改接口、算法、计数同拍语义或复位释放拍数。
- 串行复位位置试验只改变 CST 两条 INS_LOC，不移动球位、不改电压或 PLL 位置。
- 即使有部分余量改善，也须同一版所有时序门禁通过后由 M2 复核；底板、实际器件版本和 PLL 启动仍待硬件确认。
- 本轮未提交、未推送、无新的 L6 实屏/音频证据。
