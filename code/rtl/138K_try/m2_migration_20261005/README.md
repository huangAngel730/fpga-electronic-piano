# 双平台迁移第一阶段

用户于2026-10-05授权：60K保留当前演示和备用；138K建立正式扩展工程；先迁移已验证四声部，完整综合/PnR/STA并核对实际引脚，再增量迁移T027、面板和效果器。

这里是M2独立迁移入口，不覆盖M3旧试验或60K正式top/CST/SDC。首次复现采用已提供资料中C版50MHz的`C_reset_route1`输入，保持原四声部V1/CC64及V0171已有Pitch/Mod和严格视觉链；没有加入新T027、K1/B按钮、效果器或拒收流水候选。已有Pitch/Mod属于该冻结输入，不能据此声称其新板音效已验证。

## 输入及工具

- GW5AST-LV138PG484AC1/I0，Device C；不能将C结果用于未经确认的B芯片。
- 工具为用户提供的`../tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe`，与本机原教育版CLI的SHA一致。
- `tools.zip` SHA-256：`1d5e0d7b944eae83f8eb972b9743c90599d674db743e8775add270cd0a47d4ea`，压缩554437900 bytes，实际4105文件/1388773901 bytes；CRC与逐文件SHA另保存在本机tools_import_receipt.json。工具本体不入库、不覆盖D盘原60K工具链。
- 原C50证据ZIP已在资料内，Git忽略的CST/SDC、GPRJ和完整报告由ZIP补齐。56份manifest输入SHA均匹配；prepare可在新电脑自动安全解出本阶段原件。
- 新工程独立复制47项源/约束、7 ROM、2头文件，仅重定位路径。保持50/25/125MHz、Setup uncertainty1ns/Hold0.550ns、原PLL适配、Bank5 reset/key 3.3V、R44C168[1][A/B]串行复位和route1。

## 使用

在仓库根目录：

```powershell
python -B -X utf8 code/rtl/138K_try/m2_migration_20261005/migrate.py prepare
python -B -X utf8 code/rtl/138K_try/m2_migration_20261005/migrate.py verify
python -B -X utf8 code/rtl/138K_try/m2_migration_20261005/migrate.py build
python -B -X utf8 code/rtl/138K_try/m2_migration_20261005/migrate.py assess
```

prepare/build均拒绝覆盖旧工程或重跑；build最多1800秒，不扫种子、不删旧结果。产物在本目录`output/C50_baseline`，被Git局部忽略；报告结果不是可下载许可。

## 放行边界

报告检查沿用完整时钟/CDC/复位门禁，138K引脚按真实表头读14端口，对照球位/Bank/IO_TYPE/VCCIO/差分对；不能用60K固定列号误读138K。除可单独证明的器件、BSRAM和Hold约束差异，保留其余旧门禁。B/C丝印、NEO底板接线和电气实物仍待核对。

即使零违例，也须明确Setup工程余量是否达到+0.5ns。之前的C50仅+0.025ns/Hold0/Removal+0.008ns，不能承诺更换板卡自动解决时序。当前没有上板、烧录或新功能批准。
