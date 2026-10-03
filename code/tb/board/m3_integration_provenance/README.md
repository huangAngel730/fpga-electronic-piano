# M3 D：Gowin 工程来源审计

任务依据：`b9366a6`，`code/docs/M3_后续并行任务_T028收口与工程来源审计_2026-10-03.md`。

本目录只交付**只读来源审计器及其自检夹具**。不修改工程、RTL、ROM、约束、算法或既有 prepare 脚本。正式整合审计需要 M2 独立提供批准清单；不能将当前工作区的实测 SHA 自动填入清单并称为独立批准。测试生成的清单均标为 `TEST_FIXTURE_ONLY`，不是 M2 生产清单。

## 入口和结果

在仓库根目录执行（`python` 使用现有 Python 3.9+，无第三方依赖）：

```powershell
python -X utf8 code/tb/board/m3_integration_provenance/test_audit.py

python -X utf8 code/scripts/run_m3_integration_provenance_audit.py `
  --project <final.gprj> --manifest <m2_manifest.json> `
  --repo-root <actual_repo_root> --report <new_report.json>
```

`--repo-root` 默认由脚本位置定位仓库，支持 M2 的 D 盘和 M3 的 E 盘工作区。`--report` 可省略；指定时父目录须已存在，文件必须不存在，禁止覆盖旧证据。标准输出为 JSON，退出码 0 仅表示来源审计通过，失败退出码 1，缺必需命令行参数退出码 2。失败包含错误类型；SHA 不符包含实际完整路径及期望/实际原始字节 SHA。

标签：

- `PRODUCTION_PROVENANCE_ONLY`：独立生产清单来源一致，不是综合或时序通过。
- `ISOLATED_CANDIDATE_ONLY`：隔离候选，只能用于隔离实验。
- `TEST_FIXTURE_ONLY`：自检合成夹具，不是实际电子琴实现；另有 `scope` / `scope_label` 标明夹具正在测试的隔离或生产策略。

审计器验证等级为 **L0 来源检查 / L1 审计器自检**；不是 RTL 仿真 L2，更不是综合、PnR、STA、音效或上板结论。V0158 的旧冻结候选不能冒充最终接入：必须使用 M2 对最终基线、各启用源、功能和角色新提供的批准清单。本工具不判断聊天中谁有批准权限，不验证批准人的数字签名；批准清单可信性由项目受控发布保证。

## M2 清单格式（version=1）

下面为结构说明，`<...>` 必须替换为 M2 批准值，**不可直接作为正式清单运行**。自检生成目录中的 `production/repo/approved_manifest.json` 是完整可运行的合成夹具例子。

```json
{
  "version": 1,
  "scope": "production",
  "approval": {"by": "M2", "reference": "<批准记录或交付说明>"},
  "baseline_commit": "<7到40位Git提交号>",
  "features": {"audio": "<启用的音频版本>", "visual": "<启用或不启用>"},
  "project": {"path": "<仓库相对GPRJ路径>", "sha256": "<64位原始字节SHA>"},
  "synthesis_cwd": "code",
  "include_dirs": ["code/rtl/common", "code/rtl/board"],
  "files": [
    {"path": "<正式parser路径>", "kind": "source", "origin": "repository", "sha256": "<批准SHA>"},
    {"path": "<header路径>", "kind": "include", "origin": "repository", "sha256": "<批准SHA>"},
    {"path": "<ROM路径>", "kind": "rom", "origin": "repository", "sha256": "<批准SHA>"},
    {"path": "<CST路径>", "kind": "cst", "origin": "repository", "sha256": "<批准SHA>"},
    {"path": "<SDC路径>", "kind": "sdc", "origin": "repository", "sha256": "<批准SHA>"}
  ],
  "roles": {"parser": "<正式parser路径>", "button_counter": "<正式counter路径>", "public_fifo": "<FIFO路径>"},
  "required_roles": ["parser", "button_counter", "public_fifo"]
}
```

`files` 必须补齐所有启用源、综合包含文件、ROM、CST/SDC，每个完整解析路径只能出现一次。`source` / `cst` / `sdc` 必须出现在 GPRJ 启用列表；include 和隐式 ROM 不要求作为 GPRJ File 条目。至少启用一个批准 CST 和一个批准 SDC。未启用的 GPRJ 条目单独报告，不把它当成最终实现。启用状态必须明确是 `0` 或 `1`，未知类型拒收。

`roles` 与 `required_roles` 须非空，具体角色由 M2 按实际功能指定。不强迫尚未接入的 Pitch/Mod/T028 出现在当前工程。报告分别列出 parser、button_counter、public_fifo、control_snapshot、adsr、strict_flash；没有声明的角色标为 `not_declared_by_M2_manifest`，不能理解为已经验证该功能。

### 复用现有 prepare SHA 清单

