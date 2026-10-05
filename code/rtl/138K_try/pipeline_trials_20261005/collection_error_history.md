# 中途汇总入口错误留痕

第一次中途运行 collect 时，D 已创建 running 状态 receipt、尚未完成报告。汇总入口错误地仅按 receipt 存在就调用完整验收，读取 D 的 `_tr_content.html` 触发 FileNotFoundError，实际 CLI=1。未生成此次 results，不是 D 的综合／PnR 失败，也没有将缺报告认作 PASS。

仅修改新目录 `pipeline_trials.py` 的汇总控制：running／未构建条目列入 pending，不读取不存在的报告；只有 state=finished 才完整验收，已完成却缺报告仍明确报错。不修改候选、工具参数、时钟或旧验收器，不重跑物理试验。此记录保留入口缺陷，不覆盖实际构建日志。
