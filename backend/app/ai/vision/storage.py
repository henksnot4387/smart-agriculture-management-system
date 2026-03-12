from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import REPO_ROOT, Settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    public_url: str
    size_bytes: int
    content_type: str


class StorageService(Protocol):
    backend_name: str

    def save_bytes(self, key: str, content: bytes, content_type: str) -> StoredObject: ...

    def read_bytes(self, key: str) -> bytes: ...


class LocalStorageService:
    backend_name = "local"

    def __init__(self, root: Path):
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root_path(self) -> Path:
        return self._root

    def save_bytes(self, key: str, content: bytes, content_type: str) -> StoredObject:
        object_path = self._resolve_path(key)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(content)
        return StoredObject(
            key=key,
            public_url=f"/files/{key}",
            size_bytes=len(content),
            content_type=content_type,
        )

    def read_bytes(self, key: str) -> bytes:
        return self._resolve_path(key).read_bytes()

    def _resolve_path(self, key: str) -> Path:
        sanitized_key = key.lstrip("/").replace("\\", "/")
        target = (self._root / sanitized_key).resolve()
        if self._root.resolve() not in target.parents and target != self._root.resolve():
            raise ValueError("Invalid storage key path.")
        return target


class S3StorageService:
    backend_name = "object"

    def __init__(self, settings: Settings):
        self._bucket = settings.object_storage_bucket.strip()
        self._prefix = settings.object_storage_prefix.strip().strip("/")
        endpoint = settings.object_storage_endpoint.strip()
        region = settings.object_storage_region.strip() or None
        access_key = settings.object_storage_access_key_id.strip()
        secret_key = settings.object_storage_secret_access_key.strip()
        public_base_url = settings.object_storage_public_base_url.strip().rstrip("/")
        force_path_style = settings.object_storage_force_path_style

        if not endpoint:
            raise RuntimeError("OBJECT_STORAGE_ENDPOINT is required when FILE_STORAGE_BACKEND=object.")
        if not self._bucket:
            raise RuntimeError("OBJECT_STORAGE_BUCKET is required when FILE_STORAGE_BACKEND=object.")
        if not access_key or not secret_key:
            raise RuntimeError(
                "OBJECT_STORAGE_ACCESS_KEY_ID and OBJECT_STORAGE_SECRET_ACCESS_KEY are required when FILE_STORAGE_BACKEND=object."
            )

        if "://" not in endpoint:
            endpoint = f"https://{endpoint}"
        self._endpoint = endpoint.rstrip("/")
        self._public_base_url = public_base_url

        try:
            import boto3
            from botocore.config import Config
        except Exception as exc:  # pragma: no cover - import failure is environment-dependent.
            raise RuntimeError("boto3 is required for object storage mode.") from exc

        client_config = Config(s3={"addressing_style": "path" if force_path_style else "virtual"})
        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=client_config,
        )

    def save_bytes(self, key: str, content: bytes, content_type: str) -> StoredObject:
        object_key = self._apply_prefix(key)
        self._client.put_object(
            Bucket=self._bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(
            key=object_key,
            public_url=self._build_public_url(object_key),
            size_bytes=len(content),
            content_type=content_type,
        )

    def read_bytes(self, key: str) -> bytes:
        object_key = self._apply_prefix(key)
        response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        body = response["Body"].read()
        return body

    def _apply_prefix(self, key: str) -> str:
        normalized = key.lstrip("/").replace("\\", "/")
        if self._prefix:
            prefix = f"{self._prefix}/"
            if normalized.startswith(prefix):
                return normalized
            return f"{prefix}{normalized}"
        return normalized

    def _build_public_url(self, key: str) -> str:
        if self._public_base_url:
            return f"{self._public_base_url}/{key}"
        return f"{self._endpoint}/{self._bucket}/{key}"


def resolve_storage_backend(settings: Settings) -> str:
    explicit = settings.file_storage_backend.strip().lower()
    if explicit in {"local", "object"}:
        backend = explicit
    elif explicit:
        raise RuntimeError("FILE_STORAGE_BACKEND must be one of: local, object.")
    else:
        backend = "object" if settings.app_env.lower() in {"production", "prod"} else "local"

    if settings.app_env.lower() in {"production", "prod"} and backend != "object":
        raise RuntimeError("Production environment requires object storage backend.")
    return backend


def build_storage_service(settings: Settings) -> StorageService:
    backend = resolve_storage_backend(settings)
    if backend == "object":
        return S3StorageService(settings)

    root = Path(settings.local_storage_root)
    if not root.is_absolute():
        root = (REPO_ROOT / root).resolve()
    return LocalStorageService(root=root)
