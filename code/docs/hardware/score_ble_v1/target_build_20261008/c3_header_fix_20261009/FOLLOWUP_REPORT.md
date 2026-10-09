# D041 C3追加构建：真实目标编译通过（待M2复核）

2026-10-09。用户明确授权「自行追加直至成功，其他按规定要求」后，追加一次
环境／路径纠正构建，在全新直接输出目录成功；没有追加任何业务修复。
本文件接续原 REPORT.md，不覆盖原失败报告、收据和封存包。

## 实际结果

- 基线 HEAD：develop ce5df51，包含6c8e0b8及D041授权。
- C3 IDF build：exit 0，67.343秒；runner exit 0，76.031秒，未超时。
- 输出：code/output/m3_t059_target_20261009_c3_header_02；单次限1800秒。
- 状态 TARGET_COMPILED_ONLY，申请目标编译L1子阶段复核，不关闭完整T059。
- main.c.obj 实际生成100008bytes；真实main.c进入compile_commands及最终链接。
- bin 570112bytes，SHA 298fe1b3073f7874dd9412f2995b57a4fd4dfefd3a86f48a381271968eae85b5。
- elf 7329228bytes，SHA 2af24c2e5d6aee8b817577f16d9ef6ada32f8e3b574ebfd5f088536badfa7b2c。
- map 4911284bytes，SHA a0beaf6eec8a1dd12000ac0f3218ecc104b2b636e404eb34da50c6a32f15c3ba。
- sdkconfig SHA 4c4311855086a5844f21f46c11f6b94c2b1fefe339f98381ced910c36cb89675。
- bootloader、partition-table、完整命令、stdout/stderr、工具/配置/源SHA及产物都随新包交付。

## 修版身份与环境纠正

main.c仍仅在host/ble_hs.h后新增#include "host/util/util.h"，LF新SHA
c7e46b813e9f51cbaefcc658912bd629bd45d74f8ad18f85b1aa330ba5d97a17。
去掉新增28字节逐字节恢复旧主文件，其余9功能源匹配批准值；旧baseline/profile不改。
source_config_unchanged及runner_profile_unchanged均true；全部原身份/版本检查保留。

旧失败header_01来自代理未完整导出IDF环境及嵌套长路径。追加仅增加
invoke_export.py/export_build.cmd，真实调用已安装SDK的export.bat；ESP_ROM_ELF_DIR
导出到E:/FPGA/SDKs/espressif/tools/tools/esp-rom-elfs/20241011。
旧出错.d路径273字符，新路径230字符；本次相同SDK源码编译通过。
未启用全局长路径、未改SDK、未改编译错误等级或sdkconfig.defaults。
core.fileMode=false仅为当前子进程Git环境，忽略Windows ZIP执行位差异，不忽略内容差异。

工具仍为ESP-IDF v5.4.2（f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0）、
GCC14.2.0 esp-14.2.0_20241119、CMake3.30.2、Ninja1.12.1、Python3.11.2。
实际SDK路径E:/FPGA/SDKs/downloads/20261008/esp-idf-v5.4.2/esp-idf-v5.4.2；
工具E:/FPGA/SDKs/espressif/tools，精确路径、ROM ELF及工具SHA在新收据。
25个递归子模块及SDK内容检查通过。stderr有既有console多选提示，以ESP_CONSOLE_NONE
为最终选择，原日志保留，不改默认配置或把提示隐去。

## 复现及证据边界

在仓库根目录用已安装IDF Python运行invoke_export.py，指定两个互不嵌套、尚不存在的
code/output/m3_t059_target_*直接子目录。例如：

```text
E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/docs/hardware/score_ble_v1/target_build_20261008/c3_header_fix_20261009/invoke_export.py --output code/output/m3_t059_target_20261009_header_export_03 --target-output code/output/m3_t059_target_20261009_c3_header_03
```

这是复现命令示例，_03未执行，不冒称第二次成功构建。实际_02完整命令在收据。
新封存脚本seal_success.py仅核验、解析已有产物及打包，绝不调用build/flash。
selected evidence ZIP含真实bin/elf/map，Git文档只保留小型收据/日志载体与SHA，不提交整个build。
新包同时带旧失败ZIP，旧证据不回填。13项profile身份自检与其执行源码SHA一致；
新增启动器源码单独记录SHA。最终九门禁结果及包SHA见success_manifest.json。

不重复APK、波形或1128桌面事务；原精确debug APK已由M2接受目标编译L1。
未提交或推送本轮改动；共享状态/任务看板/接口/FPGA正式工程均不改。
未安装工具或APK、未打开串口、未烧录、未接FPGA；无线/实体传输、真实Android回调、
真实FPGA ACK和整机STA仍未测。下一步由M2复核本次C3编译子阶段并统一登记。
