"""Static R13 candidate. Locked byte identity, never a per-row raw hash."""
import ctypes
import hashlib
import os
from pathlib import Path

CHUNK = 1 << 20


class ContractError(ValueError):
    def __init__(self, code, where='', status='CONTRACT_REJECTED'):
        super().__init__(code + ':' + str(where))
        self.code, self.where, self.status = code, str(where), status


def require(ok, code, where='', status='CONTRACT_REJECTED'):
    if not ok:
        raise ContractError(code, where, status)


def safe_path(root, relative):
    require(type(relative) is str and relative and '\\' not in relative,
            'ARTIFACT_PATH_ESCAPE', relative)
    rel = Path(relative)
    require(not rel.is_absolute() and not rel.drive and ':' not in relative
            and '..' not in rel.parts, 'ARTIFACT_PATH_ESCAPE', relative)
    path = (Path(root).resolve() / rel).resolve()
    require(path.is_relative_to(Path(root).resolve()), 'ARTIFACT_PATH_ESCAPE', relative)
    return path


def stat_key(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


class LockedInput:
    """Keep Windows deny-write/delete handle until all audits are finalized."""
    def __init__(self, root, desc, role, tick=lambda: None):
        self.desc, self.role, self.tick = desc, role, tick
        self.path = safe_path(root, desc['path'])
        require(type(desc['bytes']) is int and desc['bytes'] >= 0, 'ARTIFACT_BYTES', role)
        value = desc['sha256']
        require(type(value) is str and len(value) == 64
                and set(value) <= set('0123456789abcdef'), 'ARTIFACT_SHA', role)
        require(os.name == 'nt', 'INPUT_LOCK_UNAVAILABLE', role, 'PENDING_INPUT')
        import msvcrt
        from ctypes import wintypes as w
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                      w.DWORD, w.DWORD, w.HANDLE]
        kernel.CreateFileW.restype = w.HANDLE
        handle = kernel.CreateFileW(str(self.path), 0x80000000, 1, None, 3, 0x80, None)
        require(handle not in (None, ctypes.c_void_p(-1).value),
                'INPUT_IDENTITY_CHANGED_OR_LOCK_VIOLATION', role)
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        self.file = os.fdopen(fd, 'rb', buffering=0)
        self.key = stat_key(os.fstat(self.file.fileno()))
        self.hash_bytes, self.passes = 0, 0
        try:
            require(self.key[2] == desc['bytes'], 'ARTIFACT_BYTES_MISMATCH', role)
            self.check_path()
        except BaseException:
            self.file.close()
            raise

    def check_path(self):
        require(stat_key(os.fstat(self.file.fileno())) == self.key
                and stat_key(self.path.stat()) == self.key,
                'INPUT_IDENTITY_CHANGED_OR_LOCK_VIOLATION', self.role)

    def chunks(self):
        self.check_path()
        self.file.seek(0)
        digest, count = hashlib.sha256(), 0
        self.passes += 1
        require(self.passes <= 3, 'HASH_PASS_BUDGET', self.role)
        while True:
            self.tick()
            raw = self.file.read(CHUNK)
            if not raw:
                break
            count += len(raw)
            self.hash_bytes += len(raw)
            require(count <= self.desc['bytes'], 'ARTIFACT_BYTES_MISMATCH', self.role)
            digest.update(raw)
            yield raw
        require(count == self.desc['bytes'] and digest.hexdigest() == self.desc['sha256'],
                'ARTIFACT_BYTES_MISMATCH', self.role)
        self.check_path()

    def verify(self):
        for _ in self.chunks():
            pass

    def close(self):
        self.file.close()
