"""
A minimal in-memory stand-in for the ``frappe`` module.

Why: the interesting logic of this app (scanning apps, de-duplicating the log,
merging the CSV, throttling the boot hook) is worth testing without a bench, a
MariaDB, a Redis and a running site. The stub implements exactly the API
surface this app uses, and records every call so tests can assert on behaviour
(for example: "the boot hook scanned only once thanks to the cache").

It is only ever installed into ``sys.modules`` by the test suite.
"""

from __future__ import annotations

import datetime
import sys
import types
from pathlib import Path


def now_datetime():
    return datetime.datetime(2025, 1, 1, 12, 0, 0)


def cstr(value):
    return "" if value is None else str(value)


class _AttrDict(dict):
    """dict with attribute access, like frappe._dict."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class Recorder:
    """Collects calls so tests can assert on them."""

    def __init__(self):
        self.calls = []

    def record(self, *args, **kwargs):
        self.calls.append((args, kwargs))

    def __len__(self):
        return len(self.calls)


class FakeLogger(Recorder):
    def info(self, message, *args, **kwargs):
        self.record("info", message)

    def warning(self, message, *args, **kwargs):
        self.record("warning", message)

    def error(self, message, *args, **kwargs):
        self.record("error", message, kwargs.get("exc_info"))

    def debug(self, message, *args, **kwargs):
        self.record("debug", message)


class FakeCache(Recorder):
    def __init__(self):
        super().__init__()
        self.store = {}

    def __call__(self):
        return self

    def get_value(self, key, *args, **kwargs):
        self.record("get_value", key)
        return self.store.get(key)

    def set_value(self, key, value, *args, **kwargs):
        self.record("set_value", key, value)
        if value is None:
            self.store.pop(key, None)
        else:
            self.store[key] = value

    def delete_value(self, key, *args, **kwargs):
        self.record("delete_value", key)
        self.store.pop(key, None)


class FakeDoc(Recorder):
    def __init__(self, values):
        super().__init__()
        self.values = dict(values)
        for key, value in values.items():
            setattr(self, key, value)

    def insert(self, *args, **kwargs):
        self.record("insert", kwargs)
        self.db_insert(self.values)

    def db_insert(self, values):  # replaced by the stub factory
        raise NotImplementedError


class FakeDB(Recorder):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def get_default(self, key, *args, **kwargs):
        self.record("get_default", key)
        return self.state.defaults.get(key)

    def count(self, doctype, filters=None, *args, **kwargs):
        self.record("count", doctype)
        return len(self.state.filter_records(doctype, filters))

    def set_value(self, doctype, name, values, *args, **kwargs):
        self.record("set_value", doctype, name)
        for record in self.state.tables.setdefault(doctype, []):
            if record.get("name") == name:
                record.update(values)
                return

    def exists(self, doctype, filters=None, *args, **kwargs):
        self.record("exists", doctype)
        return bool(self.state.filter_records(doctype, filters))

    def commit(self):
        self.record("commit")

    def rollback(self):
        self.record("rollback")


class FakeState:
    """Tables, defaults and the app registry of the fake site."""

    def __init__(self, apps_root: Path, installed):
        self.apps_root = Path(apps_root)
        self.installed = list(installed)
        self.tables = {}
        self.defaults = {"language": "zh"}
        self.scan_calls = 0
        self.enqueued = []
        self.logger = FakeLogger()
        self.cache = FakeCache()
        self.conf = _AttrDict()
        self.counter = 0

    # ---- helpers ----
    def table(self, doctype):
        return self.tables.setdefault(doctype, [])

    def insert(self, values):
        self.counter += 1
        record = dict(values)
        record.setdefault("name", f"MTL-{self.counter:04d}")
        self.table(values["doctype"]).append(record)
        return record

    @staticmethod
    def _matches(record, filters):
        if not filters:
            return True
        if isinstance(filters, dict):
            filters = [filters]
        for condition in filters:
            for field, expected in condition.items():
                if record.get(field) != expected:
                    return False
        return True

    def filter_records(self, doctype, filters=None, or_filters=None):
        records = list(self.table(doctype))
        if or_filters:
            if isinstance(or_filters, dict):
                or_filters = [or_filters]
            records = [r for r in records if any(self._matches(r, [c]) for c in or_filters)]
        if filters:
            records = [r for r in records if self._matches(r, filters)]
        return records


def install(apps_root, installed, *, user="Administrator", lang="zh", conf=None):
    """Install the stub as ``frappe`` in ``sys.modules`` and return its state."""
    state = FakeState(apps_root, installed)
    if conf:
        state.conf.update(conf)

    # Reuse the same module object across installs: modules that did
    # `import frappe` at import time (custom_translations.utils) keep a
    # reference to it, so replacing sys.modules would leave them talking to a
    # stale fake site.
    module = sys.modules.get("frappe")
    if not getattr(module, "_is_ct_stub", False):
        module = types.ModuleType("frappe")
        module._is_ct_stub = True
        sys.modules["frappe"] = module
    module._state = state

    # ---- paths & registry ----
    module.get_app_path = lambda app, *joins: str(
        Path(state.apps_root).joinpath(app, app, *joins)
    )
    module.get_installed_apps = lambda *args, **kwargs: list(state.installed)
    module.get_app = lambda app: types.SimpleNamespace(name=app)

    # ---- session / local ----
    module.session = _AttrDict({"user": user})
    module.local = _AttrDict({"lang": lang, "site": "test.local"})
    module.conf = state.conf
    module.flags = _AttrDict()

    # ---- db ----
    module.db = FakeDB(state)
    module.get_all = _get_all(state)
    module.get_list = module.get_all
    module.get_value = lambda *args, **kwargs: None

    def get_doc(arg, *args, **kwargs):
        values = dict(arg) if isinstance(arg, dict) else {"doctype": arg}
        doc = FakeDoc(values)
        doc.db_insert = state.insert
        return doc

    module.get_doc = get_doc
    module.new_doc = lambda doctype: get_doc({"doctype": doctype})
    module.logger = lambda *args, **kwargs: state.logger
    module.cache = state.cache
    module.clear_cache = lambda *args, **kwargs: state.cache.record("clear_cache")

    def enqueue(method, **kwargs):
        state.enqueued.append({"method": method, **kwargs})

    module.enqueue = enqueue
    module.msgprint = lambda *args, **kwargs: None

    # ---- frappe.utils ----
    utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
    utils.now_datetime = now_datetime
    utils.nowdate = lambda: "2025-01-01"
    utils.cstr = cstr
    utils.flt = lambda value, precision=None: float(value or 0)
    module.utils = utils

    # ---- frappe.model ----
    model = sys.modules.get("frappe.model") or types.ModuleType("frappe.model")
    sync = types.ModuleType("frappe.model.sync")
    sync.sync_for = lambda *args, **kwargs: None
    model.sync = sync
    module.model = model

    sys.modules["frappe"] = module
    sys.modules["frappe.utils"] = utils
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.sync"] = sync
    return state


def _get_all(state):
    def get_all(doctype, filters=None, or_filters=None, fields=None, pluck=None,
                limit_page_length=None, order_by=None, **kwargs):
        state.logger.record("get_all", doctype)
        records = state.filter_records(doctype, filters, or_filters)
        if limit_page_length:
            records = records[:limit_page_length]
        if pluck:
            return [record.get(pluck) for record in records]
        if fields:
            return [{field: record.get(field) for field in fields} for record in records]
        return records

    return get_all
