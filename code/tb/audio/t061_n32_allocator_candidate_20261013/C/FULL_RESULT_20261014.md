# N32-C 单次完整连续验证补齐

Review-Key：`T061-N32-C-FULL-CONTINUOUS-20261014-R02`。
当前实际结论：完整 C00–C09 指定输入的连续功能 L2／数学 L3 自验通过，待 M2 复核。
完整 T061 保持 PARTIAL；本文件形成时尚未提交推送，实际发布身份另见后续发布收据。
原 R07 分段包、R05/R06 失败和本次 R01 软件反例失败均保持原字节。

## 单一真实捕获

同一 DUT 实例、同一 VVP 进程从原 FULL 输入的首操作连续执行至唯一 END；未拼接前缀／
后缀、未导入 checkpoint。计划中的 C00/C07/C09 复位照原输入真实执行，不额外复位
长释放或 C04→C05 边界。原 4800 个采样 tick 释放过程不改，不 force 退休。

- 操作 10376 项，C00–C09 全部完成；结束 cycle 4117219。
- 230 次事件接受、4945 次采样接受、4942 次发布、158144 条逐槽结果、261 次公开读回。
- 独立数学模型得到 4 次真实退休、69 次窃取、2 次重触发、13 次踏板延迟释放。
- 最大首次结果延迟 347 拍；F/K/P、HOLD、取消／复位围栏、公开读返回与身份分别核对。
- 原始 capture：`code/output/n32cfr01/simulate.stdout.bin`，45522685 字节，SHA256
  `daf92770d8b92ec283d9eae726c5a39a8023a28808b0b262376d44c09654c79d`。
- 唯一新编译 1.094 秒、唯一新仿真 1034.828 秒，均退出 0、无 timeout。
  仿真虚拟时间约 102.93 ms，不是持续真实演奏 17 分钟。

## 首失败、最小返修与软件后继

R01 正常完整捕获及独立数学检查通过（数学 214.125 秒退出 0），但新增第24项软件反例
使用不存在的 case 名 `C01_STEAL_33`，触发 StopIteration；原反例步骤退出 1，原总收据
真实保留 `FAIL_PARTIAL / ValueError:C_STEP_FAILED:mutations`，不回填 PASS。

修后精确选择 C01_FILL32_STEAL33 的 op67（32 次填槽后 source3/channel15/note100），
只在该 OP 内最后的公开 U 记录交换 slot0/slot1 的 occupied/releasing/velocity/fcw/
note/source/channel/generation 全部8字段，严格命中 `C4_PUBLIC_ROUTE_IDENTITY_OR_STEAL`。
前23项也重新作用于本次完整 raw，逐项 scope 均改为 FULL，未复用旧短例反例结果。

R02 只执行软件 checker 与24项软件 capture 反例，没有再次编译或仿真。
`full_reuse_guard.py` 外部钉住原缺陷 checker SHA、原精确失败原因、唯一原 compile/sim/
check 成功且无 timeout、原 FULL 数学报告、原输入与工具 after SHA。plan_v6、expected_v6、
输入 mem、HDL、ROM及数学生成器必须原 SHA；正常身份／检查／main 函数 AST保持。
短段、超时／失败仿真、任意其他失败、重签改动输入、模型漂移均拒收。
执行收据明确 `RTL_REUSED_NO_NEW_SIMULATION`，原失败与新软件 PASS 链均封存。

- 新软件自检：20项通过（2项关联防卡＋7项 FULL 身份／边界＋4项窃取选点＋7项复用资格）。
- R02 数学重算 219.125 秒、24项反例集合 31.015 秒，均退出 0；总 259.890 秒退出 0。
- 反例集合退出 0 表示24项各自以 exit1 正确拒收；不是24次 RTL 行为变异，也不冒称24次
  独立 OS 进程。原报告和实际集合命令／收据保留。

## 精确身份

| 对象 | SHA256 |
|---|---|
| R01 原执行 plan | `8c759b5e9273569044217f5601938179eaac963aa93860a6a1a999130f6d24c7` |
| R02 软件后继 plan | `efabf748b5085679e067292a99437dbe689ebb19db698b22670b2aab2bf4eb28` |
| R02 收据 | `efbb45bc2b3263b045ce7ccc4271b6b18e3414f73181ada296e460624bffd8e9` |
| R02 数学报告 | `b503715a9fd64cc49a84c7d11852bf175224d9c7c1a235d77feee848cdae28ed` |
| R02 反例报告 | `09909ff996e6a1507e8872a5ea9b0a971887246cc7ecebef2dd40dc5dc4b0359` |

原工具不换、业务 RTL/TB/ROM 不改；C00–C09 业务输入沿用已存在的 v6 FULL 生成定义，
不是新声音算法或新接口。修改仅在 C 软件执行／身份／反例／封存编排和独立说明。
最终包同时保留原执行准备快照及软件后继快照，不能混称同一运行源版本。

## 未验边界与交接

正常 capture 的 clipped 全为0、左右相等；命中一次 PCM24 负满幅但不 clip 的精确等号，
不能扩写为正负饱和／不同 clip 值错拍交换／不等左右声道交换覆盖。已有独立专项保留
各自结论，不借本 FULL 运行扩大验收范围。

没有新 Gowin、综合、PnR、物理40MHz STA、正式顶层接入或设备操作。D R02仍是原精确
prepare，未自动重绑或重签本次 C 后继。资源 UNKNOWN／STA NOT_RUN，完整 T061 PARTIAL。
请 M2 按此精确单次 FULL 证据复核、登记；共享看板与状态仍由 M2统一更新。
