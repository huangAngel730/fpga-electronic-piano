# R8-04 独占输出与消费账本准备

PREPARED_NOT_RUN，七例归总控 S 组，含四线程同一claim竞争。入口：同名 software 目录 `m3r08_04.py --request REQUEST.json --output NEW_OUTPUT_DIR`。

schema=M3_R08_RESERVATION_REQUEST_V1；字段为action(RESERVE/FINALIZE)、root、capture_id、plan_sha256、nonce、guard、outcome。root仅本项docs/test或总控目录。guard只携带已校验plan SHA和NOT_GRANTED，不能产生执行许可。

用O_EXCL独占claim；capture/plan/nonce/root/output全绑定，终态另写exclusive原件。重复占用、已有输出、失败后复用及nonce更换拒收；不删除claim/失败历史。检查root/claims/claim/terminal/output路径别名与根边界；并发原子性仅限本机普通文件系统，不声称抵御具有同目录替换权限的敌对进程。

预期产物含原claim和独立终态收据；execution_allowed恒false。该状态机只验证一次性文件消费，不证明任何进程树/双流/Job清理安全。
