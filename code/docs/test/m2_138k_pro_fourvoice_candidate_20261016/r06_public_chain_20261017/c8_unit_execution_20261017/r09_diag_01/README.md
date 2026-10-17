# R09用户授权的唯一verbose编译诊断（2026-10-17）

用户直接答复“授权一次有界编译诊断”，M2已在任务单/四状态先记录范围再执行。仅同raw两源/同工具/同固定环境，原argv只加-v，新组20秒/compile15秒。新诊断已消费并结束，**编译仍失败，根因UNKNOWN，Pro仍PARTIAL、board_release_allowed=false**。没有VVP/boundary/C9/EDA/设备或自动重试；旧SW/UNIT01与30秒条件修复消费保持。

控制器exit1/10.637803秒；compiler exit3221225477(0xC0000005)/9.067787秒，未触期限。原生stdout1977B/SHA255b8b4a…ab2dc210、stderr897B/SHA46a42d4a…0d03f4ce，完整本体在封包。日志可见PARSING INPUT、ELABORATING DESIGN、CODE GENERATION、DONE和统计；只能确定这些可见阶段已经输出，不能据此认定具体异常调用/模块、全部编译成功或根因已修。产物仍未执行。Windows Job共5进程，最终active0，root句柄已关闭，输入工具身份前后同，封存双流清理无错误。

原件包`R09_DIAG_01_ORIGINAL_EVIDENCE.zip`：391077B，SHA256 **e1b75b77ec7f75fd3e59fab116f488678a499354c25d650c706b768fe495e7fd**，39载荷，CRC及全部大小/SHA回读同。含当前源/授权/精确准入、消费、原双流、前次失败、已验执行器与proof/工具清单。原UNIT01失败、原软件证明和旧源不改写；新入口只复用其已验Job能力，未新增软件功能测试或复跑旧组。

本次独立诊断授权已经用完，不将原组剩余时间、旧30秒条件修复或C9新源包当作继续运行许可。下一工具启动需有新的精确范围和有据检查方案；当前不绕过权限、不换工具盲试。新C967口/74字段仍仅静态，M3采样/行为TB与M1数学比较继续待真实候选输出。本次诊断记录不改变这些验收状态。
