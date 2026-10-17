# B双top对正式C6本体的静态绑定（当前源入口）

本次仅静态读ZIP/JSON/文件并核SHA，没有运行B builder/selftest/comparator、编译或仿真。C5缺头历史及已补齐的C5双top原包全部保留。

M2 C6源包180266字节，SHA `155177a23ae724a1c8d9a0ca3480781d0b76ae62f5a95f59c65a15a96e0d70e4`。C6 decision逐载荷SHA与本体全部核同；其71源、2头和9ROM共82件，与本窗口既有 `c5_dual_assembly/inputs/` 的同路径文件**逐字节相同**。C6正式携带 `include/sine_table.svh`、`include/sustain_controller_ports.svh` 和 `+incdir+include`，本轮不再向M2报缺头。

因此精确复用已交76源双top装配：C6的71源，加冻结旧frame_core/board、原wrapper、driver和最终TB五件。原双top `dual_compile.f` 已含相同include条件；78字面module无重复、唯一DDS leaf/sharedROM和9ROM及裸名alias的原静态证据保留。没有重装另一套top、没有改算法、端口或原B源码。

可直接使用 `INPUT_ORIGINALS/M3_R7B_C5_DUAL_SOURCE_20261017.zip`：206956B，SHA `8cdc01ccf36ee4a91d61ca270c076fcf8d20560465679a2a9b52e09f5ea0155d`。文件名保留其历史来源，本次C6_BINDING.json给出逐载荷等字节复用关系。相对清单基准仍解包inputs目录，top=tb_public_equivalence；原两份列表、driver/刺激/最终TB本体均已随双top包保全。C6决定与C6原包本体另在INPUT_ORIGINALS，不只提供SHA。

状态L0 / NOT_COMPILED_NOT_ADMITTED，执行准入为空。B末版comparator的`<=stop`变更继续L0未执行；旧15+4功能原件不重跑，不声称最终19全测。R08新角色C48项T及17项H由总控统一执行，不借它们重跑B或旧R6-6。HDL/EDA/硬件/本窗口新功能执行0，board_release_allowed=false，M2仍负责精确工具/组合/时限/输出的实际准入与最终签收。
