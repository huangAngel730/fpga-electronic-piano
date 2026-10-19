# R13-B 业务原件与消费索引

本包完成当前可取原件的静态编目，尚不代表 R13 完整软件、真实 Pro、数学、时序或板卡通过。只写任务单规定的七份索引；本角色未导入候选、编译、运行测试、调用 HDL/EDA/设备或执行 Git／网络操作。当前实际等级为 L0 静态源码、元数据和归档字节核对，历史 L1 软件结果仅索引、未重跑。

## 从哪里打开

先读 [ORIGINALS_INDEX.json](ORIGINALS_INDEX.json)：objects 按 ID 给出每件原件的准确入口、字节、SHA 和本次核验范围。repo 文件在固定 R12 基线的同路径；ZIP 对象先核外包，再打开准确 member。cohort.all_member_identities 另列同一正例全部140件成员；SOURCE_APPLICATION 内层97件源码／ROM／include／驱动／观察器／TB均已逐件读取并哈希，原声明为72基础单元、75含采集单元、9 ROM、2 header、2 alias。

已发布主容器为前一轮 frontend_close_r12_20261018/PUBLICATION_ORIGINALS.zip，16,361,886字节，SHA256 `065994d8bd286d7bf8e73c45d79a6e357df070f3a5abe56b8a056ee072fa86d3`。本包从其 RECOVERY_R02/RUNS/CD/worker/CASE01_ACTUAL 同一实例取件。该实例 capture_id=`C9_SYNTHETIC_NOT_REAL`，origin=`SYNTHETIC_SCHEMA_FIXTURE`，仅7行。FX／advance／input-apply三历史本例都是合法空文件；不把空历史或本例升级为全窗证明。输出物理成员完整前缀见索引。

## 七 INPUT 与六 OUTPUT

七项输入已有M1原合同：`mechanical_index/public_rows/raw_capture/independent_plan/frame_plan/reset_edges/provenance`。依据是 MATH_INPUT_JOB_TEMPLATE.json、c9_inputs.ROLES 和已签 CONSUMER_COMPATIBILITY_R11_20261018.json，均有精确原件身份。不存在“第七项尚未命名”的缺口。

D4数学生产者另生成六个输出文件：MATH_INPUT_BUNDLE.json、RECEIPT.json、MATH_ROW_INDEX.jsonl、FX_HISTORY.jsonl、ADVANCE_HISTORY.jsonl、INPUT_AND_APPLY_HISTORY.jsonl；前两者同为 M3_D4_C9_MATH_INPUT_BUNDLE_V1，四条JSONL没有逐行独立schema。RECEIPT只是附manifest描述符的生产回执，不是工具执行或M1/M2验收回执。17个REQUIRED_ROLES亦是第三个集合。

已有兼容决定已选定唯一未来适配目标：原D4 manifest及不改字节的四条流，不再申请改名或另造数学格式。现签M1仍整文件读取并要求rows[]；reset JSONL与窄reset投影、FRAME的cycles与frame_cycles字段、独立事件／配置plan的等价映射尚需负责方适配。本例的独立plan是显式合成空plan，首采样rst_n=1，不能补造低电平采样或独立事件。实际M1 CLI源码和参数入口、七角色逐项对应、拒收条件均在 [CONSUMER_LOAD_MAP.json](CONSUMER_LOAD_MAP.json)。未运行该CLI。

## 同源与历史边界

[DEPENDENCY_DAG.json](DEPENDENCY_DAG.json)给出原件至源码闭包、独立FRAME、raw／43投影／canonical／CSV往返／intake／calendar／serial／math／provenance的依赖；[CAPTURE_IDENTITY_BINDING.json](CAPTURE_IDENTITY_BINDING.json)绑定同一raw/reset/END/双流/plan/source/ROM/tool。12项声明SHA与实际原件相同。合成声明中的vsim argv没有被本例原件证明为真实执行，原件哈希相同也不证明执行真实性。

[POSITIVE_NEGATIVE_HISTORY.json](POSITIVE_NEGATIVE_HISTORY.json)保留旧40复用＋新增2证据、原S1/G/gate/prelaunch97失败、原计费及后继诊断。旧6540秒不返还，当前R13新5040秒及原05:00:26截止不因分卷或换窗口重置。旧W仅是前端容量且有私有D4替身，不能替代本轮实际后段全窗W。受跟踪R12元数据冻结早于最终Gate02／发布／S2，不能把其中PENDING误判成后来失败；后来终末实际回执及M2签收分别引用。M2已限定接受e39b36b9b7f956659f7fd5e3ca6dd57e5a34735b的R12前端软件，未整合、未签真实／数学／板卡。

