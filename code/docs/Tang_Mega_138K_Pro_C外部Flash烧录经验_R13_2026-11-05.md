# Tang Mega 138K Pro C 外部 Flash 烧录经验（R13，2026-11-05）

本文记录 R13 在 Tang Mega 138K Pro C 上经实机执行的外部 SPI Flash 烧录步骤，供 M3 后续复用。结论仅适用于本文记载的板卡、位流和 Gowin Programmer 版本；换版本、器件或板卡后，须重新核对工具报告和操作映射。

## 本次输入与目标

- 板卡：Tang Mega 138K Pro C。
- FPGA：GW5AST-138C，JTAG ID `0x0001081B`。
- Flash：Programmer 识别 ID `0xEF4018`。
- Programmer：Gowin Programmer V1.9.12.04 (64-bit)，本机命令行位于 `D:\Program Files (x86)\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer_cli.exe`。
- 输入包：`N32_C1_R13_李萨如放大与标题_转发包_20261105.zip`，SHA-256 `f659555efc082d932e3bd76a4b4dc6d9435a6bc50c06c21939fe6325ef0cf188`。
- 位流：`N32_C1_R13_LISSAJOUS.fs`，42,340,876 字节；SHA-256 `0b994492ecd4ac4a6e504568e2a71ed9f048ef572ceea56ac03193f4bd26363c`。
- 位流有效配置数据写入范围：`0x000000`–`0x0509E00`（Programmer 实际输出）。
- R13 包内构建回执记载 STA 通过，但烧录前 `board: NOT_RUN`；本次写入和 Flash 内容校验完成，断电重上电后的自启动及 HDMI 显示仍需单独实测。

## 实际烧录流程

### 1. 核对包和位流

解压到本地工作目录后，先按包内 `SHA256SUMS.txt` 核对文件，确认仅使用包中的 `.fs`。记录 `.fs` 的 SHA-256；不要仅凭文件名选码流。本次包清单校验 262 个文件、0 个哈希不匹配。

```powershell
Get-FileHash -LiteralPath '<位流完整路径.fs>' -Algorithm SHA256
```

### 2. 新鲜扫描下载器和 JTAG

```powershell
& $tool --scan-cables F
& $tool --device GW5AST-138C --scan --cable-index 4 --location 9009
```

本次扫描在 USB location `9009` 发现 `USB Debugger A/0/9009`，其 JTAG 链只有一颗器件，ID 为 `0x0001081B`。另一个 location `9010` 本轮未用于编程。重新操作时应按当前扫描结果选择线缆和 location，不要把 `cable-index 4` 或 `9009` 当成跨电脑固定值。

### 3. 写外部 Flash

本机工具目录中的 `data\resource\aroravgaobridge.json` 将 JTAG ID `0001081B` 的封装候选列为 GW5AST-138B/C。以完整器件选择 `GW5AST-138C` 后，Programmer 实际把 operation index `53` 解析为 **`exFlash Erase,Program Arora V`**。该操作会擦除外部 Flash 后再编程，起始地址为 `0x000000`；它会覆盖该配置区域原有内容。

```powershell
$tool = 'D:\Program Files (x86)\Gowin\Gowin_V1.9.12.04_x64\Programmer\bin\programmer_cli.exe'
$fs = '<已核对 SHA-256 的位流完整路径.fs>'
& $tool --device GW5AST-138C --operation_index 53 `
  --cable-index 4 --location 9009 --frequency 2.5MHz --fsFile $fs
```

本次 Programmer 日志确认：`Target Device: GW5AST-138C(0x0001081B)`、`Operation "exFlash Erase,Program Arora V"`、Flash ID `0xEF4018`、起始地址 `0x000000`、结束地址 `0x0509E00`，随后显示 `Program Flash finished`、`Finished`，进程退出码 0。

### 4. 单独执行写后校验

写入操作本身不含 Verify。对同一 `.fs` 再运行器件专用的 `exFlash Verify Arora V`（本机此版本 operation index `66`）：

```powershell
& $tool --device GW5AST-138C --operation_index 66 `
  --cable-index 4 --location 9009 --frequency 2.5MHz --fsFile $fs
```

