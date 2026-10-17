# B2版本与首差异原件

没有功能进程意外失败、崩溃或超时；预期反例CLI exit1不是运行失败。两轮源/工具前后SHA同，原收据和原件均不覆盖。

ROUND_01：19项新适配CLI全部符合预期（1正18拒收），8.453秒。新正例为12000拍/两epoch/14请求的CSV运输夹具，沿用只读producer代码构造**新输入**，没有调用旧38k测试、test_suite、R05 analyze或上午monitor自测。其frame级ID包含ffffffff→0，0的两笔完整串行都核到。12完整stereo含启动零，10请求完整、2复位截断、2观察尾UNKNOWN。

随后只读子智能体静态发现额外cancel未清理本桥在途状态，可能放过后续commit；该具体缺口没有在旧R1额外执行误收试验，不能冒称旧反例已运行。旧R1通过不掩盖此漏项。另指出全字段拒X严于monitor原合同，最终明确限定ALL_COLUMNS_KNOWN_FAIL_CLOSED，不做补零兼容。

ROUND_02：最小修复active_key生命周期/cancel-reset清理/commit-on-cancel拒收，补原ID行号映射；仅跑3项新增量：合法取消无发布exit0、额外取消exit1(UNEXPECTED_CANCEL，CSV850行/原cycle849/epoch0/IDffffffff)、commit同沿cancel exit1(COMMIT_ON_CANCEL)，2.734秒。未重跑R1已通过19项，最终源码不能写成22项全量重跑。

自身只读子智能体复查最终增量和现有结果未发现具体阻断，未运行程序或修改文件。B1合同只读到件补充未触发旧测试重跑；真实source/黄金/sidecar和完整结束原件仍缺，Pro B2仍PENDING。
