"""Prepare one private board-top copy connecting frozen T062 public readout."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'code/build/138k_night_cache_combo/staged_20261010_01'
MODULE=ROOT/'code/rtl/board/m2_score_playback_candidate_20261015/m2_score_playback_candidate.sv'
TOP='m2_score_playback_board_top'


def ident(path):
    data=Path(path).read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();allowed=(ROOT/'code/output').resolve()
    if out.exists() or out==allowed or not out.is_relative_to(allowed):
        raise ValueError('NEW_OUTPUT_REQUIRED')
    out.mkdir(parents=True)
    result={'status':'FAIL_PARTIAL','error':None,'scope':'PRIVATE_SCORE_BOARD_SIM_ONLY',
            'production_modified':False,'new_EDA':0,'physical_STA':'NOT_RUN','sources_before':{},'sources_after':{}}
    before={}
    try:
        frozen=BASE/'frozen_receipt.json';r=json.loads(frozen.read_text(encoding='utf-8'))
        if (r['version']!='night_cache_parser_hold_20261010_v1' or r['input_count']!=62 or
                r['new_RAM_reference_commit']!='5e1d13c398fd1cf749c613a30b9238d1a46319b4'):
            raise ValueError('FROZEN_BASELINE_IDENTITY')
        before[str(frozen)]=ident(frozen)
        for name,item in r['inputs'].items():
            source=BASE/'inputs'/name
            if ident(source)['sha256']!=item['adapted_sha256']:
                raise ValueError('SOURCE_DRIFT:'+name)
            before[str(source)]=ident(source)
        for path in (MODULE,Path(__file__)):
            before[str(path)]=ident(path)
        old=(BASE/'inputs/sources/audio_visual_coexistence_top.sv').read_text(encoding='utf-8')
        anchors={
            'module audio_visual_coexistence_top #':'module '+TOP+' #',
            'AUDIO_VISUAL_COEXISTENCE_TOP_SV':'M2_SCORE_PLAYBACK_BOARD_TOP_SV',
            '.event_valid(shared_event_valid),\n          .event_ready(shared_event_ready),.event_data(shared_event_data),.frame_tick(i2s_frame_tick),':
            '.event_valid(score_mixed_valid),\n          .event_ready(score_mixed_ready),.event_data(score_mixed_data),.frame_tick(i2s_frame_tick),',
            ".uart_tx_o(score_uart_tx),.rd_req(1'b0),.rd_index(9'd0),":
            '.uart_tx_o(score_uart_tx),.rd_req(score_rd_req),.rd_index(score_rd_index),',
        }
        new=old
        for key,value in anchors.items():
            occurrences=3 if key=='AUDIO_VISUAL_COEXISTENCE_TOP_SV' else 1
            if new.count(key)!=occurrences:raise ValueError('TOP_ANCHOR:'+key[:60])
            new=new.replace(key,value,occurrences)
        declaration='''    // M2 isolated score playback arbiter, downstream of the original FIFO.
    wire score_mixed_valid,score_mixed_ready,score_rd_req;
    wire [8:0] score_rd_index;
    wire [63:0] score_mixed_data;
    wire [9:0] score_consumed_events;
    wire [31:0] score_late_events,score_active_id;
    wire score_fault;
    m2_score_playback_candidate u_score_playback (
        .clk(core_clk),.rst_n(rst_sync_n),.frame_tick(i2s_frame_tick),
        .committed_valid(score_committed_valid),.commit_pulse(score_commit_pulse),
        .committed_count(score_committed_count),.committed_score_id(score_committed_id),
        .rd_req(score_rd_req),.rd_index(score_rd_index),
        .rd_valid(score_rd_valid),.rd_event(score_rd_event),
        .base_valid(shared_event_valid),.base_data(shared_event_data),
        .base_ready(shared_event_ready),.event_valid(score_mixed_valid),
        .event_data(score_mixed_data),.event_ready(score_mixed_ready),
        .consumed_events(score_consumed_events),.late_events(score_late_events),
        .active_score_id(score_active_id),.fault(score_fault)
    );
'''
        marker='    // M2 isolated score-storage integration. No connection to performance'
        if new.count(marker)!=1:raise ValueError('SCORE_RECEIVER_MARKER')
        new=new.replace(marker,declaration+'\n    // Original score-storage integration: playback attached in this private copy.\n    // M2 isolated score-storage integration. No connection to performance',1)
        old_head=old.split(') (',1)[1].split(');',1)[0]
        new_head=new.split(') (',1)[1].split(');',1)[0]
        if old_head!=new_head:raise ValueError('EXTERNAL_BOARD_PORT_CHANGE')
        output=out/(TOP+'.sv');output.write_text(new,encoding='utf-8',newline='\n')
        project=ET.parse(BASE/'audio_visual_coexistence_top.gprj')
        files=[]
        for x in project.getroot().iter('File'):
            if x.attrib['type']=='file.verilog':
                source=Path(x.attrib['path'])
                files.append(str(output if source.name=='audio_visual_coexistence_top.sv' else source))
        if len(files)!=50:raise ValueError('PROJECT_HDLS_COUNT:'+str(len(files)))
        result.update(status='PREPARED_SCORE_BOARD_NOT_PHYSICALLY_ADMITTED',
                      top=ident(output),source_files=files+[str(MODULE)],
                      frozen_source_count=len(r['inputs']),
                      preserved_top_sha256=hashlib.sha256(old.encode('utf-8')).hexdigest())
        result['sources_before']=before
        result['sources_after']={name:ident(Path(name)) for name in before}
        if result['sources_before']!=result['sources_after']:raise ValueError('SOURCE_DRIFT_AFTER')
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        result['sources_after']={name:ident(Path(name)) for name in before if Path(name).is_file()}
    result['exit_code']=0 if result['error'] is None else 1
    (out/'PREPARATION_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('status','error','frozen_source_count','exit_code')}))
    return result['exit_code']

if __name__=='__main__':raise SystemExit(main())