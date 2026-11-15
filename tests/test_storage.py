"""Unit tests for the object-store backends.

MemoryStore is exercised by the dataset API tests; here we also verify the
MinioStore SDK wiring against a fake MinIO client (no server needed).
"""

from __future__ import annotations

import pytest

from zest_data_api.storage import MemoryStore, MinioStore


def test_memory_store_roundtrip():
    s = MemoryStore()
    s.ensure_bucket()
    r = s.put("ds_1/a.txt", b"hello", "text/plain")
    assert r.size == 5 and r.etag
    assert s.get("ds_1/a.txt") == b"hello"
    s.put("ds_1/b.txt", b"x", "text/plain")
    s.delete_prefix("ds_1/")
    with pytest.raises(FileNotFoundError):
        s.get("ds_1/a.txt")


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass


class _FakeObj:
    def __init__(self, name: str):
        self.object_name = name


class _FakeWriteResult:
    etag = '"fake-etag"'


class FakeMinio:
    """Minimal stand-in for minio.Minio that records state in a dict."""

    def __init__(self, *args, **kwargs):
        self.store: dict[str, tuple[bytes, str]] = {}
        self.buckets: set[str] = set()

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)

    def put_object(self, bucket, key, data, length, content_type):
        self.store[key] = (data.read(), content_type)
        return _FakeWriteResult()

    def get_object(self, bucket, key):
        return _FakeResp(self.store[key][0])

    def list_objects(self, bucket, prefix="", recursive=True):
        return [_FakeObj(k) for k in self.store if k.startswith(prefix)]

    def remove_objects(self, bucket, delete_objects):
        for d in delete_objects:
            self.store.pop(d.name, None)
        return []  # errors iterator (empty)


def test_minio_store_wiring(monkeypatch):
    monkeypatch.setattr("minio.Minio", FakeMinio)
    s = MinioStore("minio:9000", "zest", "zest-minio-dev", "datasets", secure=False)

    s.ensure_bucket()  # bucket created on first use
    assert s.ensure_bucket() is None  # idempotent

    r = s.put("ds_1/a.txt", b"hello", "text/plain")
    assert r.size == 5
    assert r.etag == "fake-etag"  # quotes stripped
    assert s.get("ds_1/a.txt") == b"hello"

    s.put("ds_1/b.txt", b"world", "text/plain")
    s.delete_prefix("ds_1/")
    # both objects under the prefix removed
    assert s._client.store == {}  # type: ignore[attr-defined]
