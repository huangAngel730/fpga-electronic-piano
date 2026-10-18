"""Exact disk-backed uniqueness with a bounded set of mutable live objects."""
import json
import sqlite3
from identity_guard import require


def encode(value):
    if type(value) is set:
        return {'__stages__': sorted(value)}
    raise TypeError(type(value).__name__)


def decode(value):
    return set(value['__stages__']) if set(value) == {'__stages__'} else value


class Store:
    def __init__(self, path, budget):
        require(not path.exists(), 'LIFECYCLE_DB_EXISTS')
        self.budget = budget
        self.db = sqlite3.connect(path)
        escaped = str(path.parent.resolve()).replace("'", "''")
        self.db.execute("PRAGMA temp_store_directory='" + escaped + "'")
        for statement in ('page_size=4096', 'cache_size=-8192', 'temp_store=FILE',
                          'mmap_size=0', 'max_page_count=131072', 'journal_mode=DELETE',
                          'synchronous=FULL'):
            self.db.execute('PRAGMA ' + statement)
        self.db.execute('CREATE TABLE history(kind TEXT,epoch INTEGER,id INTEGER,'
                        'terminal INTEGER NOT NULL,body TEXT NOT NULL,'
                        'PRIMARY KEY(kind,epoch,id)) WITHOUT ROWID')
        self.db.commit()

    def mapping(self, kind, epoch, max_live=128):
        return DiskMap(self, kind, epoch, max_live)

    def close(self):
        self.db.commit()
        self.db.close()
        self.budget.check_disk()


class DiskMap:
    def __init__(self, store, kind, epoch, max_live):
        self.store, self.kind, self.epoch = store, kind, epoch
        self.live, self.max_live = {}, max_live

    def __contains__(self, key):
        return self.store.db.execute('SELECT 1 FROM history WHERE kind=? AND epoch=? AND id=?',
                                     (self.kind, self.epoch, key)).fetchone() is not None

    def __setitem__(self, key, value):
        require(type(key) is int and 0 <= key <= (1 << 32) - 1, 'ID_RANGE')
        require(key not in self, 'DUPLICATE_REQUEST_ID_IN_EPOCH' if self.kind == 'request'
                else 'DUPLICATE_ROUTER_SEQUENCE', key)
        require(len(self.live) < self.max_live, 'ACTIVE_STATE_LIMIT', self.kind, 'RESOURCE_LIMIT')
        self.store.budget.reserve_scratch(32768)
        self.store.db.execute('INSERT INTO history VALUES(?,?,?,?,?)',
                             (self.kind, self.epoch, key, 0, '{}'))
        self.live[key] = value
        self.checkpoint(key)

    def __getitem__(self, key):
        if key in self.live:
            return self.live[key]
        row = self.store.db.execute('SELECT body FROM history WHERE kind=? AND epoch=? AND id=?',
                                    (self.kind, self.epoch, key)).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0], object_hook=decode)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def values(self):
        # Legacy per-clock scans see ONLY the bounded live working set.
        return self.live.values()

    def items(self):
        return self.live.items()

    def checkpoint(self, key):
        if key not in self.live:
            return
        raw = json.dumps(self.live[key], default=encode, separators=(',', ':'), allow_nan=False)
        require(len(raw.encode()) <= 16384, 'LIFECYCLE_RECORD_LIMIT')
        self.store.budget.reserve_scratch(32768)
        self.store.db.execute('UPDATE history SET body=? WHERE kind=? AND epoch=? AND id=?',
                             (raw, self.kind, self.epoch, key))

    def retire(self, key):
        self.checkpoint(key)
        self.store.db.execute('UPDATE history SET terminal=1 WHERE kind=? AND epoch=? AND id=?',
                             (self.kind, self.epoch, key))
        del self.live[key]

    def checkpoint_all(self):
        for key in tuple(self.live):
            self.checkpoint(key)
        self.store.db.commit()
        self.store.budget.check_disk()
