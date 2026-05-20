"""
Filebase document store — each DB table is a JSON file in Filebase S3.
Read/write only the affected file per operation.
"""

import json
import threading
from datetime import datetime, date
from enum import Enum
from sqlalchemy import (
    ColumnElement, Column, DateTime, Date, String, Integer, Float, Boolean, Text,
    Enum as SAEnum,
)
import boto3
from botocore.exceptions import ClientError
from config import settings

_lock = threading.Lock()
_cache = {}       # table_name -> list of dicts
_dirty_tables = set()

S3_ENDPOINT = settings.FILEBASE_ENDPOINT
ACCESS_KEY = settings.FILEBASE_ACCESS_KEY
SECRET_KEY = settings.FILEBASE_SECRET_KEY
BUCKET = settings.FILEBASE_BUCKET


def _client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
    )


def _table_name(model_class):
    """Get the Filebase JSON filename for a model class."""
    if hasattr(model_class, "__tablename__"):
        return f"{model_class.__tablename__}.json"
    return f"{model_class.__name__}.json"


def _to_dict(obj):
    """Convert a model instance or dict to a JSON-safe dict."""
    if isinstance(obj, dict):
        return obj
    d = {}
    for col in obj._sa_class_manager.class_.__table__.columns:
        val = getattr(obj, col.name, None)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        elif isinstance(val, Enum):
            val = val.value
        d[col.name] = val
    return d


def _from_dict(model_class, data):
    """Convert a JSON dict back to a model instance."""
    from sqlalchemy import Enum as SAEnum
    from enum import Enum
    import importlib
    inst = model_class()
    # Get the module where the model is defined (contains enum classes)
    try:
        model_module = importlib.import_module(model_class.__module__)
    except (ImportError, ValueError):
        model_module = None
    for col in model_class.__table__.columns:
        val = data.get(col.name)
        if val is not None:
            if isinstance(col.type, (DateTime, Date)):
                from datetime import datetime, date
                if isinstance(col.type, Date) and isinstance(val, str):
                    val = date.fromisoformat(val)
                elif isinstance(col.type, DateTime) and isinstance(val, str):
                    val = datetime.fromisoformat(val)
            elif isinstance(col.type, SAEnum) and hasattr(col.type, 'enums') and isinstance(val, str) and model_module:
                # Try to reconstruct the Python enum value
                enum_values = col.type.enums
                if val in enum_values:
                    for name in dir(model_module):
                        obj = getattr(model_module, name, None)
                        if isinstance(obj, type) and issubclass(obj, Enum) and hasattr(obj, '__members__'):
                            if val in obj.__members__ or val in [m.value for m in obj.__members__.values()]:
                                try:
                                    val = obj(val)
                                except (ValueError, TypeError):
                                    pass
                                break
        setattr(inst, col.name, val)
    return inst


