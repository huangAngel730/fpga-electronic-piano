"""Post-publication handoff: original package, exact gate, Git and forward text."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

OUT = Path(__file__).resolve().parent
COORD = OUT.parent
ROOT = COORD.parents[5]


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()


def main():
    status = json.loads((COORD / "PUBLICATION_STATUS.json").read_text(encoding="utf-8"))
    gate = json.loads((COORD / "GATE_R01/GATE_RECEIPT.json").read_text(encoding="utf-8"))
    assert status["status"] == "PUSHED_REMOTE_SHA_VERIFIED" and gate["status"] == "PASS"
    assert gate["pass_count"] == 9 and gate["input_bytes_unchanged"]
    head = git("rev-parse", "HEAD")
    assert head == status["commit"] == git("rev-parse", "origin/develop")
    assert git("rev-parse", "HEAD^{tree}") == status["candidate_tree"]
    delivery = json.loads((COORD / "DELIVERY/DELIVERY.json").read_text(encoding="utf-8"))
    raw = ROOT / delivery["archive"]["path"]
    assert len(raw.read_bytes()) == delivery["archive"]["bytes"]
    assert sha(raw.read_bytes()) == delivery["archive"]["sha256"]
    git_blob = subprocess.run(["git", "show", head + ":" + raw.relative_to(ROOT).as_posix()],
                              cwd=ROOT, capture_output=True, check=True).stdout
    assert git_blob == raw.read_bytes()
    m2 = f"""M2你好，请限定复核M3 10月17日第二份四拓展任务。完整E1/E2/E3/E4仍PARTIAL，board_release_allowed=false；不是四项实物或新Pro整机通过。

已普通推送develop：{head}，推后fetch核HEAD/origin同SHA。提交链接：{status['commit_url']}。精确候选树{status['candidate_tree']}，98个授权新文件；本次check_repo九项9/9 PASS、退出0，{gate['seconds']:.3f}秒，前后{gate['candidate_input_count']}份输入原字节一致。不是沿用旧门禁，也未另建checkout。正式top/pkg/PLL/CST-SDC、旧源ROM/封存、当前状态/看板未改，编号请由你登记。

E1复用既有默认640×480/八槽/FIFO32的487检查/四RTL坏例，新增L0来源/原ZIP核查，功能新0轮；旧闪光FAIL保留。E2限定L2：历史5849真实采纳点原833/834节奏经新桥/core，14241输入/观察、14074消费、五黄金快照/8扫描及五RTL坏例通过。E3限定L2：一份300B真实CC0 MIDI、44条/352B，经实际UART→RAM→完整44条READ，127场景/112应答/11完整RAM快照；新后继修COMMIT语义错误4/5/6/8清会话/cache，异常后旧谱保持并恢复；14NACK及CRC旁路RTL拒收。E4短窗L3/退休L2：N4/8/16/32各64接受=60发布+3取消+1reset取消，32运输提交，最大69/109/189/349拍<833；11实际RTL坏例。N32全32槽4802推进/退休；完整串行半帧L32/R31，不签所有32commit全双声道；正常clip0、等左右、冻结piano，未签非零饱和/纯正弦/可闻32谱峰，V释放payload未完整独立逐字段签收。

本次E1/E2/E3/E4消费0/3/6/5组，各上限6，新增runner合计593.938秒；E3第6轮仅报告控制，不重跑RTL。E4物理条件2轮消耗0/NOT_RUN；所有Gowin/设备/下载0。编译/检查器/首诊断失败原件全保，修checker只复用固定捕获。正例一般退出0，E2五拒收VVP退出1；E3 CRC变体正常仿真0、独立拒收1；E4十唯一目标Fatal按ModelSim实际退出0及一clipped独立拒收1，超时/崩溃不算负例PASS。逐条argv/cwd、起止、双流和SHA见内包收据；E4单调用墙钟起止及动态加载DLL实测标UNKNOWN，不伪造。

请接收当前转发ZIP本体。内含原件总包（12235550字节/SHA da9d149b21d17dc2e5c260818d93ec6da3741200103e705ff4e27af1f1a3356b，Git blob同字节）、四内包清单、总控自审/缺件、此次门禁双流和Git核验。E1/E2/E3/E4分别128/227/283/1070份清单载荷，大小/SHA/CRC核同；总包100载荷+1清单。仅一份RTL_PATCH_PROVENANCE.json松散Git元数据规范化LF，ZIP原字节保留；所有新源码和总ZIP均Git字节一致。

