# M2 执行器安全软件后继：R01/R02/R03 原始证据

## R03 当前取消异常修复及单项实证

R02在`except Exception`内清理未归属根，仍会漏掉附着前`KeyboardInterrupt`/`SystemExit`。根M2另给`LOCAL_EXECUTION_SCOPE_R03.json`单项、90秒内许可后，R03把任何本次已创建未附着根的`Popen`持有句柄kill+wait移到`finally`；记录原`BaseException`并继续向上抛出，不冒充执行成功。原R02源码已先按SHA保存`SOURCE_R02/owned_executor.py.txt`，清单保存`FILE_IDENTITIES_R02.json`，R02原ZIP按字节保留。

唯一R03命令：

```powershell
python -B -X utf8 code/build/138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017/targeted_fix_r03.py
```

实际退出0、0.098566秒，`PASS_ONE_TARGETED_BASEEXCEPTION_FAULT`／`L1_ONE_SOFTWARE_BASEEXCEPTION_FAULT_ONLY`。`RUN_03/PRELAUNCH.json`在启动case前冻结最终executor、R03脚本、dummy、Python、helper，组前后五项核同。注入附着前`KeyboardInterrupt`后，根退出1/句柄signaled；Job未归属，根以本次`Popen.kill_and_wait_current_handle`清理；原异常实际向上抛出并由外层断言捕获。原双流均0B，没有child/grandchild/ESCAPED文件。原错误保留在逐case收据，组PASS只表示这一预期故障被正确清理和传播。

最终executor SHA：`86227ae2637adf270df056b30ad67c751cb930daad50d1eb788f76228a090979`；R03脚本SHA：`bccfb2978ac28368c164e76b6c887ea3121e8c0e40fb4cb56af5fa4ecbc0a98b`。

**验证关系**：R01旧SHA为五个行为场景＋拒绝命令；R02另一SHA仅补两项普通故障；R03最终SHA仅补一项BaseException故障。没有重跑R01/R02，不声称最终版全组覆盖；SystemExit路径仅共用finally静态可核，未另实跑。三次许可均已消费，P7继续`BLOCKED_EXECUTOR_GUARD`，真实HDL/EDA/设备均未运行，不证明所有可能OS故障或全局orphan已清理。

当前原件包为`M2_EXECUTOR_GUARD_SOFTWARE_SUCCESSOR_20261017_R03.zip`及包外`PACKAGE_RECEIPT_R03.json`；R02原包另保留。原双流/SOURCE_R01/R02以包内字节为权威，发布只取`PUBLICATION_CANDIDATES.json`白名单，不直接暂存这些可能被LF正规化的原件。以下R02/R01文字为原阶段记录，不能改读成当前全量回归。

## R02 历史修复版本及定向实证

R01静态自审发现：挂起`Popen`之后先写启动元数据、后绑定Job；写失败时可能留下未归属的挂起根进程。R02把Job绑定/恢复放在后续启动元数据写入前；任何已创建但未成功归属的根，异常路径均用本次持有的`Popen`句柄kill+wait，最终再核根句柄已signal。旧P7/helper原件及旧PID均未动。

根M2另给`LOCAL_EXECUTION_SCOPE_R02.json`的90秒内、两case定向复查许可后，实际只运行一次：

```powershell
python -B -X utf8 code/build/138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017/targeted_fix_r02.py
```

实际退出0、0.118751秒，`PASS_TWO_TARGETED_SOFTWARE_FAULTS`／`L1_SOFTWARE_FAULT_INJECTION_ONLY`。`RUN_02/PRELAUNCH.json`在任何case启动前冻结executor、定向脚本、dummy、helper、Python五项，组收据前后同SHA。两case的预期错误及真实空双流（均0B）原样保留：

| R02定向case | 真实结果 |
| --- | --- |
| metadata_write_failure | 注入`INJECTED_LAUNCH_METADATA_WRITE_FAILURE`；Job归属已成功，关闭Job后自身句柄`wait_result=0`、根句柄signaled，根实际退出0。退出0不当作功能正例，只核预期故障与清理。 |
| before_attachment_failure | 注入`INJECTED_FAILURE_BEFORE_JOB_ATTACHMENT`；未归属根仅以本次`Popen.kill_and_wait_current_handle`终止，根退出1且句柄signaled。 |

当前executor SHA：`1cd67eaeed4195b12dbfe62898fbde28ec46908fdceea89e1574111c04f3b68d`；定向脚本SHA：`6bcebaad1e7175a18e195604511376edf69012663e18627fc5e65f7fae248c5b`。R02没有全面重跑R01五组，不把旧5组直接称为最终新SHA的全量通过。旧受测executor经R02反向差异恢复至`SOURCE_R01/owned_executor.py.txt`，保存前按RUN_01启动收据核11209B与SHA完全同；`RESTORATION_RECEIPT.json`明确它是后恢复文件、非运行当时已保存副本。