def load_table(model_class):
    """Fetch a table's JSON from Filebase (or cache), return list of dicts."""
    name = _table_name(model_class)
    with _lock:
        if name in _cache:
            return _cache[name]
    try:
        resp = _client().get_object(Bucket=BUCKET, Key=f"db/{name}")
        data = json.loads(resp["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            data = []
        else:
            raise
    with _lock:
        _cache[name] = data
    return data


def save_table(model_class):
    """Write a table's cached JSON back to Filebase."""
    name = _table_name(model_class)
    with _lock:
        data = _cache.get(name, [])
    body = json.dumps(data, default=str, indent=2).encode("utf-8")
    _client().put_object(Bucket=BUCKET, Key=f"db/{name}", Body=body)
    with _lock:
        _dirty_tables.discard(name)


def mark_dirty(model_class):
    name = _table_name(model_class)
    with _lock:
        _dirty_tables.add(name)


def _get_pk(model_class):
    """Return the primary key column name."""
    for col in model_class.__table__.columns:
        if col.primary_key:
            return col.name
    return "id"


def _make_id(model_class):
    """Generate a new auto-increment ID."""
    rows = load_table(model_class)
    pk = _get_pk(model_class)
    ids = [r.get(pk, 0) or 0 for r in rows]
    return max(ids) + 1 if ids else 1


class FilebaseQuery:
    """Replacement for SQLAlchemy Query — supports filter, order_by, first, all, count, delete."""

    def __init__(self, model_class):
        self._model = model_class
        self._filters = []
        self._order = []
        self._offset_val = None
        self._limit_val = None

    def filter(self, *exprs):
        for expr in exprs:
            self._filters.append(expr)
        return self

    def join(self, *args, **kwargs):
        # No-op: document store doesn't need JOINs (data is already denormalized)
        return self

    def filter_by(self, **kwargs):
        for k, v in kwargs.items():
            col = getattr(self._model, k, None)
            if col is None:
                raise ValueError(f"Unknown column: {k}")
            self._filters.append(col == v)
        return self

    def order_by(self, *exprs):
        self._order.extend(exprs)
        return self

    def offset(self, n):
        self._offset_val = n
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def _rows(self):
        all_rows = load_table(self._model)
        pk = _get_pk(self._model)
        results = []

        for row in all_rows:
            match = True
            for expr in self._filters:
                if not _evaluate(expr, row):
                    match = False
                    break
            if match:
                results.append(row)

        # ordering
        for expr in self._order:
            reverse = _is_desc(expr)
            col_name = _get_col_name(expr)
            if col_name:
                results.sort(key=lambda r: (r.get(col_name) or ""), reverse=reverse)

        # offset/limit
        if self._offset_val:
            results = results[self._offset_val:]
        if self._limit_val:
            results = results[:self._limit_val]

        return [_from_dict(self._model, r) for r in results]

    def all(self):
        return self._rows()

    def first(self):
        rows = self._rows()
        return rows[0] if rows else None

    def count(self):
        return len(self._rows())

    def delete(self, synchronize_session=False):
        """Delete all matching rows from the table."""
        all_rows = load_table(self._model)
        pk = _get_pk(self._model)
        to_delete_ids = set()
        for row in all_rows:
            match = True
            for expr in self._filters:
                if not _evaluate(expr, row):
                    match = False
                    break
            if match:
                to_delete_ids.add(row.get(pk))
        name = _table_name(self._model)
        with _lock:
            _cache[name] = [r for r in _cache.get(name, []) if r.get(pk) not in to_delete_ids]
        mark_dirty(self._model)
        return len(to_delete_ids)

    def __iter__(self):
        return iter(self._rows())

    def __bool__(self):
        return self.first() is not None


def _get_col_name(expr):
    """Extract column name from a SQLAlchemy expression."""
    if isinstance(expr, ColumnElement):
        return str(expr.key) if hasattr(expr, 'key') else str(expr.name) if hasattr(expr, 'name') else None
    if hasattr(expr, 'element'):
        return _get_col_name(expr.element)
    return None


def _evaluate(expr, row):
    """Evaluate a SQLAlchemy filter expression against a dict row."""
    from sqlalchemy.sql import operators
    from sqlalchemy import UnaryExpression

    if isinstance(expr, UnaryExpression):
        if expr.modifier == operators.desc_op:
            return True  # used in order_by, not filter
        return True

    left = expr.left if hasattr(expr, 'left') else None
    right = expr.right if hasattr(expr, 'right') else None
    op = expr.operator if hasattr(expr, 'operator') else None

    col_name = _get_col_name(left)
    if not col_name:
        return True

    row_val = row.get(col_name)
    row_val = _normalize(row_val)
    r_val = _right_value(right)

    if op is operators.eq:
        return row_val == r_val
    elif op is operators.ne:
        return row_val != r_val
    elif op is operators.gt:
        return (row_val or 0) > r_val
    elif op is operators.lt:
        return (row_val or 0) < r_val
    elif op is operators.ge:
        return (row_val or 0) >= r_val
    elif op is operators.le:
        return (row_val or 0) <= r_val
    elif op is operators.like_op or op is operators.contains_op:
        if row_val is None:
            return False
        pattern = str(r_val).replace("%", "")
        if op is operators.contains_op:
            return pattern.lower() in str(row_val).lower()
        return pattern.lower() in str(row_val).lower()
    elif op is operators.in_op:
        return row_val in r_val
    elif op is operators.is_:
        if r_val is None:
            return row_val is None
        return row_val is r_val
    elif op is operators.is_not:
        if r_val is None:
            return row_val is not None
        return row_val is not r_val

    return True


def _right_value(right):
    """Extract the right-side value from an expression."""
    from sqlalchemy.sql.elements import True_, False_, Null
    if isinstance(right, True_):
        return True
    if isinstance(right, False_):
        return False
    if isinstance(right, Null):
        return None
    if hasattr(right, 'value'):
        return right.value
    if hasattr(right, 'element'):
        return _right_value(right.element)
    if isinstance(right, Column):
        return None
    if hasattr(right, '_arg'):
        return right._arg
    if isinstance(right, (str, int, float, bool)):
        return right
    return right


def _normalize(val):
    """Convert ISO datetime strings to comparable types."""
    from datetime import datetime, date
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            pass
        try:
            return date.fromisoformat(val)
        except (ValueError, TypeError):
            pass
    return val


def _is_desc(expr):
    """Check if an order_by expression is DESC."""
    from sqlalchemy.sql import operators
    from sqlalchemy import UnaryExpression
    if isinstance(expr, UnaryExpression) and hasattr(expr, 'modifier'):
        return expr.modifier is operators.desc_op
    return False


class FilebaseSession:
    """
    Drop-in replacement for SQLAlchemy Session.
    Same .query().filter().first() / .add() / .delete() / .commit() API.
    Backed by Filebase JSON files.
    """

    def __init__(self):
        self._new = []
        self._deleted = []
        self._modified = set()

    def query(self, model_class):
        return FilebaseQuery(model_class)

    def add(self, obj):
        self._new.append(obj)

    def add_all(self, objs):
        self._new.extend(objs)

    def delete(self, obj):
        self._deleted.append(obj)

    def merge(self, obj):
        """Mark an existing object as modified (re-save on commit)."""
        pk = _get_pk(obj.__class__)
        pk_val = getattr(obj, pk, None)
        if pk_val is not None:
            self._modified.add((obj.__class__, pk_val))
        return obj

    def commit(self):
        """Persist all pending changes to Filebase."""
        # 1. Deletes
        for obj in self._deleted:
            model = obj.__class__
            pk = _get_pk(model)
            pk_val = getattr(obj, pk, None)
            rows = load_table(model)
            name = _table_name(model)
            with _lock:
                _cache[name] = [r for r in rows if r.get(pk) != pk_val]
            mark_dirty(model)

        # 2. New objects
        for obj in self._new:
            model = obj.__class__
            pk = _get_pk(model)
            pk_val = getattr(obj, pk, None)
            if pk_val is None:
                pk_val = _make_id(model)
                setattr(obj, pk, pk_val)
            rows = load_table(model)
            d = _to_dict(obj)
            # replace if exists
            name = _table_name(model)
            with _lock:
                existing = [r for r in _cache.get(name, []) if r.get(pk) != pk_val]
                existing.append(d)
                _cache[name] = existing
            mark_dirty(model)

        # 3. Modified objects (from merge)
        for model_class, pk_val in self._modified:
            name = _table_name(model_class)
            with _lock:
                rows = _cache.get(name, [])
            for i, r in enumerate(rows):
                if r.get(_get_pk(model_class)) == pk_val:
                    rows[i] = r
                    break
            mark_dirty(model_class)

        # 4. Flush all dirty tables to Filebase
        for name in list(_dirty_tables):
            with _lock:
                data = _cache.get(name, [])
            body = json.dumps(data, default=str, indent=2).encode("utf-8")
            try:
                _client().put_object(Bucket=BUCKET, Key=f"db/{name}", Body=body)
            except Exception as e:
                print(f"[Filebase] Commit error for {name}: {e}")
                raise

        with _lock:
            _dirty_tables.clear()
        self._new.clear()
        self._deleted.clear()
        self._modified.clear()

    def rollback(self):
        self._new.clear()
        self._deleted.clear()
        self._modified.clear()

    def close(self):
        pass

    def refresh(self, obj):
        """Reload an object from its table."""
        model = obj.__class__
        pk = _get_pk(model)
        pk_val = getattr(obj, pk, None)
        if pk_val is not None:
            rows = load_table(model)
            for r in rows:
                if r.get(pk) == pk_val:
                    for col in model.__table__.columns:
                        val = r.get(col.name)
                        setattr(obj, col.name, val)
                    break
        return obj

    def execute(self, stmt):
        """Minimal text() support — for raw SQL migrations we ignore."""
        from sqlalchemy.sql.elements import TextClause
        if isinstance(stmt, TextClause):
            return _DummyResult()
        return _DummyResult()

    def scalar(self):
        return None

    def scalar(self):
        """Return a single scalar value (e.g. from func.sum, func.count)."""
        # Check if this is an aggregate query (func.sum, func.count, etc.)
        if not self._filters:
            return None
        # If any filter looks like an aggregate, compute it
        for expr in self._filters:
            if _is_aggregate(expr):
                return _compute_aggregate(expr, load_table(self._model))
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _is_aggregate(expr):
    """Check if an expression is an aggregate function call like func.sum()."""
    from sqlalchemy.sql.elements import Label
    if isinstance(expr, Label):
        return _is_aggregate(expr.element)
    name = getattr(expr, 'name', '') or ''
    return name in ('sum', 'count', 'avg', 'min', 'max')


def _compute_aggregate(expr, rows):
    """Compute an aggregate function over rows."""
    from sqlalchemy.sql.elements import Label
    # Unwrap Label
    if isinstance(expr, Label):
        expr = expr.element
    agg_name = getattr(expr, 'name', '') or ''
    # Get the column being aggregated
    col_expr = getattr(expr, 'expr', None) or getattr(expr, 'clause_expr', None)
    col_name = _get_col_name(col_expr or expr)
    if not col_name:
        return 0
    values = [r.get(col_name, 0) or 0 for r in rows]
    if agg_name == 'sum':
        import numbers
        return sum(v for v in values if isinstance(v, numbers.Number))
    elif agg_name == 'count':
        return len(values)
    elif agg_name == 'avg':
        import numbers
        nums = [v for v in values if isinstance(v, numbers.Number)]
        return sum(nums) / len(nums) if nums else 0
    elif agg_name == 'min':
        return min(values) if values else 0
    elif agg_name == 'max':
        return max(values) if values else 0
    return 0


class _DummyResult:
    def scalar(self):
        return None
    def all(self):
        return []
    def first(self):
        return None
    def fetchone(self):
        return None


# Re-initialize from Filebase (clear cache to force re-read)
def reset_cache():
    with _lock:
        _cache.clear()
        _dirty_tables.clear()


# Auto-sync: pull latest data from Filebase before each request
def sync_from_filebase(model_class):
    """Force re-read a table from Filebase, bypassing cache."""
    name = _table_name(model_class)
    with _lock:
        _cache.pop(name, None)
    return load_table(model_class)
