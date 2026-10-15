"""Explicitly synthetic negative captures; normal input is the new RTL fixture."""
import argparse
import json
from pathlib import Path
import zipfile
from check_capture import check, digital_latency, quantize, FIELDS


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--capture",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args(); args.output.mkdir(exist_ok=False)
    original=args.capture.read_text(encoding="ascii").splitlines()
    results=[]
    def mutate(name, diagnostic, transform):
        lines=original.copy(); transform(lines)
        path=args.output/(name+".SYNTHETIC.csv")
        path.write_text("\n".join(lines)+"\n",encoding="ascii")
        try:
            check(path)
            error="ACCEPTED"
        except ValueError as exc:
            error=str(exc)
        passed=error.startswith(diagnostic)
        results.append({"name":name,"expected":diagnostic,"actual":error,"passed":passed,"kind":"SYNTHETIC_MUTATION"})
    def field(lines, index, key, value):
        row=lines[index].split(","); row[FIELDS.index(key)]=str(value); lines[index]=",".join(row)
    live=next(i for i,l in enumerate(original[1:-1],1) if l.split(",")[2]=="1")
    commit=next(i for i,l in enumerate(original[1:-1],1) if l.split(",")[7:9]==["1","1"])
    mutate("missing_cycle","MISSING_OR_DUPLICATE_CYCLE",lambda x:x.pop(live+100))
    mutate("duplicate_cycle","MISSING_OR_DUPLICATE_CYCLE",lambda x:x.insert(live+100,x[live+100]))
    mutate("x_pin","UNKNOWN_OR_NONINTEGER",lambda x:field(x,live+200,"din","x"))
    mutate("invalid_flag","FLAG_RANGE",lambda x:field(x,live+200,"clip",2))
    mutate("missing_end","MISSING_END",lambda x:x.pop())
    mutate("wrong_signed_pcm","FIXTURE_INPUT_CALENDAR",lambda x:field(x,commit,"left",1))
    mutate("wrong_clip_alignment","FIXTURE_INPUT_CALENDAR",lambda x:field(x,commit,"clip",1))
    mutate("old_id_accept","ID_READY_QUALIFICATION",lambda x:field(x,commit,"pcm_id",0))
    mutate("wrong_sample_phase","SAMPLE_TICK_PHASE",lambda x:field(x,live+200,"tick",1))
    mutate("wrong_serial_phase","LSBJ_PADDING_PHASE",lambda x:[field(x,i,"din",1) for i in range(live+500,live+600)])
    try:
        check(args.capture,expected_underflows=0)
        error="ACCEPTED"
    except ValueError as exc:
        error=str(exc)
    results.append({"name":"unexpected_underflow","expected":"UNEXPECTED_UNDERFLOW","actual":error,"passed":error=="UNEXPECTED_UNDERFLOW","kind":"SYNTHETIC_POLICY"})
    for name,request,complete,expected in (("10ms_exact",10,400010,None),("10ms_exceeded",10,400011,"DIGITAL_LATENCY_EXCEEDS_10MS"),("negative_time",10,9,"LATENCY_CALENDAR")):
        try:
            digital_latency(request,complete); error=None
        except ValueError as exc:
            error=str(exc)
        results.append({"name":name,"expected":expected,"actual":error,"passed":error==expected,"kind":"SYNTHETIC_TIMESTAMPS"})
    for value,expected in ((8388607,32767),(-8388608,-32768),(127,0),(128,1),(-128,0),(-129,-1)):
        actual=quantize(value)
        results.append({"name":"round_"+str(value),"passed":actual==expected,"actual":actual,"expected":expected,"kind":"SOFTWARE_FIXED_POINT"})
    (args.output/"RESULTS.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    with zipfile.ZipFile(args.output/"SYNTHETIC_BAD_CAPTURES.zip","x",zipfile.ZIP_DEFLATED) as z:
        for path in args.output.glob("*.csv"): z.write(path,path.name)
    print(json.dumps(results))
    return int(not all(r["passed"] for r in results))


if __name__=="__main__":
    raise SystemExit(main())
