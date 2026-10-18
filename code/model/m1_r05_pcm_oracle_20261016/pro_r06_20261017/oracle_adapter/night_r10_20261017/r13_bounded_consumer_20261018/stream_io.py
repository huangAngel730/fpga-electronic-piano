"""Byte-exact logical streams; JSONL may cross transport-volume boundaries."""
import hashlib
import json
from identity_guard import LockedInput, require


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'DUPLICATE_JSON_KEY', key)
        result[key] = value
    return result


def noninteger(value):
    require(False, 'NONINTEGER_JSON_NUMBER', value)


def loads(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_float=noninteger, parse_constant=noninteger)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


class LogicalStream:
    def __init__(self, root, desc, role, *, max_bytes, max_line, max_rows, tick):
        self.desc, self.role = desc, role
        self.max_line, self.max_rows, self.count = max_line, max_rows, 0
        require(type(desc['bytes']) is int and 0 < desc['bytes'] <= max_bytes,
                'INPUT_SIZE_LIMIT', role)
        self.inputs = []
        self.complete = False
        parts = desc.get('parts')
        if parts is None:
            parts = [{**desc, 'offset': 0}]
        require(type(parts) is list and 0 < len(parts) <= 512, 'VOLUME_COUNT', role)
        offset, paths, physical_ids = 0, set(), set()
        try:
            for part in parts:
                require(part['path'] not in paths and part.get('offset') == offset,
                        'LOGICAL_FILE_SHA_OR_SOURCE_ORDER', role)
                paths.add(part['path'])
                require(type(part['bytes']) is int and part['bytes'] > 0,
                        'VOLUME_OR_LOGICAL_EOF_MISMATCH', role)
                if 'parts' in desc:
                    require(part['bytes'] <= 64 << 20, 'VOLUME_SIZE_LIMIT', role)
                offset += part['bytes']
                stream = LockedInput(root, part, role, tick)
                self.inputs.append(stream)
                require(stream.key[:2] not in physical_ids, 'DUPLICATE_VOLUME_FILE_ID', role)
                physical_ids.add(stream.key[:2])
            require(offset == desc['bytes'], 'VOLUME_OR_LOGICAL_EOF_MISMATCH', role)
        except BaseException:
            self.close()
            raise

    def lines(self):
        digest, size, pending = hashlib.sha256(), 0, bytearray()
        for stream in self.inputs:
            for block in stream.chunks():
                digest.update(block)
                size += len(block)
                pending.extend(block)
                while True:
                    end = pending.find(b'\n')
                    if end < 0:
                        break
                    require(end + 1 <= self.max_line, 'LINE_BYTES_LIMIT', self.role)
                    raw = bytes(pending[:end + 1])
                    del pending[:end + 1]
                    self.count += 1
                    require(self.count <= self.max_rows, 'ROW_COUNT_LIMIT', self.role)
                    require(bool(raw.strip()), 'EMPTY_LOGICAL_LINE', self.role)
                    yield self.count, raw
                require(len(pending) <= self.max_line, 'LINE_BYTES_LIMIT', self.role)
        if pending:
            self.count += 1
            require(self.count <= self.max_rows and bool(pending.strip()),
                    'ROW_COUNT_LIMIT', self.role)
            yield self.count, bytes(pending)
        require(size == self.desc['bytes'] and digest.hexdigest() == self.desc['sha256'],
                'VOLUME_OR_LOGICAL_EOF_MISMATCH', self.role)
        if 'rows' in self.desc:
            require(self.count == self.desc['rows'], 'ROW_COUNT_MISMATCH', self.role)
        self.complete = True

    def records(self):
        for number, raw in self.lines():
            value = loads(raw)
            require(type(value) is dict, 'ROW_OBJECT', self.role)
            yield number, raw, value

    def final_verify(self):
        require(self.complete, 'UNCONSUMED_INPUT_EOF', self.role)
        for stream in self.inputs:
            stream.verify()

    def close(self):
        for stream in self.inputs:
            stream.close()


def small_json(root, desc, role, tick=lambda: None, limit=16 << 20):
    require(type(desc['bytes']) is int and desc['bytes'] <= limit, 'METADATA_SIZE_LIMIT', role)
    stream = LockedInput(root, desc, role, tick)
    try:
        raw = b''.join(stream.chunks())  # bounded small metadata only
        return loads(raw), stream
    except BaseException:
        stream.close()
        raise
