"""Object storage abstraction.

A thin interface over an S3-compatible store (MinIO) plus an in-memory fallback.
When ``settings.storage_endpoint`` is empty the in-memory store is used, so the
test suite and a bare ``uvicorn`` run need no MinIO.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Protocol

from .config import get_settings


@dataclass(frozen=True)
class StoredObject:
    """Result of a successful put."""

    etag: str
    size: int


class ObjectStore(Protocol):
    def ensure_bucket(self) -> None: ...
    def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...


class MemoryStore:
    """Dict-backed store for tests / MinIO-less local runs."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def ensure_bucket(self) -> None:  # noqa: D102 - no-op
        pass

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self._objects[key] = (data, content_type)
        return StoredObject(etag=hashlib.md5(data).hexdigest(), size=len(data))  # noqa: S324

    def get(self, key: str) -> bytes:
        try:
            return self._objects[key][0]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._objects if k.startswith(prefix)]:
            del self._objects[key]


class MinioStore:
    """S3-compatible store backed by the MinIO SDK."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool):
        from minio import Minio

        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        result = self._client.put_object(
            self._bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )
        return StoredObject(etag=(result.etag or "").strip('"'), size=len(data))

    def get(self, key: str) -> bytes:
        from minio.error import S3Error

        response = None
        try:
            response = self._client.get_object(self._bucket, key)
            return response.read()
        except S3Error as exc:
            if exc.code in ("NoSuchKey", "NoSuchBucket"):
                raise FileNotFoundError(key) from exc
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def delete(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)

    def delete_prefix(self, prefix: str) -> None:
        from minio.deleteobjects import DeleteObject

        objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        to_delete = [DeleteObject(obj.object_name) for obj in objects]
        if to_delete:
            # remove_objects returns a lazy iterator of errors; consume it to execute.
            for _ in self._client.remove_objects(self._bucket, to_delete):
                pass


_store: ObjectStore | None = None


def get_store() -> ObjectStore:
    """Return the process-wide object store (MinIO when configured, else in-memory)."""
    global _store
    if _store is None:
        s = get_settings()
        if s.storage_endpoint:
            _store = MinioStore(
                endpoint=s.storage_endpoint,
                access_key=s.storage_access_key,
                secret_key=s.storage_secret_key,
                bucket=s.storage_bucket,
                secure=s.storage_secure,
            )
        else:
            _store = MemoryStore()
    return _store


def reset_store() -> None:
    """Drop the cached store (used by tests)."""
    global _store
    _store = None
