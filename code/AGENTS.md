# 代码目录协作规范

本文件适用于 `code/` 下全部内容。开始工作前必须同时阅读根目录 `AGENTS.md` 和 `code/docs/协作入口.md`。

## 岗位代号

本项目使用 M1、M2、M3 三个岗位代号，定义见 `code/docs/角色分工.md`：

- M1：音频算法、验证与竞赛交付负责人。
- M2：FPGA 技术与系统集成负责人，兼任技术与集成负责人。
- M3：实体硬件、交互与上板验证负责人。

子目录局部 `AGENTS.md` 中的岗位名称与本文件保持一致。若发现仍有旧称谓“硬件一、硬件二、软件”，以 `code/docs/角色分工.md` 为准，并尽快修正该文件。

## 共同规则

1. 模块通过文档化接口连接，不读取其他模块内部寄存器或层级路径。
2. 公共类型、参数和接口只允许在接口变更获批后修改。
3. 新增 RTL 必须同时新增或更新自检 testbench。
4. 音频算法必须具有 Python 参考模型或明确的数学参考结果。
5. 任何声称完成的模块必须给出运行命令、PASS 结果和未验证项目。
6. 不提交大型波形、临时缓存和厂商自动生成目录。
7. 板级约束、接线表和引脚文档必须同步变更。
8. 报告状态必须给出 L0 至 L7 验证等级，不得跨级描述。

## 默认写入边界

**2026-09-16 起按 D025：复核人统一为 M2，M2 自己主责的目录标记为「自审」。**
本表只界定**谁可以改**；它不表示需要按分支隔离——三人一律直接推 `develop`。

| 目录 | 主负责人 | 复核人 |
|---|---|---|
| `rtl/audio/`、`rtl/synth/`、`rtl/voice/`、`rtl/mixer/`、`rtl/effects/` | M1 | M2 |
| `model/`、`docs/test/` | M1 | M2 |
| `rtl/audio_out/`（I2S 数字发送） | M2 | 自审 |
| `rtl/common/`、`rtl/board/`、顶层模块、公共接口文件、构建入口 | M2 | 自审 |
| `constraints/`、`sim/` | M2 | 自审 |
| `rtl/input/` | M3 | M2 |
| `software/`、`scripts/`（串口、仪器、采集） | M3 | M2 |

补充约定：

- I2S 数字发送属于接口时序与约束，归 M2；PCM 数据格式和位宽要求由 M1 提供。
- 数字效果器（延迟、合唱）属算法，归 M1；跨采样率切换和跨时钟域部分由 M2 参与。
- `rtl/common/`、顶层模块、公共接口文件和构建入口属于共享区：**标「自审」不等于
  可以随手改**，改动前仍须按 `code/docs/变更与决策流程.md` 提变更说明。
- 软件任务积压时按 D010 分担，分担后仍由 M1 负责算法定义与最终验收。
- 需要跨目录修改时先停止，列出影响并取得授权，不得自行扩大写入范围。
- **四处共享文件改动前先在群里说一句**：`rtl/board/electronic_piano_top.sv`、
  `rtl/common/audio_defs_pkg.sv`、`constraints/electronic_piano.cst`、
  `docs/模块接口规范.md`。这是取消分支隔离后的替代保障之一（D025 §3.3）。

## 推送最低条件

**原称「合并最低条件」，2026-09-16 起改名**：不再有功能分支合并动作，改为直接推 `develop`（D025）。

- **推送前运行 `.\code\scripts\check_repo.ps1` 且全 PASS**（当前 8／8、退出码 0）。
- **推送前先 `git fetch`；取号前先看 `develop` 上的最新一行。**
- 模块测试自动 PASS，且测试覆盖复位、边界和至少一个异常场景。
- 无新增未解释 lint 错误。
- 接口和参数与 `code/docs/模块接口规范.md` 一致。
- 更新任务状态，并在 `code/docs/验证记录.md` 追加**任务自身的验证等级**行。
  注意区分：**任务完成的验证记录行是必需的**（它是验证等级的唯一记录）；
  **复核动作本身不强制留痕**，只有复核发现问题时才补一行。
- 涉及时钟、复位、CDC、FIFO 或引脚时，完成对应专项检查。
- 禁止 `git push --force`；回退用 `git revert`。

## 脚本编写约定（PowerShell）

**本机默认 `pwsh` 是 Windows PowerShell 5.1 Desktop，不是 PowerShell 7。**
它把无 BOM 的 UTF-8 源文件按 ANSI（GBK）解码，且把原生程序的 stderr
当作致命错误。这两点会让脚本静默失效或直接报语法错误。

实际发生过的事故：`check_repo.ps1` 含 10 处中文路径字面量，
在 PS 5.1 下 `.\code\` 被解码成 `.\浠ｇ爜\`，引号失配导致整个脚本
无法解析——即此前所有合并检查实际从未执行。

因此 `.ps1` 脚本必须遵守：

1. **脚本源文件保持纯 ASCII。** 注释、字符串、提示信息一律用英文。
   需要输出中文时，从数据文件读取，不要写进脚本源码。
2. **需要中文路径时，用码点构造**，不要写字面量：

   ```powershell
   $codeDir = [char]0x4EE3 + [char]0x7801   # 代码
   . ".\$codeDir\scripts\enter_fpga_env.ps1"
   ```

3. **调用原生程序时把 `$ErrorActionPreference` 临时降为 `Continue`。**
   `iverilog`、`git` 等把警告写到 stderr，PS 5.1 会据此抛出
   `NativeCommandError` 并中断脚本。判断成功应以产物或退出码为准，
   不要以"有没有 stderr 输出"为准。
4. **非 ASCII 路径传给原生 exe 会被截断。** 例如把
   `D:\...\嵌赛FPGA\...` 作为参数传给 `iverilog`，PowerShell 可能只
   传出 `D:`。编译这类工具前先把源文件复制到 ASCII 临时目录，
   见 `scripts/run_t019_sim.ps1` 的做法。
5. **不要依赖 BOM 修复。** 环境可能拒绝写入 BOM；纯 ASCII 是唯一
   在两种 PowerShell 下都可靠的做法。
6. **git 必须改用 Windows 原生 OpenSSH。** Git for Windows 自带的
   `C:\Program Files\Git\usr\bin\ssh.exe` 是 Cygwin 程序，启动时要建
   命名管道，受限环境下会崩：

   ```
   ssh.exe: *** fatal error - couldn't create signal pipe, Win32 error 5
   ```

   对策是切到 `C:\WINDOWS\System32\OpenSSH\ssh.exe`（原生实现，不用
   命名管道）。执行 `.\code\scripts\setup_git_ssh.ps1` 即可写入
   `core.sshCommand`。该配置在 `.git/config` 里，**不随仓库分发**，
   每个新克隆都要跑一次。

Python 脚本不受此限，可正常使用中文，但文件读写需显式指定
`encoding="utf-8"`，并用 `python -X utf8` 运行。
