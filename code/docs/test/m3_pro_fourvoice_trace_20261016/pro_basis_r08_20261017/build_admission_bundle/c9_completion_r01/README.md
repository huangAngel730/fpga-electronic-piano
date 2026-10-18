# R8-06 C9 申请装配后继

状态为PREPARED_NOT_RUN。唯一写集是本包三根下c9_completion_r01；旧C6装配器、共用helper、旧收据和源包原字节不改。生产入口为software对应目录assembler.py，API `build_application(request, output_dir) -> dict`；CLI `--request APPLICATION_REQUEST.json --output NEW_DIR`。本窗口不导入/编译/执行候选，由总控在task-day4新台账中统一选择新用例。

output_dir必须不存在，且处于code/output/m3_c9_complete_d4_20261017；函数自行创建。返回artifacts的application/guard/reservation/dependency_graph/tools/resolved_plan/source/claim均为path/bytes/SHA描述符。申请始终execution_allowed=false、approved=false、authenticated=false，只返回PENDING_M2_EXECUTION_ADMISSION；不生成可信准入。

APPLICATION_REQUEST.json是非空实际C9实例：固定M2源ZIP/decision，读取既有SOURCE_APPLICATION_C9.zip中的72+driver/observer/TB=75单元、9 ROM、2头、两个同字节ROM别名和四份独立R6-2输入。每个M2 decision载荷及新增source/输入本体逐项核同；完整75清单顺序、incdir与精确payload集合不得偷换。实际67口/74字段合同独立绑定。旧C6硬编码不再用于本后继，错误C6基包必须拒收。

窗口实例是明确请求，不是已签真实相位：WINDOW_PROPOSAL.json从原1122320-cycle输入计划请求额外10×834-cycle尾段，给出非空CAPTURE/STOP/finish/sample/watchdog值并绑定原计划。expected finish仅为待M2核相位的提案，不能据数值出现称实际正确。argv逐字匹配唯一vlib/vlog/vsim模板，六个-g参数只能出现一次，其他top/list/source或重复覆盖均拒收。环境、预算、窗口原件身份、原spec与proposed_plan全字段比较；修改plan、同时改spec/plan但保留原窗口证据、自填批准或额外output均拒收。16GiB输出额度是本例的请求上限，不是磁盘容量证明；M2需审核实际资源和捕获相位后才能批准运行。

只复用旧01的inspect、旧03的固定SHA纯AST提取与consumer canonical/need比较原语、旧04的原子claim状态机和旧05文件身份/PE静态引用。函数AST不改写、派生SHA及原源身份进入未来产物，全部从字节加载，避开旧pyc。旧03完整audit仍是固定Python-worker范围，**没有调用它审核HDL，也没有放宽为真实HDL执行许可**；本后继是C9申请规范的纯重建/逐字段比较扩展。未启动worker、工具或DLL。

旧04以隔离的common命名空间把DOC证据域定位在本次out/r，原函数体和O_EXCL/full64hex/capture/plan/nonce绑定不变。claim绑定已解析cwd/output/env/budget的规范计划SHA，输出限定本次out。成功装配保持RESERVED，不冒称HDL成功；后续失败保存FAILURE并写FAILED_CONSUMED终态，不删除原件。该claim只是申请目录占用，不替代M2执行器的一次性真实消费授权。

工具先核固定路径及SHA的旧EXTERNAL_INPUTS.json，白名单本身也绑定进plan；仅使用其中声明的实际vlib/vlog/vsim及已有DLL身份，不扫机器、不复制安装文件、不探测版本/许可。IDENTITY_ONLY下动态/延迟装载依赖未知；工具文件一致不证明装载闭包、清理能力或执行安全。真实执行器、M2精确准入、参数readmem、真实捕获/数学/物理仍PENDING。首次HDL申请不要求预先已有该次真实trace。

十二个新案例包含实际C9装配、漏头、错基包、少75单元、plan/窗口篡改、自填批准、额外output，以及自审发现的设备名ZIP、重复-g覆盖、incdir篡改及外部白名单替换反例。只定义新差额；旧R7-A8+端口4及旧已过组不在本包重写或重跑。所有测试先存完整实际INPUT，再调用候选；失败保留档案。

静态自审已修：全部ZIP目标在任何物化前调用公共no_alias并核out/inputs内，拒Windows设备名/非规范尾点空格；argv由唯一完整模板核同。当前仅编辑、文件/JSON/哈希读取，无Python AST/语法检查、候选导入、功能测试、HDL/EDA/设备操作。