M2上次未收到的外置FINAL_HANDOFF_MANIFEST.json现已在M3本地找回：80,791字节，SHA256 `498b707df48fdc51b96c9d265c39b97eae941fa4c64a776bd86e2822b8f6db95`；其外包17,270,092字节SHA与M2已收包一致。它与外包内80,488字节MANIFEST.json是两件原件。保留M2过去缺件／首次错比记录；找回不等于已重新送达，主窗口须把外置原件正文纳入本轮可取交接。

## 无损分卷与新交付

旧R12大流可从已发布ZIP内PARTS.json及21个gzip原件恢复。压缩卷体本次逐卷核过；连续offset／decoded长度之和为1,398,627,657字节。本次未重新解码该1.4GB流，decoded核验仍属历史生产证据。读取须验证每卷压缩与解码SHA，保持同一逻辑流的全局摘要、UTF-8／换行／行号／cycle／epoch状态，最终核总长和总SHA。旧大流是合成前端stderr容量证据，不是本轮真实raw或全后段W。

用户已确认沿用人工转发原包／无损卷：准确交付根是 code/output/m3_backend_stream_r13_20261018/DELIVERY，交付单位是该目录全部卷和清单。Git跟踪backend_close/EXECUTION_ORIGINALS.zip仍限32MiB，容纳索引和小原件，不冒称包含所有大卷。实际卷名、字节、SHA、逻辑偏移和成员映射必须由总控根据实际归档冻结；本索引不预造。通道已确认，但M2收件／接受仍PENDING，W仍须单独满足来源、前置组、512MiB内存、1MiB chunk、24GiB workspace、32GiB起始可用／8GiB保留及原时窗预算。

所有外部转发授权原件、找回的外置清单及ignored控制原件都有实际本地正文与身份；主窗口仍须纳入最终归档并补准确成员映射。本地绝对路径和哈希不能代替跨机原件。[MISSING_ORIGINALS.json](MISSING_ORIGINALS.json)逐项列责任人、影响范围和恢复条件。最终运行／发布／S2实际结果以总控backend_close与最终DELIVERY清单及接收回执为准；本包是有明确时间点的静态索引，不更新共享账、不提前签任何新结果。

## 新到件增补：M1 R13 静态36（B第二版）

已按交接ID M1-R13-R02-STATIC-20261018-01、功能提交 86cd5975f5679ad2db9da7b0d20d2892e76e76b1、接收方M3去重。绑定提交7319fe670d3524252ac299e11f00d00ae52c9953，当前源码检查点 544f5af23fa427db0a931df719dc6135c75a180f；批准功能基线e39与旧消费／原START／截止均不重开。接收单见ORIGINALS_INDEX中的m1_r13_M3_receipt；该记录的30个manifest引用由总控已核，本次只增量核36份新原件正文bytes/SHA及3份接收／安全FF／原读失败收据，原163项不全面重做。

新bounded reader、独立语义及54案规格已有L0候选源码，不能继续把“尚无适配源码”当现状。旧R10已签consumer未变；新入口为run_stream_math.evaluate，由worker_group准入，M1_R13_STREAM_JOB_V1只是作业控制包，不能替代或改写已签D4数学数据。新候选七条流是raw_capture/public_rows/line_index/row_index/fx_history/advance_history/input_apply_history，与旧七INPUT角色是不同集合；逐项映射见CONSUMER_LOAD_MAP新增candidate。

原7行cohort和所有旧source/raw/reset/END/双流/SHA不变；新M1合成schedule不会成为旧cohort或真实FRAME/finish依据。新候选54案、容量及数学实际运行均为0；CAP01仍明确CAPACITY_GENERATOR_BINDING_PENDING，M3实际几何、固定生成器接入和M1独立执行许可需齐全后才能按其本岗预算运行。M1静态发布许可不等于目标执行许可；M3已收静态源码不等于兼容、REAL、数学或验收通过。上游本机STATIC_HANDOFF.zip未取，不冒称已送达，入口采用当前Git树精确文件。

本次只增补B七文件及关联索引。首版HANDOFF.json保留不覆盖，首版七文件字节快照在code/output/m3_backend_stream_r13_20261018/roles/night3/B_STATIC_01_BEFORE_M1_R13，各SHA仍由首版HANDOFF绑定。旧段中“未来适配尚未实现”描述首版及旧R10状态；当前收到L0源码以本增补及新增candidate状态为准，测量／语义等价／真实准入仍PENDING。新交接收据另存HANDOFF_R02.json。