优先沿用现有 `inputs.json` / `combo_override.json` / 控制快照准备清单，不复制重建其 SHA 表。M2 先批准这些元数据文件本身的 SHA，然后用引用替代文件或 GPRJ 的直接 `sha256`：

```json
{
  "hash_manifests": [{"path": "<existing_inputs.json>", "sha256": "<独立批准的元数据SHA>"}],
  "files": [{
    "path": "<实际源路径>", "kind": "source", "origin": "repository",
    "hash_ref": {
      "manifest": "<existing_inputs.json>",
      "field": "input_sha256",
      "key": "<原清单内完整键，逐字保留>"
    }
  }]
}
```

可选择现有 `input_sha256`、`actual_input_sha256`、`actual_build_input_sha256`、`original_source_sha256` 等字段，点号表示嵌套对象字段。选中的值可以是 SHA 字符串或含 `sha256` 的对象。引用只允许使用已固定 SHA 的 `hash_manifests`；不得只按 basename 寻找键。直接 SHA 与引用同时存在时必须一致。示例是增量字段说明，仍须补齐上节完整清单。

### 路径、来源和隔离

- 清单路径以实际仓库根为基准；GPRJ 相对路径以该 GPRJ 所在目录为基准；综合 `$readmemh/$readmemb` 路径以 M2 指定的 `synthesis_cwd` 为基准，不能借用仿真工作目录。
- 现有准备清单或 GPRJ 含另一机器的绝对仓库路径时，可设置 `recorded_repo_root: "D:/.../fpga-electronic-piano"`，仅将该**完整根路径**映射至 `--repo-root`。E 盘同理；不自动替换所有 D/E 盘路径，不做文件名回退。哈希引用的 `key` 保留旧清单的原键。外部文件不因此自动获准。
- `origin=repository` 只允许实际仓库内非 `code/output/` 文件。`isolated_candidate` 要求 `scope=isolated`；必须逐一列路径和 SHA，报告隔离标签。
- 生产中的 `code/output/` 副本默认拒收。只有 M2 明确批准的 `origin=approved_production_stage` 且有非空 `approval_reference` 才能作为最终冻结构建快照使用；这是逐文件例外，不是把隔离候选直接改称生产。
- 外部文件须指定 `approved_external_roots`（绝对、现存、仓库外目录），且文件来源为 `approved_external` 并有 `approval_reference`。未批准目录、根外逃逸、无盘符根路径、盘符相对路径拒收。
- 重复启用同一实际路径始终拒收。不同文件同 basename 默认拒收；例外须在 `allowed_duplicate_basenames` 中列出 `name` 和精确 `paths` 集合。即使批准 basename 例外，重复定义同一个 module（例如改名的第二份 parser）仍拒收。
- 所有 SHA 按原始字节，CRLF 与 LF 不等价。只为解析兼容现有 Gowin XML `version="1"`，不改 GPRJ 字节或批准 SHA。DOCTYPE/ENTITY、重复 JSON 键拒收。

综合依赖检查移除明确的 `synthesis/synopsys translate_off/on` 段，解析字面量 include、ROM 字面路径或字符串 parameter/localparam 默认值，以及命名参数的 `.mem/.hex` 字面覆盖。保守要求默认与字面覆盖都获准，不将仿真专用 ROM 当成综合 ROM。不能静态解析的 ROM/include 表达式、加密 HDL、VHDL 拒收；不替代完整预处理、综合 elaboration 或厂商 IP 内部依赖审查。遇到这些边界，应交 M2 提供可审计源/依赖，不猜测通过。

## 自检覆盖与证据

`test_audit.py` 在新建的 `code/output/m3_provenance_<随机后缀>/` 生成可复跑夹具和日志，不覆盖或删除既有目录。可用 `--output code/output/<全新目录>` 固定路径。

当前 **37 组：7 正向、30 负向**。正向包括生产夹具、禁用缺失源、D/E 绝对路径迁移、显式隔离、批准生产快照、精确 basename 例外。必须的旧 parser、output-only button、缺 ROM、重复 parser、CST/SDC 不匹配均实际调用 CLI，非零退出；另外覆盖改名重复 module、仅仿真 ROM、未列源/ROM、动态 ROM、宏 include、加密源、严格 CRLF、缺角色/文件/manifest/约束、失效/未批准元数据、非法 XML/JSON/启用值、根外路径和禁止覆盖证据。

每例保存 `stdout.log`、`stderr.log`、`audit_report.json`（覆盖保护例除外）。总 `evidence.json` 保存真实命令、退出码、期望/实际错误、日志 SHA、输入 SHA、工具版本及脚本 SHA。自检验证所有审计输入运行前后逐字节一致。

交付仅新增本 README、自检脚本和审计入口。M2 负责正式 manifest、来源复核、验证编号及共享状态收口；最终 manifest 未到件时只交“审计器就绪”，不宣称正式整合工程通过。
