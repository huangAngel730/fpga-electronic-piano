# T052 128 沿公开端口静态准备

本写集只准备 M2 指定的 128 个 `posedge` 控制窗口，没有编译或运行 RTL，也没有执行 Gowin。冻结 v5 DUT、DDS、mixer、ROM 和旧证据均未修改。

## 数据来源与时序口径

- 输入唯一来源为 M2 的 `controls_proposed.jsonl`，SHA256 为 `b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02`。
- 170 位 `controls_128.hex` 是该计划的逐沿无损投影。软件预检逐字段重算并要求 128 行完全相同；TB 不读取任何 DUT 输出来决定后续输入。
- cycle 0 是第一个被观察的 `posedge`。cycle N 的输入在此前 `negedge` 已稳定；observer 在 `posedge` 的 NBA 更新前记录全部公开输入和 `calc_ready/result_valid/result_req_id`。
- 真接受仅为 `rst_n && !frame_tick && !cancel && sample_req && calc_ready`。
- 真发布仅为 `rst_n && !frame_tick && !cancel && result_valid && result_ready`。因此 frame/cancel 与 valid/ready 同沿时不得记发布。
- observer 只连接公开端口，不读取 `state/accept` 或任何层级内部信号。重复 ID 以 `[reset_epoch, accepted_serial, req_id]` 关联。
- `always @(rst_n)` 独立记录复位断言/释放的仿真时间和下一可见 cycle。缺边沿、窗口不完整或末尾仍有 open 事务时只能返回 UNKNOWN，不能 PASS。

## 只读依赖闭包

冻结 DUT 从仓库已跟踪的 M2 `RAW_EVIDENCE.zip` 精确成员提取；DDS、mixer 和 ROM 从 `READONLY_T052_DEPENDENCIES.zip` 提取。`source_manifest.json` 钉住外层包、成员、TB、observer、输入投影及本机拟用 Icarus 工具 SHA。未来若获许可，只能在全新 ASCII 输出目录提取和运行，不得读取同名工作树 DUT。

## 本次实际验证

- 仅运行 Python 静态检查与软件自检；没有 lower、compile、VVP、Gowin、综合、PnR、STA 或设备操作。
- 6 接受／3 发布／3 取消是冻结计划的软件预测，用于检查准备的一致性，不是实际 RTL 结果；测试夹具中的合成 observation 也明确仅供 parser 单测，不能作为 capture 交付。
- 旧 4207 结果完整性、实际 128 沿 RTL 输出、异步复位无遗漏和完整 T052 仍未验证。

## 后续唯一入口

M2 静态预检通过并另发一次精确小窗口许可后，才可按 manifest 中的拟执行命令建立全新目录、复核工具/源/计划身份、编译并运行一次。当前 `execution_authorized=false`，不得借用已消费的 T060 A/B 许可。
