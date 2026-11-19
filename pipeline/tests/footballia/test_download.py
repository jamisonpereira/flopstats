import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
import respx

from flopstats.footballia import download
from flopstats.footballia.download import IncompleteVideo, LoginFailed, NotLoggedIn, fetch_match, login, video_urls

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "footballia"
MATCH = "https://footballia.eu/matches/brentford-fc-nottingham-forest-premier-league"
PART1 = "https://videos.footballia.net/uploads/video/source_file/71033/2024BreNfo_1st.mp4"
PART2 = "https://videos.footballia.net/uploads/video/source_file/71034/2024BreNfo_2nd.mp4"
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_video_urls_from_logged_in_page():
    assert video_urls((FIX / "match_logged_in.html").read_text()) == [PART1, PART2]


def test_video_urls_logged_out_raises():
    with pytest.raises(NotLoggedIn):
        video_urls((FIX / "match_logged_out.html").read_text())


@respx.mock
def test_login_posts_visible_sign_in_form():
    respx.get("https://footballia.eu/users/sign_in").respond(200, text=(FIX / "sign_in.html").read_text())
    post = respx.post("https://footballia.eu/users/sign_in", params={"locale": "en"}).respond(
        200, text='<a href="/users/sign_out">Sign out</a>')
    login(httpx.Client(), "user@example.com", "pw-secret")
    form = dict(httpx.QueryParams(post.calls[0].request.content.decode()))
    assert form["authenticity_token"] == "csrf-abc"
    assert form["user[email]"] == "user@example.com" and form["user[password]"] == "pw-secret"
    assert form["user[remember_me]"] == "1"


@respx.mock
def test_login_failure_raises_without_credentials():
    respx.get("https://footballia.eu/users/sign_in").respond(200, text=(FIX / "sign_in.html").read_text())
    respx.post("https://footballia.eu/users/sign_in", params={"locale": "en"}).respond(200, text="Invalid Email or password.")
    with pytest.raises(LoginFailed) as exc:
        login(httpx.Client(), "user@example.com", "pw-secret")
    assert "user@example.com" not in str(exc.value) and "pw-secret" not in str(exc.value)


def _tiny_mp4(path: Path, seconds: int) -> bytes:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=64x36:rate=5:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=duration={seconds}", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)],
        check=True,
    )
    return path.read_bytes()


def _mock_match(mock, tmp_path):
    mock.get(MATCH).respond(200, text=(FIX / "match_logged_in.html").read_text())
    b1, b2 = _tiny_mp4(tmp_path / "p1.mp4", 2), _tiny_mp4(tmp_path / "p2.mp4", 3)
    mock.get(PART1).respond(200, content=b1, headers={"content-length": str(len(b1))})
    mock.get(PART2).respond(200, content=b2, headers={"content-length": str(len(b2))})


@needs_ffmpeg
@respx.mock
def test_fetch_match_downloads_parts_and_concatenates(tmp_path):
    _mock_match(respx, tmp_path)
    out = fetch_match(MATCH, tmp_path / "videos", client=httpx.Client(), min_minutes=0)
    assert out.name == "brentford-fc-nottingham-forest-premier-league.mp4"
    assert 4.5 <= download.probe_duration_s(out) <= 5.5
    assert sorted(p.name for p in (tmp_path / "videos").iterdir()) == [out.name]  # parts removed


@needs_ffmpeg
@respx.mock
def test_incomplete_video_raises(tmp_path, monkeypatch):
    _mock_match(respx, tmp_path)
    monkeypatch.setattr(download, "probe_duration_s", lambda path: 40 * 60.0)  # fake ffprobe: 40 min
    with pytest.raises(IncompleteVideo):
        fetch_match(MATCH, tmp_path / "videos", client=httpx.Client())
    assert not list((tmp_path / "videos").glob("*.mp4"))  # nothing half-done is left as a "match"


@respx.mock
def test_download_part_resumes_from_partial_file(tmp_path):
    dest = tmp_path / "part.mp4"
    dest.write_bytes(b"0123")
    route = respx.get(PART1).respond(206, content=b"456789", headers={"content-range": "bytes 4-9/10"})
    download.download_file(httpx.Client(), PART1, dest)
    assert route.calls[0].request.headers["range"] == "bytes=4-"
    assert dest.read_bytes() == b"0123456789"
