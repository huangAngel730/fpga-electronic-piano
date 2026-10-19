# R13 A 合同包：最小决定表

版本 `M3_R13_CONTRACT_20261019_R01`；入口 `CONTRACT_INDEX.json`，机读原件 `OPEN_DECISIONS.json`。本件为 L0 静态组装，未运行合同检查、目标模块、仿真或设备；未改公共合同/TB。当前 R13 软件整包计划 SHA `729cb21bd4b759f7d5738bdc14964bee1eaf5da053eee20b4a278acf651357d3` 已获用户批准，无须重批同一范围。

|编号/负责人|已知事实|最小返回或保持状态|受影响范围|
|---|---|---|---|
|D01／M2|旧 TB 同槽两次负沿等待，D=1130660 或 D+1=1130661 尚未冻结；原案均保留。|选明确 core 正沿屏障后继或另一确定方案，返回新路径/diff/SHA、clock/reset/window/argv；未决定不改 TB。|真实 HDL finish；独立合成软件窗可另冻，不由此批准真实相位。|
|D02／M2|`audio_stable` 无已批准策略，ready 计划接诊断线，未证明 DUT 背压。|默认保留 null/理由及背压 PENDING；如需改变，交精确公开策略和受控影响。|对应真实稳定/背压验收。|
|D03／M1，接口改动才交 M2|63 字节/23 事件独立 plan 已存在；尚无真实 seq→accept→各 apply stage 因果映射。|交基于来源的完整64bit、epoch、generation、阶段 join；缺件时 apply_event_seq=null，不反推黄金。|真实因果映射与数学；不妨碍保留机械输入。|
|D04／M1执行，M2范围/准入|七INPUT及既定D4 manifest＋四流方向不变。M1 R13 bounded reader／semantics已有L0候选到件，旧R10整体reader另保留。|待M1精确输入/来源/资源/时限准入及54案/容量实测；实际reset/envelope/FRAME/plan/provenance等价绑定仍待核。CAP01明确GENERATOR_BINDING_PENDING，不可在时钟外预造fixture绕过。|候选已到不代表兼容/REAL/数学通过；不改M1、不重问命名或已签方向，不借M3预算代跑。|
|D05／M1|B0 只支持 settled 同时四lane；实际 PCM/FX 不能当黄金。|给同源受支持 profile/adapter/独立黄金；缺件 `PENDING_UNSUPPORTED_PROFILE`。|数学验收，非软件机械格式成立与否。|
|D06／M3总控|W须实际全后段≥1130662行/raw≥1398627657B；旧明文落盘容量不能直接放行。用户已确认转发DELIVERY全目录的所有无损卷及清单。|只剩核 A2 全产物物理几何、暂存/控制JSON、512MiB/1MiB/24GiB与32GiB空闲/8GiB余量；GitZIP≤32MiB放索引/小原件，大卷走已确认通道。实际卷名/大小/SHA生产后封存，M2_RECEIVED仍false。|W资源前置仍NO_GO；不再以缺通道选择单独阻断，不删产物降标准。|
|D07／M2准入、M3真实采集|工具清单及声明receipt不是动态闭包/可信原生执行；真实Pro/板/数学另缺。|保留PENDING；将来另准入后交同次raw/reset/END/双流/退出清理/动态依赖及物理原件。|真实HDL/数字/物理/板；本页不申请或启动它们。|

七个INPUT为 `mechanical_index/public_rows/raw_capture/independent_plan/frame_plan/reset_edges/provenance`；其生产者、schema、原件入口和当前consumer差异详见索引。M1任务模板SHA `d473350a15ec72c0a6c050dbb7012c71db02b0376065019ee64adfea7b3a55fc`；已签兼容方向SHA `6983eb4d96f81974490e98e2806a4657d423cd581bc37b62b792913a8f98c0e1`。此前将七INPUT与六OUTPUT比较产生的“第七命名缺口”已撤销，首版原件保留于私有历史目录。

R03到件记录：M1功能 `86cd5975f5679ad2db9da7b0d20d2892e76e76b1`，绑定 `7319fe670d3524252ac299e11f00d00ae52c9953`；总控已收静态36原件，收据 `code/output/m3_backend_stream_r13_20261018/INTAKE/M1_R13_NEW/M3_RECEIPT.json`。当前树检查点 `544f5af23fa427db0a931df719dc6135c75a180f`，R13已批功能基线e39、START00:00:26/截止05:00:26、旧消费均不变。这里只记录L0到件，不把M1发布权限或静态门禁当其54案／容量／数学执行许可。

已关闭事项直接复用：NoteOn 勘误为 E=成功 allocation、H=首次随后 CTRL_ON&&cmd_ready、无reset打断时C=H+1且最早E+2（M2已L0签收）；R12限定接收旧40复用＋新增2，不重跑42。原失败和消费不归零，原声明/原件不重写。R13 K/V/B/W/P0/P1/R、门禁和发布仅总控执行；本页不给新权限、不给M2签收、不启用审核员制度。
