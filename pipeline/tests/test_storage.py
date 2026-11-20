import json

import httpx
import pytest
import respx

from flopstats.config import Settings
from flopstats.storage import (
    LocalStorage, SupabaseStorage, clip_path, get_storage, image_path, segment_path,
)

URL = "https://example.supabase.co"
KEY = "svc-secret-456"


@pytest.fixture
def clip(tmp_path):
    f = tmp_path / "in.mp4"
    f.write_bytes(b"fake-mp4-bytes")
    return f


def test_path_conventions():
    assert clip_path(12, 345) == "clips/12/345.mp4"
    assert segment_path(12, 6) == "segments/12/6.mp4"
    assert image_path("players", 276, "png") == "images/players/276.png"


def test_local_put_then_url_then_delete(tmp_path, clip):
    store = LocalStorage(tmp_path / "store")
    store.put("clips/1/2.mp4", clip, "video/mp4")
    target = tmp_path / "store" / "clips" / "1" / "2.mp4"
    assert target.read_bytes() == b"fake-mp4-bytes"
    assert store.public_url("clips/1/2.mp4") == target.as_uri()
    assert store.signed_url("clips/1/2.mp4", 60) == target.as_uri()
    store.delete("clips/1/2.mp4")
    assert not target.exists()
    store.delete("clips/1/2.mp4")  # deleting a missing object is not an error


@pytest.mark.parametrize("bad", ["../x.mp4", "/abs/x.mp4", "clips/../../x", ""])
def test_paths_cannot_escape(tmp_path, clip, bad):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).put(bad, clip, "video/mp4")
    with pytest.raises(ValueError):
        SupabaseStorage(URL, KEY).public_url(bad)


@respx.mock
def test_supabase_put_uses_upsert_and_content_type(clip):
    route = respx.post(f"{URL}/storage/v1/object/media/clips/1/2.mp4").respond(200, json={"Key": "media/clips/1/2.mp4"})
    SupabaseStorage(URL, KEY).put("clips/1/2.mp4", clip, "video/mp4")
    req = route.calls[0].request
    assert req.headers["x-upsert"] == "true"
    assert req.headers["content-type"] == "video/mp4"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert req.content == b"fake-mp4-bytes"


@respx.mock
def test_supabase_put_error_raises_without_key(clip):
    respx.post(f"{URL}/storage/v1/object/media/clips/1/2.mp4").respond(400, json={"error": "Bucket not found"})
    with pytest.raises(RuntimeError) as exc:
        SupabaseStorage(URL, KEY).put("clips/1/2.mp4", clip, "video/mp4")
    assert "400" in str(exc.value) and KEY not in str(exc.value)


@respx.mock
def test_supabase_signed_url_and_delete():
    sign = respx.post(f"{URL}/storage/v1/object/sign/media/clips/1/2.mp4").respond(
        200, json={"signedURL": "/object/sign/media/clips/1/2.mp4?token=abc"}
    )
    delete = respx.delete(f"{URL}/storage/v1/object/media").respond(200, json=[])
    store = SupabaseStorage(URL, KEY)
    assert store.signed_url("clips/1/2.mp4", 600) == f"{URL}/storage/v1/object/sign/media/clips/1/2.mp4?token=abc"
    assert json.loads(sign.calls[0].request.content) == {"expiresIn": 600}
    store.delete("clips/1/2.mp4")
    assert json.loads(delete.calls[0].request.content) == {"prefixes": ["clips/1/2.mp4"]}
    assert store.public_url("clips/1/2.mp4") == f"{URL}/storage/v1/object/public/media/clips/1/2.mp4"


@respx.mock
def test_supabase_ensure_bucket_creates_private_and_tolerates_existing():
    route = respx.post(f"{URL}/storage/v1/bucket").mock(
        side_effect=[httpx.Response(200, json={"name": "media"}),
                     httpx.Response(400, json={"statusCode": "409", "error": "Duplicate", "message": "The resource already exists"})]
    )
    store = SupabaseStorage(URL, KEY)
    store.ensure_bucket()
    assert json.loads(route.calls[0].request.content) == {"id": "media", "name": "media", "public": False}
    store.ensure_bucket()


def test_get_storage_selects_backend(fake_env, monkeypatch, tmp_path):
    s = Settings(_env_file=None)
    assert s.storage_backend == "supabase"
    store = get_storage(s)
    assert isinstance(store, SupabaseStorage) and store.bucket == "media"
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    local = get_storage(Settings(_env_file=None))
    assert isinstance(local, LocalStorage) and local.root == tmp_path
