"""File storage behind one small protocol, so Supabase Storage can become R2 by config.

Path conventions: clips/<match_id>/<incident_id>.mp4, segments/<match_id>/<candidate_id>.mp4,
images/<kind>/<id>.<ext>. The Supabase `media` bucket is private; the review screen uses
signed URLs.
"""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import quote

import httpx

from flopstats.config import Settings


def clip_path(match_id: int, incident_id: int) -> str:
    return f"clips/{match_id}/{incident_id}.mp4"


def segment_path(match_id: int, candidate_id: int) -> str:
    return f"segments/{match_id}/{candidate_id}.mp4"


def image_path(kind: str, entity_id: int, ext: str) -> str:
    return f"images/{kind}/{entity_id}.{ext.lstrip('.')}"


def _check_path(path: str) -> str:
    p = PurePosixPath(path)
    if not path or p.is_absolute() or ".." in p.parts or "\\" in path:
        raise ValueError(f"invalid storage path {path!r}")
    return str(p)


class StorageAdapter(Protocol):
    def put(self, path: str, local_file: Path, content_type: str) -> None: ...
    def delete(self, path: str) -> None: ...
    def public_url(self, path: str) -> str: ...
    def signed_url(self, path: str, expires_s: int) -> str: ...


class LocalStorage:
    """Files under a local directory (tests and offline development)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _file(self, path: str) -> Path:
        return self.root / _check_path(path)

    def put(self, path: str, local_file: Path, content_type: str) -> None:
        target = self._file(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_file, target)

    def delete(self, path: str) -> None:
        self._file(path).unlink(missing_ok=True)

    def public_url(self, path: str) -> str:
        return self._file(path).resolve().as_uri()

    def signed_url(self, path: str, expires_s: int) -> str:
        return self.public_url(path)


class SupabaseStorage:
    def __init__(self, url: str, service_key: str, bucket: str = "media", *, http: httpx.Client | None = None):
        self._base = f"{url.rstrip('/')}/storage/v1"
        self._key = service_key
        self.bucket = bucket
        self._http = http or httpx.Client(timeout=120.0)

    def _headers(self, **extra) -> dict[str, str]:
        return {"apikey": self._key, "Authorization": f"Bearer {self._key}", **extra}

    def _object(self, path: str) -> str:
        return quote(_check_path(path))

    @staticmethod
    def _raise(resp: httpx.Response, what: str) -> None:
        if resp.status_code >= 400:
            try:
                message = resp.json().get("message") or resp.json().get("error")
            except ValueError:
                message = None
            raise RuntimeError(f"storage {what} failed: HTTP {resp.status_code}" + (f" ({message})" if message else ""))

    def ensure_bucket(self) -> None:
        """Create the private bucket if it does not exist."""
        resp = self._http.post(
            f"{self._base}/bucket",
            json={"id": self.bucket, "name": self.bucket, "public": False},
            headers=self._headers(),
        )
        if resp.status_code < 400:
            return
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if str(body.get("statusCode")) == "409" or "already exists" in str(body.get("message", "")):
            return
        self._raise(resp, "create bucket")

    def put(self, path: str, local_file: Path, content_type: str) -> None:
        with open(local_file, "rb") as fh:
            resp = self._http.post(
                f"{self._base}/object/{self.bucket}/{self._object(path)}",
                content=fh.read(),
                headers=self._headers(**{"Content-Type": content_type, "x-upsert": "true"}),
            )
        self._raise(resp, f"upload {path}")

    def delete(self, path: str) -> None:
        resp = self._http.request(
            "DELETE",
            f"{self._base}/object/{self.bucket}",
            json={"prefixes": [_check_path(path)]},
            headers=self._headers(),
        )
        self._raise(resp, f"delete {path}")

    def public_url(self, path: str) -> str:
        return f"{self._base}/object/public/{self.bucket}/{self._object(path)}"

    def signed_url(self, path: str, expires_s: int) -> str:
        resp = self._http.post(
            f"{self._base}/object/sign/{self.bucket}/{self._object(path)}",
            json={"expiresIn": expires_s},
            headers=self._headers(),
        )
        self._raise(resp, f"sign {path}")
        return f"{self._base}{resp.json()['signedURL']}"


def get_storage(settings: Settings) -> StorageAdapter:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_root)
    if settings.supabase_url is None or settings.supabase_service_key is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set for Supabase storage")
    return SupabaseStorage(settings.supabase_url, settings.supabase_service_key.get_secret_value())
