"""Actual Tk widget smoke, injected chooser/confirm; not a human picker test."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    root_repo=HERE.parents[2]
    if not output.is_relative_to(root_repo/'code/output'):
        parser.error('require task output under code/output')
    output.mkdir(parents=True,exist_ok=False)
    result=dict(status='FAIL',passed=False,hardware_pass_claim=False,
                scope='Actual Tk creation/update/buttons/tree with injected callbacks; NOT human native picker',
                native_picker_tested=False,screenshot_claim=False,serial_calls=0,network_calls=0,checks=[])
    root=None;controller=None
    try:
        import tkinter as tk
        from desktop_gui import DesktopApp
        from desktop_controller import Controller
        source=root_repo/'code/software/score_midi_real_input_acceptance_20261015/inputs/MIDI_sample_2018-03-21.mid'
        root=tk.Tk();root.withdraw()
        controller=Controller(output/'w')
        choices=iter(['',str(source)])
        confirmed={'value':False}
        destination=output/'confirmed_export'
        app=DesktopApp(root,controller,chooser=lambda:next(choices),
                       directory_chooser=lambda:str(destination),confirm=lambda path:confirmed['value'])
        app.choose_button.invoke();root.update()
        assert controller.source is None
        result['checks'].append('cancel_injected_file_chooser_no_selection')
        app.choose_button.invoke();root.update()
        assert controller.source==source.resolve()
        app.source_var.set('GolhaMedia Commons original; see SOURCE_RIGHTS.txt')
        app.license_var.set('CC0 1.0 original')
        app.preview_button.invoke();root.update()
        assert str(app.choose_button['state'])=='disabled'
        result['checks'].append('busy_buttons_disabled')
        deadline=time.monotonic()+30
        while controller.state=='loading' and time.monotonic()<deadline:
            root.update();time.sleep(0.01)
        root.update()
        assert controller.state=='ready',controller.error
        assert len(app.tree.get_children())==44
        assert int(app.tree.item('43')['values'][4])==384000
        assert '44/512' in app.summary_var.get()
        result['checks'].append('actual_tree_44_rows_final_sample_384000')
        app.export_button.invoke();root.update()
        assert not destination.exists()
        result['checks'].append('confirmation_cancel_no_output')
        confirmed['value']=True
        app.export_button.invoke();root.update()
        deadline=time.monotonic()+30
        while controller.state=='exporting' and time.monotonic()<deadline:
            root.update();time.sleep(0.01)
        root.update()
        assert controller.state=='ready',controller.error
        exported=json.loads((destination/'desktop_export_receipt.json').read_text(encoding='utf-8'))
        assert exported['status']=='OFFLINE_EXPORT_PASS'
        result['checks'].append('confirmed_export_actual_original_bytes')
        app.close()
        assert controller.wait_closed(5)
        root=None
        result['checks'].append('normal_close_private_worker_stopped')
        # A second actual Tk instance checks cancel/close with an injected
        # blocking runner; no child is falsely claimed to have launched here.
        root=tk.Tk();root.withdraw()
        started=threading.Event()
        def blocking(argv,cwd,logs,cancel,timeout):
            started.set();cancel.wait(2)
            return dict(exit_code=1,cancelled=True,tool_calls=0)
        controller=Controller(output/'wc',runner=blocking)
        controller.select_file(source)
        app=DesktopApp(root,controller)
        app.preview_button.invoke();root.update();assert started.wait(2)
        app.cancel_button.invoke();app.close()
        deadline=time.monotonic()+5
        while not controller.wait_closed(0) and time.monotonic()<deadline:
            try:root.update()
            except tk.TclError:break
            time.sleep(0.01)
        assert controller.wait_closed(0)
        result['checks'].append('actual_cancel_button_and_close_with_injected_worker')
        result.update(passed=True,status='TK_WIDGET_SMOKE_PASS',exit_code=0)
    except Exception as error:
        result.update(error=type(error).__name__+': '+str(error),exit_code=1)
    finally:
        if controller is not None:
            controller.close();controller.wait_closed(5)
        if root is not None:
            try:root.destroy()
            except Exception:pass
        (output/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
