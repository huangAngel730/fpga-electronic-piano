"""Strict public-output capture framing/count oracle, not a TMDS/IP checker."""
import argparse
import json
from pathlib import Path


def check(path):
    lines=path.read_text(encoding="ascii").splitlines()
    if not lines or not lines[0].startswith("META 1 "):
        raise ValueError("META_OR_EMPTY")
    if lines[-1].startswith("REJECT "):
        raise ValueError(lines[-1])
    if not lines[-1].startswith("END "):
        raise ValueError("END_OR_TRUNCATION")
    mode=lines[0].split()[2]
    counters={"A":0,"D":0,"V":0,"C":0}
    for line in lines[1:-1]:
        parts=line.split()
        if not parts or parts[0] not in counters:
            raise ValueError("UNKNOWN_OR_DUPLICATE_META_END")
        counters[parts[0]]+=1
        if parts[0]=="D" and (len(parts)!=5 or not -(2**23)<=int(parts[3])<2**23 or not -(2**23)<=int(parts[4])<2**23):
            raise ValueError("DELIVERED_PCM_FIELDS")
    values=list(map(int,lines[-1].split()[1:]))
    if mode=="full_top":
        if len(values)!=9 or counters["A"]!=values[1] or counters["D"]!=values[4] or counters["V"]!=values[3]:
            raise ValueError("EXACT_END_COUNTS")
        if values[0]<100000 or values[1]<600 or values[2]<200000 or values[6]<500:
            raise ValueError("TOP_COVERAGE")
    elif mode=="integrated_display":
        if len(values)!=7 or counters["A"]!=values[2] or counters["D"]!=values[3] or counters["V"]!=values[1]:
            raise ValueError("DISPLAY_EXACT_COUNTS")
        if values[0]<3360000 or values[2]!=5849 or values[3]!=5849 or values[4]<1:
            raise ValueError("DISPLAY_COVERAGE")
    else:raise ValueError("UNKNOWN_SCOPE")
    return dict(passed=True,scope=mode,counts=counters,end=values)


def main():
    p=argparse.ArgumentParser();p.add_argument("capture",type=Path);a=p.parse_args()
    try:result=check(a.capture)
    except (ValueError,OSError,IndexError,UnicodeError) as e:
        print("FAIL",e);return 1
    print("PASS",json.dumps(result,sort_keys=True));return 0


if __name__=="__main__":raise SystemExit(main())
