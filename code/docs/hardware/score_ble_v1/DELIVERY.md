# T059部分阶段交付：源码候选＋桌面核心实测

2026-10-07。按扩展合同先交T058，再推进T059。**T059完整验收尚未完成**，不是无线实物PASS。
仅五处授权路径，T057 dc217ae封存只读，未改共享登记、原L/ROM、CDC、音频、顶层/约束/工程。

## 已实际执行

- MinGW GCC6.3.0：C99 `-Wall -Wextra -Werror -pedantic -O2`，核心/桌面入口exit0。
- 已有Vivado随附OpenJDK11.0.2：javac `--release 8 -Xlint:all -Werror`，Java核心/桌面入口exit0。
- `m3_score_ble_20261007_attempt6` 正向8522桥检查/660对原T057帧回放，exit0。
- 7357 Java/C联合模拟检查：512项4096B、同tick序、全读回、零力度、合法CRC/错身份、
  相同bytes有限重试、无回复失败、真实NACK拒绝、取消ABORT、断线清理、缓存/期限、
  全256字节、各种分片/合包/损片/重复/乱序、单事务、Java扫描门控/双目标函数；exit0。
- 两反例均compile0＋完整capture0（每个8522检查），checker1：CRC_REJECT／NO_PARTIAL_UART。
- 空/截断/乱码/计数篡改/参考篡改capture均checker1；非超时/编译错误代替。
  独立checker锁定完整公开刺激／reference plan SHA，不信任capture中的自报预期或计数。
- 首次Java子进程因环境JAVA_TOOL_OPTIONS提示被测试入口当错误；子进程移除变量后重跑。
  第二次反例host.c缺include搜索路径；补候选根include后重跑。最终attempt6原日志保留，
  旧attempt输出未覆盖；attempt5补齐原收发bytes，attempt6增加reference plan身份拒收，
  正式目标固件未试跑。
- 最终仓库门禁`m3_score_ble_20261007_gate3`九项PASS、exit0，Python语法196文件。
  gate2达到600秒未得完整结果，未当PASS；gate3改为直接文件记录原stdout/stderr并限时
  清理自身子进程树后完整通过。原T007辅助日志仍有既有sine/triangle相对ROM读取ERROR，
  门禁总结果为PASS；此处不把门禁总PASS扩写为这些音色资源或新整机音频已验证。

## 尚未执行／后续

缺ESP-IDF v5.4.2、RISC-V工具链、Android SDK35/build-tools34、Gradle8.9和JDK17。
已提供固件main.c和KotlinActivity/工程候选，但**未进行目标固件编译、APK构建或UI测试**；
无firmware.bin/APK SHA，不以桌面GCC/javac替代。SDK实际commit/工具链与依赖锁最终核验
须在目标构建阶段完成，源码当前只锁明确版本，不能声称可复现目标产物已经交齐。
可用SDK路径待用户提供；新增大型安装尚未获准，因此没有擅自安装或下载。
本轮L2仅指桌面共同协议核心，C3/Android系统层仍为L0候选；实体无线、手机权限、模块
两块身份、UART物理时序/电平、FPGA/音频播放/最终STA全部未验证，未操作任何设备。

## 复现

```powershell
python -B -X utf8 code/scripts/run_m3_score_ble_acceptance.py --output code/output/m3_score_ble_NEW
python -B -X utf8 code/docs/hardware/score_ble_v1/seal.py --verify
```

默认明确标`desktop_passed=true,complete_t059_passed=false`。目标编译可选参数见两候选README。
完整证据是evidence.zip.b64（原bytes压缩封存），索引raw_manifest.json，receipt内源/产物SHA；
verify重新核对SHA、原日志退出码和执行源身份，不编辑原stdout/capture。
