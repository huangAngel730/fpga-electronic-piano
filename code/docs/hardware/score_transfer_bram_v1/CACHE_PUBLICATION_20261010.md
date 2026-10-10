# T062 RAM 候选 GitHub 发布边界

用户在停止开发并要求交接后，追加明确要求“请你上传GitHub”。
本次仅发布已完成的 RAM 候选改动，不恢复 FPGA 构建，不操作设备。
目标为现有 origin/develop，禁止 force；N8、生产工程和共享登记文件不在本次提交范围。
实际提交号和远端确认以最终交付消息为准，本文不预称已上传。

## 源码和验证身份

最终功能为 ModelSim 40MHz/115200 UART 独立仿真；最终物理结果为 Gowin
GW5AST-LV138PG484AC1/I0 独立虚拟 I/O 模块，25ns/Setup uncertainty 1ns/
Hold uncertainty 650ps，Setup +7.654ns、Hold +0.001ns、TNS/违例零。
这不是完整系统 STA、真实 I/O 或上板许可。

两份已执行 RTL 的 SHA256：

- score_byte_lane.sv：ef9d42a6634fcbf1594ac7feb56609b9f84b2f3b280a6133ab1fe9e8e7400e7e
- score_transfer_bram_candidate.sv：ef57f7f98559a9f9dd262dacc77313cf720b4ff3df63ee962f75c41d1669bc1f

以下原始收据仍在本机 code/output，未改写，也不随本次 Git 提交上传：

| 相对路径 | SHA256 |
|---|---|
| m4_t062_cache_sim_20261010_02/receipt.json | 3832aa2b9ef7a3ea42ab153df7e0e7f265449247dde52da084b910bbcd9a0507 |
| m4_t062_cache_build_20261010_03/receipt.json | 88fa1b877ec7a02e0c4a3c7221484702833f49f27b44fef15bef217e57fb1e49 |
| m4_t062_cache_build_20261010_03/sta_review.json | 4e30cbc5838b7ce595e55b9a2ea227c41cd17f986483d6ca887bbb1f0a150703 |
| m4_t062_gate_20261010_02/receipt.json | 5d63195570bf432b0402534642e6e3129c70e1823525a76b1cddc0ddd3e03041 |

原工作树门禁 9PASS/exit0/125.344s，前后文件身份一致。发布文档后另在
code/output/m4_t062_publish_gate_20261010_01 保存本次暂存树对应的新九门禁与身份收据；
必须实际通过且树未变化才提交推送，不借用旧门禁作为新提交通过证明。

## 未完成事项

单一转发 ZIP 尚未生成。本次不把 ignored 原始日志、码流、仿真数据库或旧证据混入提交。
完整原始证据打包、M2 正式复核、共享状态/任务看板/验证编号登记及新整机验证仍待收口。
M2 交接消息待用户转发，尚未送达；同一设备上其他对话的进度通知不代替正式交接。
