"""Stage exactly one registered-preparation parser experiment on frozen V0171."""
from pathlib import Path
import importlib.util,sys
ROOT=Path(__file__).resolve().parents[2]
def main():
    path=ROOT/'code/scripts/prepare_midi_pending_mask_trial.py'
    spec=importlib.util.spec_from_file_location('existing_frozen_stager',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.SCOPE=ROOT/'code/tb/common/midi_prepared_candidate'
    return mod.main()
if __name__=='__main__':raise SystemExit(main())