需要你决定/提供：新Pro完整FPG676型号修订、商用许可、同版source/ROM/IP/top/时钟复位/正式生产者与接点、隔离CST-SDC及完整CDC/Setup/Hold/Recovery/Removal、准入.fs/恢复SHA和电气/设备许可；E3选定该行为后继与BRAM/正式UART方案。E4若要求纯音，请M1先冻结隔离测试模式/ROM/混音数学。正式同版签收仍基础Pro→双音色→E1→E2→E3→E4；M3待准入后补实屏、实体ACK/READ与32音频谱原件。

待用户转发，尚未送达；四夜间AI回执不等于真人已收到或验收。
"""
    (OUT / "给M2_待用户转发.md").write_text(m2, encoding="utf-8", newline="\n")
    m1 = f"""M1你好，M3本次N32隔离候选已按冻结piano/ROM及既有独立参考核N4/8/16/32，未改算法或旧原件。发布提交{head}。完整E4仍PARTIAL，未签纯音、32可闻/独立谱峰或实物。

若最终32频独奏/混合验收要求纯正弦，请明确与piano模式隔离的测试模式、phase→sine ROM、各槽增益、混音/saturation/clipped口径及独立黄金定义；收到冻结口径后M3才实施新候选，不从DUT反推黄金或直接替换旧ROM。新Pro物理/完整STA/码流准入归M2。当前转发包内有N32原件与限定边界，正常clip0、等左右和生命周期尾段不升级为更高覆盖。

待用户转发，尚未送达。本消息是精确算法事项请求，不声称你已处理或签收。
"""
    (OUT / "给M1_待用户转发.md").write_text(m1, encoding="utf-8", newline="\n")
    (OUT / "README.txt").write_text("第二任务四拓展仍PARTIAL。请转发本ZIP及给M2文字；需要纯音算法确认时转给M1。\n"
        "ORIGINALS为四包原件总ZIP，PUBLICATION为本次门禁/Git证据。所有设备操作0。\n"
        "原件总ZIP SHA256 da9d149b21d17dc2e5c260818d93ec6da3741200103e705ff4e27af1f1a3356b。\n",
        encoding="utf-8", newline="\n")
    files = {"ORIGINALS/" + raw.name: raw}
    for name in ("RESULT.md", "COORDINATOR_SELF_REVIEW.md", "PENDING_INTEGRATION.md",
                 "E1_REUSE_AUDIT.md", "ENVIRONMENT_COMPARISON.md", "INTAKE_FINAL.json", "PUBLICATION_STATUS.json"):
        files["COORDINATOR/" + name] = COORD / name
    for p in (COORD / "DELIVERY").glob("*.json"):
        files["ORIGINALS/" + p.name] = p
    for folder in sorted(COORD.glob("GATE_R*")) + [COORD / "PUBLICATION_AUDIT"]:
        for p in folder.rglob("*"):
            if p.is_file():
                files["PUBLICATION/" + p.relative_to(COORD).as_posix()] = p
    for p in OUT.iterdir():
        if p.is_file():
            files["FORWARD/" + p.name] = p
    entries = [{"member": key, "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
               for key, p in sorted(files.items())]
    save(OUT / "HANDOFF_MANIFEST.json", {"files": entries})
    archive_path = OUT / "M3_TASK2_FOUR_EXTENSIONS_HANDOFF_COMPLETE_20261017.zip"
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for key, p in sorted(files.items()):
            archive.write(p, key)
        archive.write(OUT / "HANDOFF_MANIFEST.json", "HANDOFF_MANIFEST.json")
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(files) | {"HANDOFF_MANIFEST.json"}
        for entry in entries:
            data = archive.read(entry["member"])
            assert len(data) == entry["bytes"] and sha(data) == entry["sha256"]
    result = {"status": "LOCAL_HANDOFF_COMPLETE_FULL_FEATURES_PARTIAL", "utc": datetime.now(timezone.utc).isoformat(),
              "commit": head, "commit_url": status["commit_url"], "gate": "9/9_PASS_EXIT0_EXACT_TREE",
              "archive": {"path": str(archive_path), "bytes": archive_path.stat().st_size,
                          "sha256": sha(archive_path.read_bytes())},
              "members": len(entries) + 1, "CRC_size_SHA": "ALL_PASS",
              "M1_M2_human_delivery": "WAITING_FOR_USER_FORWARD_NOT_DELIVERED", "board_release_allowed": False}
    save(OUT / "FINAL_DELIVERY.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
