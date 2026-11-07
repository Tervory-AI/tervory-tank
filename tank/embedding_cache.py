"""Opt-in C4 vectors: tenant, encoder revision, dimensions and exact text digest."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import math
import json
import os
from threading import Lock
import time
import uuid

from qdrant_client import QdrantClient, models

TTL = 7 * 86400
MAX_ENTRIES = 1024
_scope = ContextVar("embedding_cache_tenant", default=None)
_measure = ContextVar('embedding_cache_measurement', default=None)
_cache = None
_init_lock = Lock()


class Measurement:
    def __init__(self):
        self.lock = Lock()
        self.values = dict(attempts=0, hits=0, saved_usd=0., saved_compute_ms=0.)

    def add(self, values):
        with self.lock:
            for key in self.values:
                value = values.get(key, 0)
                if type(value) in {int, float} and math.isfinite(value) and value >= 0:
                    self.values[key] += value


@contextmanager
def measure():
    counter = Measurement()
    token = _measure.set(counter)
    try:
        yield counter
    finally:
        _measure.reset(token)


def merge(values):
    counter = _measure.get()
    if counter is not None and isinstance(values, dict):
        counter.add(values)


class VectorCache:
    def __init__(self, client=None):
        self.client = client
        self.local = OrderedDict()
        self.lock = Lock()
        self.stripes = [Lock() for _ in range(64)]
        self.collections = set()
        self.swept = OrderedDict()

    def store(self):
        if self.client is None:
            # DECISION reuse regional Qdrant; no new service, dependency or raw text.
            self.client = QdrantClient(url=os.environ.get('QDRANT_URL', 'http://qdrant:6333'),
                api_key=os.environ.get('QDRANT_API_KEY') or None, timeout=1,
                check_compatibility=False, trust_env=False, follow_redirects=False)
        return self.client

    def collection(self, model, dimensions):
        name = 'tank_c4_' + hashlib.sha256(f'{model}:{dimensions}'.encode()).hexdigest()
        with self.lock:
            if name not in self.collections:
                client = self.store()
                if not client.collection_exists(name):
                    try:
                        # DOT preserves the original vector; COSINE would normalize it.
                        client.create_collection(name, vectors_config=models.VectorParams(
                            size=dimensions, distance=models.Distance.DOT, on_disk=True),
                            hnsw_config=models.HnswConfigDiff(m=0), on_disk_payload=True)
                    except Exception:
                        if not client.collection_exists(name):
                            raise
                self.collections.add(name)
        return name

    @staticmethod
    def valid(entry, key, dimensions, tenant_key):
        if not isinstance(entry, dict) or entry.get('key') != key or entry.get('tenant') != tenant_key:
            return False
        if any(type(entry.get(k)) not in {int, float} or not math.isfinite(entry[k]) or entry[k] < 0
               for k in ('expires', 'compute_ms')) or entry['expires'] <= time.time():
            return False
        vector = entry.get('vector')
        return (isinstance(vector, list) and len(vector) == dimensions
                and all(type(v) in {float, int} and math.isfinite(v) for v in vector))

    def embed(self, tenant, model, text, dimensions, compute):
        tenant_key = hashlib.sha256(str(tenant).encode()).hexdigest()
        key = hashlib.sha256(json.dumps([tenant_key, model, dimensions, text],
                                      ensure_ascii=False).encode()).hexdigest()
        with self.stripes[int(key[:8], 16) % len(self.stripes)]:
            with self.lock:
                entry = self.local.get(key)
            name, point = None, str(uuid.UUID(key[:32]))
            if not self.valid(entry, key, dimensions, tenant_key):
                try:
                    name = self.collection(model, dimensions)
                    rows = self.store().retrieve(name, [point], with_vectors=True)
                    entry = {**(rows[0].payload or {}), 'vector': rows[0].vector} if rows else None
                except Exception:
                    entry = None  # Cache outages never turn a valid embedding into an error.
            hit = self.valid(entry, key, dimensions, tenant_key)
            if not hit:
                started = time.perf_counter()
                vector = list(compute())
                entry = {'key': key, 'vector': vector, 'expires': time.time() + TTL,
                         'compute_ms': (time.perf_counter() - started) * 1000, 'tenant': tenant_key}
                if not self.valid(entry, key, dimensions, tenant_key):
                    raise ValueError('Invalid embedding vector')
                if name is not None:
                    try:
                        self.store().upsert(name, points=[models.PointStruct(id=point, vector=vector,
                            payload={k: v for k, v in entry.items() if k != 'vector'})], wait=True)
                        with self.lock:
                            sweep_key = (name, tenant_key)
                            sweep = time.time() - self.swept.get(sweep_key, 0) > 3600
                            if sweep:
                                self.swept[sweep_key] = time.time()
                                self.swept.move_to_end(sweep_key)
                                while len(self.swept) > MAX_ENTRIES:
                                    self.swept.popitem(last=False)
                        if sweep:
                            self.store().delete(name, points_selector=models.FilterSelector(filter=models.Filter(
                                must=[models.FieldCondition(key='tenant', match=models.MatchValue(value=tenant_key)),
                                      models.FieldCondition(key='expires', range=models.Range(lt=time.time()))])), wait=True)
                    except Exception:
                        pass
            with self.lock:
                self.local[key] = entry
                self.local.move_to_end(key)
                while len(self.local) > MAX_ENTRIES:
                    self.local.popitem(last=False)
            merge(dict(attempts=1, hits=int(hit), saved_compute_ms=entry['compute_ms'] if hit else 0.))
            return list(entry['vector'])


def enabled():
    return os.environ.get('ENGINE_C4_ENABLED', '').strip() == '1'


def scoped_embed(encode, text, tenant):
    """Preserve encoder/fake interfaces and propagate tenant into worker threads."""
    if not enabled():
        return encode(text)
    token = _scope.set(str(tenant) if tenant else None)
    try:
        return encode(text)
    finally:
        _scope.reset(token)


def active():
    return enabled() and bool(_scope.get())


def embed(model, text, dimensions, compute):
    global _cache
    if not active():
        return compute()
    with _init_lock:
        if _cache is None:
            _cache = VectorCache()
    return _cache.embed(_scope.get(), model, text, dimensions, compute)
