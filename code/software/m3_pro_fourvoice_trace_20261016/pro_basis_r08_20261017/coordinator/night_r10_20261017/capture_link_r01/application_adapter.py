"""D4 application-binding adapter for the R10 capture continuation.

Only build_application is exposed. No source loading or output at import.
The coordinator replaces only D4's application module descriptor with this
adapter; all source validation and permission refusals remain in frozen code.
"""
import hashlib as _hashlib
from pathlib import Path as _Path
import re as _re
import types as _types

_ROOT = _Path(__file__).resolve().parents[7]
_OUTPUT = _ROOT / 'code/output/m3_c9_chain_night_r10_20261017'
_SOURCE = (_ROOT / 'code/software/m3_pro_fourvoice_trace_20261016/'
           'pro_basis_r08_20261017/coordinator/night_r10_20261017/admission/adapter.py')
_SOURCE_SHA = '91ef6b5e0f757edc3e50363c10ff5196af6ffa6d5d42e1fc6d377ee614eb1c90'


def build_application(request, out):
    """Same D4 API, restricted to a fresh R10 output descendant.

    Only the exact, previously published R10 admission adapter is loaded.
    It creates the directory exclusively and retains its old result/derivation
    artifacts. This wrapper cannot grant execution, start a tool or change the
    original D4 output constant/module or an existing module cache.
    """
    output = _Path(out)
    if str(output).startswith(('\\\\', '\\??\\')):
        raise ValueError('CAPTURE_LINK_OUTPUT_ALIAS')
    for part in output.parts:
        if (part.rstrip(' .') != part
                or _re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part)):
            raise ValueError('CAPTURE_LINK_OUTPUT_ALIAS')
    for part in (output, *output.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('CAPTURE_LINK_OUTPUT_ALIAS')
    output = output.resolve()
    if output == _OUTPUT or not output.is_relative_to(_OUTPUT):
        raise ValueError('CAPTURE_LINK_R10_OUTPUT_SCOPE')
    source = _SOURCE
    for part in (source, *source.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('CAPTURE_LINK_SOURCE_ALIAS')
    raw = source.read_bytes()
    if _hashlib.sha256(raw).hexdigest() != _SOURCE_SHA:
        raise ValueError('CAPTURE_LINK_ADMISSION_SOURCE_SHA')
    module = _types.ModuleType('_capture_link_r10_admission_' + _SOURCE_SHA[:20])
    module.__file__, module.__package__ = str(source), ''
    exec(compile(raw, str(source), 'exec', dont_inherit=True), module.__dict__)
    result = module.build_application(request, output)
    if _hashlib.sha256(source.read_bytes()).hexdigest() != _SOURCE_SHA:
        raise ValueError('CAPTURE_LINK_ADMISSION_SOURCE_CHANGED')
    if (not isinstance(result, dict) or result.get('schema') != 'M3_C9_APPLICATION_BUILD_RESULT_V1'
            or result.get('execution_allowed') is not False or result.get('real_pass') is not False
            or result.get('board_release_allowed') is not False):
        raise ValueError('CAPTURE_LINK_APPLICATION_RESULT_AUTHORITY')
    return result
