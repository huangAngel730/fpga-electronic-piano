# M2 R09实际执行与阻断交接（2026-10-17）

R09已从重启包恢复并真实执行。**当前PARTIAL，任务未完成，两个HDL单元均未获得L2 PASS，board_release_allowed=false。** 旧暂停段落只保留历史；不要重跑已消费组，也不要把残留vvp或TB中的PASS字符串当作成功。

| 项目 | 实际结果 | 消费 |
|---|---|---|
| 新owned Job执行器 | root引用释放后再核Job空；最后bytes复判；双流分别close；首BaseException保留；固定能力/身份/私有tmp | 本轮实现 |
| SW_01 | 8启动场景+3启动前拒收，exit0，4.393640秒 | 一次≤90秒已消费 |
| SW_FIX_01 | 目录枚举漏2个include/*.vams；仅改递归枚举和后继证明路径，5检查通过，exit0/0.948080秒 | 唯一≤60秒增量已消费；0夹具/HDL |
| UNIT01 raw compile | exit3221225477 (0xC0000005)，9.448011秒，stdout/stderr各0B | 唯一≤60秒组已消费 |
| raw VVP / boundary compile+VVP | NOT_STARTED | 不可把组剩余时间挪成新组 |
| 对应单元修复 | 尚无有据源码/入口修法，根因UNKNOWN | 一次≤30秒未用；条件未满足 |

新软件场景为正常双流、非零7、root退后子孙写流、超时子孙、日志越限、最终尾写越限、附Job前BaseException、首错同时回执失败；启动前拒收改argv/未知操作/重复步骤。负例通过指正确拒收或清理，不指进程退出0。首错+回执失败场景预期备用FINALIZATION_FAILURE，不能改写成完整回执。

软件证明绑定当前entry/runtime/fixture、冻结Job助手和本机Python EXE/DLL。最初SW证明保留；后继证明继承未变生命周期代码并检查唯一两行controller差异。工具应用侧绑定原26项与完整ivl目录36项并集50项；额外核HKCU/HKLM 32/64 Command Processor AutoRun及五EXE的.local/.manifest不存在。Windows API-set/SxS/loader和Python标准库作为当前平台边界接受，**没有证明完整动态闭包**。`vvp -M- -M fixed_IVL`及产物VPI绑定已实现，但本轮未到VVP阶段，不能写实际装载通过。

固定单元源为C7 raw leaf+TB，以及冻结pcm_result_hold/pcm_frame_buffer+C4 sidecar SHA40fd+boundary C7 TB。UNIT_01/source保存全部六源。C4/C7仍保留其本地历史版本，不在此次直接暂存/代发；包内C7_PARENT与六源是此次输入快照。已签准入是**单次历史准入**，当前CURRENT_RUN_OUTCOME说明已消费失败，不能复用。发布的entry为原执行记录，依赖本机固定路径及历史输入；其他checkout不得直接启动，应先以封包回读核同，再由新有效任务指定新范围/环境/额度。

实际编译argv/cwd/env/UTC在UNIT_01/raw_compile/START与RECEIPT；控制器双流在LAUNCH_UNITS。Job共5进程且最终active0、root句柄关闭、双流封存、输入前后SHA同。残留unit.vvp 4934B仅静读见版本/六VPI/尾表，SHA见RESULT；没有运行。访问冲突来源尚不确定；历史相同退出码、提权后成功记录均不能证明本次根因。应用事件日志读取被拒，未重试/换访问方式。

封包：`R09_ACTUAL_EVIDENCE_PARTIAL.zip`，1227614B，SHA-256 **f5d60754efc6cd1b97b204b4f77c0cb1b8bb397c6e77559a0ac95d885d6770c2**，128载荷；CRC和全部清单大小/SHA已回读。包含首次准入失败、修复前源码、原SW与增量、原编译失败、当前源码/准入、工具静态材料、C7父输入及重启来源。首个辅助失败记录命令引号SyntaxError、若干只读路径拼写/检索错误无产品修改，已记录；它们不计为编译修复或三次有效解决尝试。

下一动作是形成**独立、有界的编译诊断范围和可用执行环境**后再启动工具；现额度不支持无变化重试、换工具、放宽时限或绕过被拒操作。R09保持PARTIAL，不把软件部分单独改成整项完成。本次仅按需新执行许可/环境决定节点集中封存；是否发布取决于本任务精确文件的九门禁，发布前无编号，发布结果另有独立回执。

M3继续其最新R08任务的既有授权软件工作，不能把本轮安全执行器证明当作M3 plan_adapter或旧P7许可。M1十九语义/apply/config/audio_stable、真实Pro公开trace/时基/PCM/身份和板测仍待。本轮未启用审核员/预审员；M2自审，M3消息待用户转发尚未送达。

参考：[微软Job计数语义](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)、[Icarus VVP参数](https://steveicarus.github.io/iverilog/usage/vvp_flags.html)、[产物版本所指官方driver源码](https://raw.githubusercontent.com/steveicarus/iverilog/a690e3a03/driver/main.c)。前两者仅支持机制实现，均不代签本机实际HDL成功。
