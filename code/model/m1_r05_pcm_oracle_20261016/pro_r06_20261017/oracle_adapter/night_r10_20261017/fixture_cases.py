"""New synthetic integration fixtures, never represented as a DUT capture.

Expected arithmetic is obtained from the pre-existing settled Reference API,
with the independently scheduled consumption cycles. The new clocked adapter
is not imported or used to manufacture the expected sample values.
"""
from pathlib import Path
import copy
import hashlib
import json

from c9_math import PROFILE, load_reference
from c9_inputs import REPO, read_json


def encode(on=True,source=1,channel=0,note=60,velocity=800,program=None):
    if program is not None:
        return (4<<61)|(source<<57)|(channel<<53)|(5<<18)|(program<<6)
    return ((0 if on else 1)<<61)|(source<<57)|(channel<<53)|(note<<46)|(velocity<<36)


def json_data(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def describe(path,root):
    raw=path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def make_fixture(root, *, notes=(60,), timbre=0, samples=2, cancel_first=False,
                 delay=False, backpressure=2, fx_gains=(16384,16384,8192)):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    bindings=read_json(Path(__file__).with_name('SOURCE_BINDINGS.json'))
    schema=read_json(REPO/bindings['c9_row_schema_path'])
    fields=schema['required']
    refmod=load_reference()
    reference=refmod.Reference()
    assignments={}
    plans=[]
    config_plan=[]
    seq=0
    current=6
    if timbre:
        word=encode(program=timbre)
        plans.append(dict(epoch=0,event_seq=101,expected_event_hex=f'{word:016x}',arrival_window=dict(min_cycle=3,max_cycle=3)))
        assignments[3]=dict(event_valid=1,event_data=word)
        assignments[5]=dict(apply_valid=1,apply_kind=5,apply_data=word,router_apply_seq=0,router_apply_seq_valid=1)
        reference.event(5,'program',program=timbre)
        seq=1
        current=12
    shadow=refmod.allocator.Oracle()
    changes={}
    consume=[]
    for k,note in enumerate(notes):
        accept=current+k*12
        allocate=accept+3
        c=allocate+2+backpressure
        word=encode(note=note,velocity=1023)
        planseq=201+k*7
        plans.append(dict(epoch=0,event_seq=planseq,expected_event_hex=f'{word:016x}',arrival_window=dict(min_cycle=accept,max_cycle=accept)))
        assignments[accept]=dict(event_valid=1,event_data=word)
        _,lane,_,_,_=shadow.step(1,1,0,1,0,note,0)
        assignments[allocate]=dict(apply_valid=1,apply_kind=1,apply_mask=1<<lane,
            apply_data=word,router_apply_seq=seq,router_apply_seq_valid=1)
        assignments[c]=dict(apply_valid=1,apply_kind=2,apply_mask=1<<lane,note_on_mask=1<<lane,
            apply_data=word,router_apply_seq=seq,router_apply_seq_valid=1)
        changes[allocate]=(lane,note)
        consume.append((c,note))
        seq+=1
    for c,note in consume:
        reference.event(c,'note_on',note=note,velocity=1023)
    start=max(c for c,_ in consume)+22
    if delay:
        c=start-12
        dry,wet,feedback=fx_gains
        payload=(1<<61)|(1<<45)|(dry<<30)|(wet<<15)|feedback
        assignments[c]=dict(config_valid=1,config_ready=1,config_take=1,config_payload=payload)
        config_plan.append(dict(epoch=0,payload=payload,arrival_window=dict(min_cycle=c,max_cycle=c)))
        reference.config_accept(c,True,1,dry,wet,feedback)
    frames=[]
    expected=[]
    for i in range(samples):
        a=start+i*28
        req=i+1
        frames.append(a-10)
        assignments[a-10]=dict(frame_tick=1,cancel=1)
        assignments[a-9]=dict(req_valid=1,req_id=req)
        assignments[a]=dict(advance_mask=15,advance_frame_req_id=req)
        out=reference.sample(a,req,effect_accepted=True,publish=not (cancel_first and i==0),postprocess_accept_cycle=a+7)
        assignments[a+7]=dict(effect_input_valid=1,effect_input_ready=1,effect_input_id=req,
            effect_input_left=out['mixed_left'],effect_input_right=out['mixed_right'],
            effect_input_clip_mask=3 if out['upstream_clip'] else 0)
        effectmask=sum(int(x)<<j for j,x in enumerate(out['effect_clip']))
        fbmask=sum(int(x)<<j for j,x in enumerate(out['feedback_clip']))
        clip=sum(int(x)<<j for j,x in enumerate(out['clipped']))
        if cancel_first and i==0:
            frames.append(a+8)
            assignments[a+8]=dict(frame_tick=1,cancel=1)
        else:
            assignments[a+11]=dict(result_valid=1,result_id=req,result_left=out['left'],result_right=out['right'],
                result_clip_mask=clip,upstream_clip_mask=3 if out['upstream_clip'] else 0,
                effect_clip_mask=effectmask,feedback_clip_mask=fbmask)
            assignments[a+12]=dict(commit=1,commit_id=req,commit_left=out['left'],commit_right=out['right'],commit_clip=int(bool(clip)))
        expected.append(out)
    finish=start+(samples-1)*28+16
    plan=dict(schema='M1_NEW_SYNTHETIC_PLAN_V1',independent_of_trace=True,events=plans,config_events=config_plan)
    frame=dict(independent_of_trace=True,epochs=[dict(epoch=0,frame_cycles=sorted(frames))],finish=dict(epoch=0,cycle=finish))
    reset=dict(independent_of_trace=True,sampling_phase='POSEDGE_PRE_NBA',profile='ASSERT_OBSERVED_LOW_BEFORE_RELEASE_V1',
        low_ranges=[dict(epoch=0,first_cycle=0,last_cycle=2)],
        raw_edges=[dict(epoch=0,time_ps=0,value=0,first_sampled_cycle=0),dict(epoch=0,time_ps=62500,value=1,first_sampled_cycle=3)])
    rows=[]
    sources=[0]*4;channels=[0]*4;slotnotes=[0]*4;gens=[0]*4;occupied=0
    for cycle in range(finish+1):
        row={k:0 for k in fields}
        row.update(cycle=cycle,epoch=0,rst_n=int(cycle>2),event_ready=1,req_ready=1,result_ready=1,
            apply_event_seq=None,pll_locked=1,audio_stable=1,finish=int(cycle==finish),
            occupied_mask=occupied,slot_sources=sum(x<<(4*i) for i,x in enumerate(sources)),
            slot_channels=sum(x<<(4*i) for i,x in enumerate(channels)),
            slot_notes=sum(x<<(8*i) for i,x in enumerate(slotnotes)),
            slot_generations=sum(x<<(32*i) for i,x in enumerate(gens)))
        row.update(assignments.get(cycle,{}))
        if row['frame_tick']:
            row['req_ready']=0
            row['result_ready']=0
        rows.append(row)
        if cycle in changes:
            lane,note=changes[cycle]
            sources[lane],slotnotes[lane]=1,note
            gens[lane]+=1
            occupied|=1<<lane
    fixture=dict(rows=rows,plan=plan,frame=frame,reset=reset,capture_id=root.name,
                 expected_samples=expected)
    write_fixture(root,fixture)
    return fixture


def write_fixture(root,fixture):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    raw_capture=json_data(dict(origin='SYNTHETIC_FIXTURE_NOT_RTL',capture_id=fixture['capture_id'],
                               fields=fixture['rows']))
    reset_raw=json_data(fixture['reset'])
    rawsha=hashlib.sha256(raw_capture).hexdigest()
    public=[]
    for i,row in enumerate(fixture['rows'],1):
        source=dict(trace_path='public_rows.jsonl',raw_capture_sha256=rawsha,line=i,
                    cycle=row['cycle'],epoch=row['epoch'],sampling_phase='POSEDGE_PRE_NBA')
        public.append(dict(schema='M3_R7C_C9_PUBLIC_ROW_V1',capture_id=fixture['capture_id'],
            origin='SYNTHETIC_C9_FIXTURE',source=source,fields=row,plan_association=None))
    public_lines=[json_data(r) for r in public]
    public_raw=b''.join(public_lines)
    indexrows=[]
    for original,line in zip(public,public_lines):
        row=original['fields']
        indexrows.append(dict(source={**original['source'],'raw_line_sha256':hashlib.sha256(line).hexdigest()},
            fields=row,apply=dict(apply_kind=row['apply_kind'],independent_apply_event_seq=None)))
    index=dict(schema='M3_R7C_C9_MECHANICAL_INDEX_V1',capture_id=fixture['capture_id'],
        origin='SYNTHETIC_C9_FIXTURE',row_count=len(indexrows),rows=indexrows,
        trace_input=dict(path='public_rows.jsonl',bytes=len(public_raw),sha256=hashlib.sha256(public_raw).hexdigest()))
    files=dict(mechanical_index=('index.json',json_data(index)),public_rows=('public_rows.jsonl',public_raw),
        raw_capture=('raw_capture.json',raw_capture),independent_plan=('plan.json',json_data(fixture['plan'])),
        frame_plan=('frame_plan.json',json_data(fixture['frame'])),reset_edges=('reset_edges.json',reset_raw),
        provenance=('provenance.json',json_data(dict(capture_id=fixture['capture_id'],origin='SYNTHETIC_FIXTURE_NOT_RTL'))))
    for filename,data in files.values():
        (root/filename).write_bytes(data)
    job=dict(schema='M1_C9_MATH_JOB_V1',mode='SYNTHETIC',profile=PROFILE,capture_id=fixture['capture_id'],
        artifacts={role:describe(root/name,root) for role,(name,_) in files.items()})
    (root/'job.json').write_bytes(json_data(job))
    return root/'job.json'
