"""Private S3-compatible object storage support for user-uploaded files."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Dict, Iterator, Optional


TRUE_VALUES = {"1", "true", "yes", "on"}
VALID_MODES = {"volume", "mirror", "bucket"}


class StorageConfigurationError(RuntimeError):
    """Raised when bucket mode is enabled without complete credentials."""


class StorageObjectNotFound(FileNotFoundError):
    """Raised when an object does not exist in the configured bucket."""


class StorageObjectConflict(RuntimeError):
    """Raised when a migration would overwrite different bucket content."""


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _safe_metadata_value(value: object, limit: int = 900) -> str:
    text = str(value or "").strip()
    return text.encode("ascii", "replace").decode("ascii")[:limit]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file_obj:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class StorageObjectInfo:
    key: str
    size: int
    checksum: str = ""
    content_type: str = ""
    original_filename: str = ""
    last_modified: object = None


class FileStorageBackend:
    """Storage adapter supporting volume, mirror, and private bucket modes."""

    def __init__(self) -> None:
        requested_mode = _first_env("FILE_STORAGE_MODE", default="volume").lower()
        self.mode = requested_mode if requested_mode in VALID_MODES else "volume"
        self.bucket_name = _first_env(
            "STORAGE_BUCKET_NAME", "AWS_S3_BUCKET_NAME", "BUCKET_NAME", "BUCKET"
        )
        self.endpoint_url = _first_env(
            "STORAGE_BUCKET_ENDPOINT", "AWS_ENDPOINT_URL", "ENDPOINT"
        ).rstrip("/")
        self.access_key = _first_env(
            "STORAGE_BUCKET_ACCESS_KEY", "AWS_ACCESS_KEY_ID", "ACCESS_KEY_ID"
        )
        self.secret_key = _first_env(
            "STORAGE_BUCKET_SECRET_KEY", "AWS_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY"
        )
        self.region = _first_env(
            "STORAGE_BUCKET_REGION", "AWS_DEFAULT_REGION", "AWS_REGION", "REGION",
            default="auto",
        )
        self.url_style = _first_env(
            "STORAGE_BUCKET_URL_STYLE", "AWS_S3_URL_STYLE", default="virtual"
        ).lower()
        if self.url_style not in {"path", "virtual", "auto"}:
            self.url_style = "path"
        fallback_default = "true" if self.mode in {"mirror", "bucket"} else "false"
        self.volume_fallback = _first_env(
            "STORAGE_VOLUME_FALLBACK", default=fallback_default
        ).lower() in TRUE_VALUES
        self._client = None

    @property
    def bucket_enabled(self) -> bool:
        return self.mode in {"mirror", "bucket"}

    @property
    def bucket_configured(self) -> bool:
        return bool(
            self.bucket_name
            and self.endpoint_url
            and self.access_key
            and self.secret_key
        )

    @property
    def writes_volume(self) -> bool:
        return self.mode in {"volume", "mirror"}

    @property
    def writes_bucket(self) -> bool:
        return self.mode in {"mirror", "bucket"}

    def public_config(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "bucket_enabled": self.bucket_enabled,
            "bucket_configured": self.bucket_configured,
            "bucket_name": self.bucket_name,
            "endpoint_configured": bool(self.endpoint_url),
            "region": self.region,
            "url_style": self.url_style,
            "volume_fallback": self.volume_fallback,
        }

    def _require_bucket(self) -> None:
        if not self.bucket_configured:
            raise StorageConfigurationError(
                "Bucket storage is enabled but the Railway bucket credentials are incomplete."
            )

    def client(self):
        self._require_bucket()
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise StorageConfigurationError(
                "boto3 is required when bucket storage is enabled."
            ) from exc

        addressing_style = self.url_style
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing_style},
                retries={"max_attempts": 4, "mode": "standard"},
                connect_timeout=8,
                read_timeout=60,
            ),
        )
        return self._client

    @staticmethod
    def normalize_key(key: str) -> str:
        normalized = str(key or "").replace("\\", "/").lstrip("/")
        parts = [part for part in normalized.split("/") if part not in {"", ".", ".."}]
        if not parts:
            raise ValueError("Storage object key is empty.")
        return "/".join(parts)

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        original_filename: str = "",
        extra_metadata: Optional[Dict[str, object]] = None,
    ) -> StorageObjectInfo:
        key = self.normalize_key(key)
        checksum = sha256_bytes(data)
        metadata = {
            "sha256": checksum,
            "size": str(len(data)),
            "original-filename": _safe_metadata_value(original_filename),
        }
        for name, value in (extra_metadata or {}).items():
            clean_name = str(name or "").strip().lower().replace("_", "-")
            if clean_name:
                metadata[clean_name] = _safe_metadata_value(value)
        self.client().put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
            Metadata=metadata,
        )
        return StorageObjectInfo(
            key=key,
            size=len(data),
            checksum=checksum,
            content_type=content_type or "application/octet-stream",
            original_filename=original_filename or "",
        )

    def upload_file(
        self,
        key: str,
        path: str,
        *,
        content_type: str = "application/octet-stream",
        original_filename: str = "",
        overwrite: bool = True,
    ) -> StorageObjectInfo:
        key = self.normalize_key(key)
        local_size = os.path.getsize(path)
        local_checksum = sha256_file(path)
        existing = self.head(key)
        if existing:
            exact_match = existing.size == local_size and existing.checksum == local_checksum
            if exact_match:
                return existing
            if not overwrite:
                raise StorageObjectConflict(
                    f"Bucket object {key} already exists with different content."
                )
        with open(path, "rb") as file_obj:
            data = file_obj.read()
        return self.upload_bytes(
            key,
            data,
            content_type=content_type,
            original_filename=original_filename,
        )

    def head(self, key: str) -> Optional[StorageObjectInfo]:
        key = self.normalize_key(key)
        try:
            response = self.client().head_object(Bucket=self.bucket_name, Key=key)
        except Exception as exc:
            response_meta = getattr(exc, "response", {}) or {}
            error = response_meta.get("Error", {}) if isinstance(response_meta, dict) else {}
            if str(error.get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        metadata = response.get("Metadata") or {}
        return StorageObjectInfo(
            key=key,
            size=int(response.get("ContentLength") or 0),
            checksum=str(metadata.get("sha256") or ""),
            content_type=str(response.get("ContentType") or ""),
            original_filename=str(metadata.get("original-filename") or ""),
            last_modified=response.get("LastModified"),
        )

    def download_bytes(self, key: str) -> bytes:
        key = self.normalize_key(key)
        try:
            response = self.client().get_object(Bucket=self.bucket_name, Key=key)
        except Exception as exc:
            response_meta = getattr(exc, "response", {}) or {}
            error = response_meta.get("Error", {}) if isinstance(response_meta, dict) else {}
            if str(error.get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
                raise StorageObjectNotFound(key) from exc
            raise
        body = response.get("Body")
        return body.read() if body is not None else b""

    def delete(self, key: str) -> None:
        self.client().delete_object(Bucket=self.bucket_name, Key=self.normalize_key(key))

    def iter_objects(self, prefix: str = "") -> Iterator[StorageObjectInfo]:
        normalized_prefix = str(prefix or "").replace("\\", "/").lstrip("/")
        paginator = self.client().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=normalized_prefix):
            for item in page.get("Contents") or []:
                key = str(item.get("Key") or "")
                if key:
                    yield StorageObjectInfo(
                        key=key,
                        size=int(item.get("Size") or 0),
                        last_modified=item.get("LastModified"),
                    )

    def test_connection(self) -> Dict[str, object]:
        if not self.bucket_configured:
            return {"ok": False, "message": "Bucket credentials are not configured."}
        try:
            self.client().head_bucket(Bucket=self.bucket_name)
            return {"ok": True, "message": "Bucket connection is healthy."}
        except Exception as exc:
            return {"ok": False, "message": str(exc)[:300]}