两组均已消费；P7继续`BLOCKED_EXECUTOR_GUARD`，Pro/HDL/EDA/硬件仍未运行。以下保留R01形成时记录。

R02封包入口为本目录`M2_EXECUTOR_GUARD_SOFTWARE_SUCCESSOR_20261017_R02.zip`，输入为当前`FILE_IDENTITIES.json`列出的全部文件加清单本身，封包与包外`PACKAGE_RECEIPT_R02.json`不递归列入自身载荷清单。压缩后按原件逐成员读回核验；根M2另核最终发布树。说明补丁曾因原文空格匹配失败而一次原子拒绝，未产生修改；按实际原文修正一次成功，不涉及执行器代码/双流重跑。

## R01 历史软件组

本目录是新建独占证据写集；`LOCAL_EXECUTION_SCOPE.json` 在实现及运行前落盘，限定一组不超过90秒的自写Python dummy。旧P7、旧T052自测和旧消费额度均未运行或恢复。

唯一实际命令：

```powershell
python -B -X utf8 code/build/138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017/selftest_once.py
```

实际退出0，软件组3.579587秒，`PASS_SOFTWARE_ONLY`／`L1_SOFTWARE_PROCESS_CONTROL_ONLY`。`RUN_01/RECEIPT.json` 是组原收据，逐case各有启动前身份、挂起启动PID、原始stdout/stderr、终态/清理收据；没有执行失败，本目录不编造失败原件。

| case | 实际结果与边界 |
| --- | --- |
| normal_exit0 | 退出0，0.174799秒；原双流分别含`DUMMY_NORMAL_STDOUT`/`DUMMY_NORMAL_STDERR`。 |
| error_exit7 | 预期退出7，0.127170秒；原双流分别含`DUMMY_EXIT7_STDOUT`/`DUMMY_EXIT7_STDERR`，非零退出保留原状。 |
| timeout_parent_child_grandchild | 2.508137秒，timeout=true，根退出1；同一新Job捕获3个进程句柄，`TerminateJobObject`后3个句柄`wait_result=0`。 |
| parent_exit_child_grandchild | 根先正常退出0，0.436682秒；Job内仍有2个后代，关闭最后Job句柄后，两句柄均`wait_result=0`，未用PID终止。 |
| observed_log_limit | 阈值65536B，实际stdout为98326B才停树，0.124119秒，根退出1；`TerminateJobObject`，其自身句柄终止已核。**这是检测后停树，不是硬字节上限。** |
| deny_unapproved_tool | validator静态拒绝Icarus、Gowin及未知dummy模式3种；CLI原stdout与退出2一并保留，未授权进程启动0。 |

源码身份：

| 文件 | SHA256 |
| --- | --- |
| owned_executor.py | `97a2cfaaf0250e81bca2474da57d7bd430375c429dec1507f1394ad6122e0534` |
| selftest_once.py | `3eca4ffd548a71287f61efde6425d98757e8f7096fcc7a3b8592a87037cce66c` |
| software_dummy.py | `efb1fd478fe3c7ba043f04bce9b795991b37c9d4c185c60ff4bdf842f5831b66` |
| Python工具 | `388fe2cffda8a134e7d7dc4e978f7c478857ece6b69694daecbed25e51ec633a` |
| 只读Windows Job helper | `5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b` |

每个启动前后executor/dummy/Python/helper身份均同。输出组排他新建，重复执行会拒绝已有目录。`-B`保证导入旧helper不在其目录写`__pycache__`。

**自检主脚本身份边界（运行后补充）**：`RUN_01`启动前/后快照只包含executor、dummy、Python与helper四项，不包含`selftest_once.py`本身。上表selftest SHA仅为本轮运行后的当前封存值，没有独立启动前后哈希原件，不声明其before=after已实证。不为补此项重跑软件组，也不回填或修改旧START/逐case/组收据。补充说明见`SELFTEST_SOURCE_IDENTITY_BOUNDARY.json`；初版清单按字节保留为`FILE_IDENTITIES_INITIAL.json`，当前清单另刷新。

CLI没有真实Pro/HDL/EDA/任意命令入口。新安全软件组不是P7重试、不证明全局没有其他orphan、不提供真实Pro工具许可。P7仍`BLOCKED_EXECUTOR_GUARD`，完整链仿真、实际工具启动异常、Job分配失败、Pro源/ROM观察映射、综合/PnR/STA和板测均未由本组验证；`board_release_allowed=false`。后续真实执行须根M2另绑定精确源/工具/路径/预算和实际许可。

根M2另做旧三PID只读存在核验，本组没有使用历史PID，不用其结果代替全局清理事实。未提交／未推送，由根窗口决定本任务统一发布；未向M1/M3或审核窗口发消息。
