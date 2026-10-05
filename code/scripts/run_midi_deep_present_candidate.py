"""Bounded isolated presentation/live-RR pipeline tests. No production writes/PnR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "code/tb/common/midi_deep_present_candidate"
CAD = Path(r"D:\Gowin\oss-cad-suite")
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    out=a.output.resolve();out.relative_to(ROOT / "code/output");out.mkdir(parents=True,exist_ok=False)
    formal=ROOT/"code/rtl/input/midi_input/midi_event_parser.sv"
    before=sha(formal)
    ref=out/"reference.sv";ref.write_text(formal.read_text(encoding="utf-8").replace("module midi_event_parser #(","module midi_event_parser_reference #(",1),encoding="utf-8",newline="\n")
    env=os.environ.copy();env["PATH"]=str(CAD/"bin")+";"+str(CAD/"lib")+";"+env["PATH"]
    runs={}
    def run(name,cmd,good=True,marker=None,timeout=300):
        log=out/(name+".log")
        with log.open("wb") as f:
            r=subprocess.run(list(map(str,cmd)),cwd=out,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
        text=log.read_text(encoding="utf-8",errors="replace")
        runs[name]={"exit":r.returncode,"expected_success":good,"sha256":sha(log),"command":list(map(str,cmd)),"tail":text[-1000:]}
        print(name,r.returncode,text[-500:],flush=True)
        if ((r.returncode==0)!=good) or (marker and marker not in text):raise RuntimeError(name)
    defs=ROOT/"code/rtl/common/audio_defs_pkg.sv";parser=SCOPE/"midi_event_parser.sv";selector=SCOPE/"control_snapshot_top4.sv";tb=SCOPE/"tb_midi_deep_present.sv"
    cc=[CAD/"bin/iverilog.exe","-g2012","-s","tb_midi_deep_present"]
    try:
        for name,burst,depth,hz in [("b1d1",1,1,100000),("b8d8",8,8,100000),("b16d8",16,8,100000),("real50m",8,8,50000000)]:
            v=out/(name+".vvp")
            run(name+"_compile",cc+["-Ptb_midi_deep_present.BURST="+str(burst),"-Ptb_midi_deep_present.DEPTH="+str(depth),"-Ptb_midi_deep_present.CLOCK_HZ="+str(hz),"-o",v,defs,selector,parser,ref,tb])
            run(name+"_run",[CAD/"bin/vvp.exe",v],marker="PASS deep parser")
        rng=random.Random(715819)
        masks=[0,0xffffffff]+[1<<k for k in range(32)]+[(1<<k)|(1<<((k+1)%32)) for k in range(32)]+[0x55555555,0xaaaaaaaa,0x80000001]+[rng.getrandbits(32) for _ in range(512)]
        rows=[]
        for mask in masks:
            for rr in range(32):
                w=[(rr+i)%32 for i in range(32) if mask&(1<<((rr+i)%32))][:4]
                valid=(1<<len(w))-1;indices=sum(k<<(5*i) for i,k in enumerate(w))
                rows.append(f"{len(rows)} {mask:08x} {rr} {valid:x} {indices:05x}\n")
        assert len(rows)==18592
        vec=out/"top4.txt";vec.write_text("".join(rows),encoding="ascii")
        topv=out/"top4.vvp"
        run("top4_compile",[CAD/"bin/iverilog.exe","-g2012","-s","tb_snapshot_top4","-o",topv,selector,SCOPE/"tb_snapshot_top4.sv"])
        run("top4_run",[CAD/"bin/vvp.exe",topv,"+VECTORS="+str(vec)],marker="PASS snapshot top4 vectors=18592")
        for name,text in [("empty", ""),("short",rows[0])]:
            bad=out/(name+".txt");bad.write_text(text,encoding="ascii")
            run(name,[CAD/"bin/vvp.exe",topv,"+VECTORS="+str(bad)],good=False,marker="vacuous or truncated count")
        source=parser.read_text(encoding="utf-8")
        mutants=[
            ("no_reservation","(discrete_handshake && burst_limit_reached)","(discrete_handshake && 1'b0)","no ninth discrete"),
            ("revoke_head","event_valid      = control_locked || discrete_presented;","event_valid      = control_locked || (discrete_presented && eligible_mask==0);","held presentation changed"),
            ("stale_lock","if(parsed_control && parsed_control_index==selected_index)","if(1'b0 && parsed_control && parsed_control_index==selected_index)","exact LIVE RR and newest"),
            ("two_not_four","repair_valid[k]=snapshot_valid[k] && eligible_mask[repair_index[k]];","repair_valid[k]=(k<2) && snapshot_valid[k] && eligible_mask[repair_index[k]];","live pending requires first-computation grant")]
        for name,old,new,reason in mutants:
            assert source.count(old)==1,name
            bad=out/(name+".sv");bad.write_text(source.replace(old,new,1),encoding="utf-8",newline="\n")
            v=out/(name+".vvp");run(name+"_compile",cc+["-o",v,defs,selector,bad,ref,tb])
            run(name+"_run",[CAD/"bin/vvp.exe",v],good=False,marker=reason)
        record={"date":"2026-10-05","passed":True,"runs":runs,"formal_sha_before":before,"formal_sha_after":sha(formal),"inputs":{str(p.relative_to(ROOT)):sha(p) for p in [parser,selector,tb,SCOPE/"tb_snapshot_top4.sv",defs]},"not_cycle_equivalent_to_original":True,"no_Gowin_or_STA_yet":True,"fixtures_are_decoded_event_injections_not_UART":True}
        assert record["formal_sha_after"]==before
        (out/"functional.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        print("PASS presentation/live RR pipeline, four configurations, top4 and four compiled mutants",flush=True)
    finally:
        (out/"run_status.json").write_text(json.dumps({"runs":runs,"formal_sha_after":sha(formal)},indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":raise SystemExit(main())