本次输出 `Operation "exFlash Verify Arora V"`、Flash ID `0xEF4018`、`Verify Flash successfully`、`Finished`，退出码 0。校验必须针对刚刚写入的同一位流，并保留完整工具日志、命令行和退出码。

## 关键经验与踩坑

1. **按 FPGA 精确型号使用 Arora V 外部 Flash 操作。** 不要把 SRAM Program、embFlash 或普通 Generic exFlash 操作当成同一流程。Gowin 用户指南列出 GW5AST-138C 的器件专用 Arora V 操作；本次本机工具实际日志确认了 operation 53 和 66 的名称。官方 Programmer 指南也说明 GAO Bridge 擦写操作会先擦除外部 Flash 再写入，带 Verify 的操作还会读回校验。[Gowin Programmer 用户指南](https://cdn.gowinsemi.com.cn/SUG502E.pdf)
2. **命令行帮助的通用编号说明不足以确认 Arora V 操作。** 本机 `--help` 对部分编号显示为通用/5A 描述；以 `--device GW5AST-138C` 实际运行时 Programmer 打印出的器件专用 `Operation "... Arora V"` 为准。若日志解析出的操作名称与预期不符，应立即停止，不要继续擦写。
3. **先核地址与写入范围。** 本次文件有效配置数据落在 `0x000000` 起，工具显示末址 `0x0509E00`。板卡资料记载有两颗 128 Mbit Flash；但应以当前选中的 Flash ID、工具容量检查和本机实际日志为准，不要仅根据板卡总容量推断分区/启动布局。[Sipeed Tang Mega 138K Pro 文档](https://wiki.sipeed.com/hardware/en/tang/tang-mega-138k/mega-138k-pro.html)
4. **校验成功不等于上电启动/功能验收。** 校验只说明 Flash 内容与输入位流匹配。完成后需按板卡安全流程断电再上电，观察 DONE/HDMI/目标功能；未看到实机结果前不能记作启动通过。本次断电启动结果尚待 M3 补录。
5. **保护现场条件。** 依项目硬件安全要求确认同一块板、接线正确、供电稳定、操作者在旁；音频输出接有源输入并先将功放音量调低。外设插拔须先断电。擦写 Flash 是会覆盖原配置的操作，先保存原始位流和回执。

## 本次验证等级与证据

- 包清单/哈希：262 项通过，0 不匹配。
- 新鲜下载器扫描：通过；location 9009 可用。
- JTAG 扫描：通过；一颗器件，ID `0x0001081B`。
- Flash 写入：Programmer 报告完成，进程退出码 0。
- Flash 读回校验：`Verify Flash successfully`，进程退出码 0。
- 断电再上电自启动、HDMI 与功能：**待实物观察**。
- 仓库证据见 [Flash 写入与校验回执](evidence/r13_flash_20261105/FLASH_PROGRAM_VERIFY_RECEIPT_20261105.json)和 [主开发版本交接](MAIN_DEV_HANDOFF_R13_FLASH_2026-11-13.md)。SRAM/JTAG 会话保存在本机 `code/output/n32_c1_r13_lissajous_sram_20261105_r01/SESSION_20261105_163800`。

## 给 M3 的简版结论

本次已在 Tang Mega 138K Pro C / GW5AST-138C 上，以 Gowin Programmer V1.9.12.04 将 R13 的 `N32_C1_R13_LISSAJOUS.fs` 写入外部 Flash：写入用器件专用 `exFlash Erase,Program Arora V`（index 53），同一文件随后用 `exFlash Verify Arora V`（index 66）校验，二者均退出码 0，Flash ID `0xEF4018`，配置数据地址从 `0x000000` 到 `0x0509E00`。请补做断电再上电启动和 HDMI 实测，并把实测结果与该回执关联；不要将工具校验等同于硬件功能通过。
