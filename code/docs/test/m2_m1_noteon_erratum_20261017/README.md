# M1 Note On 单字段勘误：M2 限定接入

M1 已确认原 note_on_mask 定义把 allocation E 错当消费前一沿。本次只接受文字与源码语义的 L0 勘误：E 为成功 ALLOC_APPLY；H 为后续第一次 CTRL_ON && cmd_ready，reset 不打断时消费 C=H+1，最早 C=E+2，背压可继续推迟。Note On 不等于 sample advance 或 DDS 相位复位。

原语义、原 ZIP、四份 M1 RTL、C9 源包与 R10 DELIVERY_CONTRACT 保持原字节。SEMANTICS_BINDING.json 并引原 SHA 和仅改 /fields/4/definition 的后继 SHA；消费者同时读取该绑定与旧合同，不能覆写旧引用或把继承的旧 PENDING 元数据解释成实际验证。

M1_ORIGINALS 保留七份到件根文本，必要 CRLF→LF 变换逐项记账；USER_ORIGINALS 保留原 ZIP 和用户交接 MD，本体含源码快照、双流、旧包及全部失败历史。BYTE_AUDIT 记录本次 CRC/大小/SHA/源码锚点和历史回执核验，未执行附件脚本、旧十九方法或新的软件/HDL/EDA/设备组。

M1原Markdown中的inputs/相对链接指原ZIP内快照；在独占output展开原ZIP后查阅，不代表M1_ORIGINALS下有第二份inputs。本包来源中的绝对路径仅作证据索引，不作覆盖目标。原包299607B/SHA9c258467…9076b07，74成员/73清单；内嵌原R07的61成员/60清单，57个repo成员中52同字节、1已记CRLF→LF、4原bin仅ZIP。后继SHA为d853e8fc0818d153563bb2f2c9d971efcc8d8cd357b5a0c458779f677178ae0a。

M1当时七项blob读取失败及双流按身份保留，网络DNS/凭据/低速/404情况是其normalized报告，M2未重演该网络故障。本机七个指定对象均可读，本轮最终交接包附精确原提交对象、当前C9源包和R10合同；仍不能声称M1已收到或读过。

M2本轮文件核验首轮因ZIP原CRLF日志的行尾匹配失败而停止，原日志不改；初步多转义判断不准确，错误补丁未应用，经只读字节检查证实后用原CR兼容匹配一次完成。另一次文档生成调用因字符串定界在执行前失败、未写文件。失败helper及实际工具结果的normalized记录与纠正证据留在本轮output封存包，不消费R09或N10功能组。

关闭原待 M1 确认的 Note On 文字勘误。M1 不另造重复 ERRATA_NOTEON_R10；其余 R10 夜间组织、写集、时间盒、软件预算及旧 R09 消费保持。独立 plan 序号、audio_stable、真实同版数学输入及数字/物理/板测仍 PENDING，board_release_allowed=false。发布 SHA、精确树门禁和远端核验由后续实际发布回执给出，不引用旧门禁代签。

发布并发补充：门禁期间远端新增M3提交e394790b的432个文件，均在M3三根且与本勘误写集/验证记录无交集；现已到库，单独待M2限定复核，本次NoteOn接收不代签其软件/真实链。原两次本地提交、旧精确树9/9与失败推送已封存bundle；只在干净发布树重放本轮文字勘误，主树未重置/拉取覆盖。新精确树门禁与远端SHA另封。
