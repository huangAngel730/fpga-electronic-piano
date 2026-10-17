# R7-B 软件准备完成，TB待编译

状态SOFTWARE_READY__PENDING_M2_ASSEMBLY_AND_HDL_ADMISSION。新TB/装配为L0，比较器/首差异/UART解码为L1新软件夹具；真实等价未运行，board_release_allowed=false。

RUN_01：15项新检查符合预期，组exit0，0.531秒，输入前后SHA一致。该版只检查40MHz采样，后由总控发现95–100ns沿间异值/X漏覆盖，不能作为完整外部行为等价检查器签收。全部首轮源/原件保留。未重跑R06旧组，无HDL/EDA/设备。

唯一允许RUN_02修复增量：增加公共pins变化时postponed稳定事件流、起点anchor、唯一事件结束标记，CLI强制--events。4项新定向检查（沿间相等、PA脉冲、TMDS脉冲、X）符合预期，组exit0，0.187秒，首差异95000ps；未重跑首轮15项。随后只读自审发现stop timestamp的严格<会漏尾拍NBA后差异，最终改为<=；此最后一处边界修订仅静态核读，**没有再次执行测试**，不称最终版19项全量通过。B两组已消费完，不借D组补测。

首轮装配原件在RUN_01/products/assembly：原69清单按R06C3替换，保留9ROM与clock stub身份；其TB仍为首轮冻结源。最终事件修复源码需M2重新冻结装配，不能拿旧stage冒充最终版。dds_oscillator本体在原archive但未列入原69，不擅自添加；结果PENDING_M2_DDS_LIST_DECISION，不冒称真实编译失败或闭包通过。两份子清单不能单独编译本双top TB。

同外部输入/固定起相位/1200–12000000拍窗口与允许差异表见CONTRACT.md；旧38obs全部NOT_PUBLIC，不改旧源、不读私有层级。不完整STAT保留PENDING；软件合成相等不是Pro实际等价。M2下一步决定精确DDS列表、clock stub及真实编译组合/工具许可，随后才运行TB和比较真实原件。

两份RUN_SPEC均在启动前冻结输入/依赖与case，RUN_01/02含源快照、argv/cwd/UTC/PID、原双流、消费、逐产物SHA。运行时枚举不代表独立证明全部动态DLL闭包。初组1/1、修复1/1已消费，共0.718秒；没有意外功能进程失败，静态发现与最后未执行边界修订如实保留。未提交/推送，由总控统一收口。
