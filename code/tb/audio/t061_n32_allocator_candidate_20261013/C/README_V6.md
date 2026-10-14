# 当前 N32-C 入口：分段 v6

当前结果与边界见 `RESULT_20261014.md`；旧 v3 合同与 v4 说明保持历史原字节。
当前执行为已证明的 R05 真实 C00–C04 字节前缀＋R07 独立复位短段 C05–C09，
绝不是把两份日志拼成一份连续 PASS。

- `generate_v6.py`：独立输入黄金；`SHORT_SUFFIX` 默认输出 `plan_v6.jsonl/expected_v6.jsonl`。
- `tb_c_n32_r1_v6.sv`：真实公开驱动和观察；操作级 5000 拍防卡。
- `check_v6.py`：live 接受资格、逐沿独立数学及 23 个实际短段日志软件反例。
- `check_prefix_v6.py`：原始完整沿前缀资格、四退休／读排空及错误抢占槽软件反例，不补 END。
- `c_process.py`：owned Windows Job；sim 按 OP 转换判断进度，300 秒无语义推进即停。
- `c_assets.py --profile suffix-v6`：先生成输入与数学，再生成命令表，输入 SHA 前后保持。
- `c_capsule.py prepare --profile suffix-v6`：只从 B 已通过封存复制 DUT／依赖，冻结新输出；
  `execute` 必须从精确快照内运行，参数带外部 plan SHA。每份 plan 只执行一次，无自动重试。
- `c_prefix_evidence.py --full-math --output <新目录>`：只做原捕获的纯软件数学／反例，
  不启动编译／VVP；保留独立命令／退出码／源身份收据。
- `c_delivery.py seal --prefix <真实前缀报告> ...`：明确分段状态并保留失败全程。

已完成运行不需要重跑。重新执行任何工具必须重新核对用户/M2 的有效范围，不能拿本说明
当作恢复旧一次性许可。最终 ZIP 的 manifest 精确记录工具与源码、输入、两段证据和旧失败。
没有 Gowin、综合、PnR、STA 或设备操作。
