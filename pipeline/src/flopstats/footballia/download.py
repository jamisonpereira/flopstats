"""Footballia login and full-match download.

The logged-in match page lists every part (half) of the match as base64 URLs in its inline
`var playlist` (and/or a `data-videos` attribute). The parts are plain MP4 files that support
byte ranges, so no browser is needed: log in with a form post, read the URLs from the HTML,
download each part (resumable), and join them with `ffmpeg -c copy`.
Error messages never include credentials.
"""

from __future__ import annotations

import base64
import html as htmllib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://footballia.eu"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
COOKIE_PATH = Path.home() / ".flopstats" / "footballia-cookies.json"
MIN_MINUTES = 85


class LoginFailed(Exception):
    pass


class NotLoggedIn(Exception):
    pass


class IncompleteVideo(Exception):
    pass


def new_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60.0)


def _logged_in(html: str) -> bool:
    return "sign_out" in html


def login(client: httpx.Client, username: str, password: str) -> None:
    """Sign in with the site's own form (the visible one that has the email field)."""
    try:
        page = client.get(f"{BASE_URL}/users/sign_in")
        soup = BeautifulSoup(page.text, "html.parser")
        forms = [f for f in soup.select("form#new_user")
                 if "sign_in" in (f.get("action") or "") and f.select_one('input[name="user[email]"]')]
        if not forms:
            raise LoginFailed("footballia login form not found")
        form = forms[-1]
        data = {i["name"]: i.get("value", "") for i in form.select("input[name]")
                if i.get("type") in ("hidden", "submit") and i["name"] != "user[remember_me]"}
        data.update({"user[email]": username, "user[password]": password, "user[remember_me]": "1"})
        resp = client.post(httpx.URL(BASE_URL).join(form["action"]), data=data)
    except httpx.HTTPError as exc:
        raise LoginFailed(f"footballia login request failed ({type(exc).__name__})") from None
    if not _logged_in(resp.text):
        raise LoginFailed(f"footballia login rejected (HTTP {resp.status_code})")


def session(username: str, password: str, cookie_path: Path = COOKIE_PATH) -> httpx.Client:
    """A logged-in client, reusing saved cookies when they are still valid."""
    client = new_client()
    if cookie_path.exists():
        try:
            for c in json.loads(cookie_path.read_text()):
                client.cookies.set(c["name"], c["value"], domain=c.get("domain") or "", path=c.get("path") or "/")
        except (ValueError, KeyError):
            pass
        if _logged_in(client.get(BASE_URL).text):
            return client
        client.cookies.clear()
    login(client, username, password)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(cookie_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump([{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in client.cookies.jar], fh)
    return client


def video_urls(page_html: str) -> list[str]:
    """The match's part URLs, in order, from a logged-in match page."""
    urls: list[str] = []
    m = re.search(r"var\s+playlist\s*=\s*(\[.*?\]);", page_html, re.S)
    if m:
        for item in json.loads(m.group(1)):
            if item.get("file"):
                urls.append(base64.b64decode(re.sub(r"\s", "", item["file"])).decode())
    if not urls:
        attr = re.search(r'data-videos="([^"]*)"', page_html)
        if attr:
            for item in json.loads(htmllib.unescape(attr.group(1)) or "[]"):
                if item.get("encoded_url"):
                    urls.append(base64.b64decode(re.sub(r"\s", "", item["encoded_url"])).decode())
    if not urls:
        if not _logged_in(page_html):
            raise NotLoggedIn("match page has no video list; the session is not logged in")
        raise RuntimeError("logged in, but the match page lists no videos")
    return urls


def download_file(client: httpx.Client, url: str, dest: Path, chunk: int = 1 << 20) -> Path:
    """Download to dest, resuming a partial file with a Range request."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = dest.stat().st_size if dest.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with client.stream("GET", url, headers=headers) as resp:
        if resp.status_code == 416:  # already complete
            return dest
        resp.raise_for_status()
        mode = "ab" if have and resp.status_code == 206 else "wb"
        expected = None
        if resp.status_code == 206 and "content-range" in resp.headers:
            expected = int(resp.headers["content-range"].rsplit("/", 1)[1])
        elif "content-length" in resp.headers:
            expected = int(resp.headers["content-length"])
        with open(dest, mode) as fh:
            for block in resp.iter_bytes(chunk):
                fh.write(block)
    if expected is not None and dest.stat().st_size != expected:
        raise IOError(f"download of {urlparse(url).path} incomplete: {dest.stat().st_size} of {expected} bytes")
    return dest


def probe_duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


class BadJoin(Exception):
    pass


JOIN_TIMESCALE = 90000
JOIN_TOLERANCE_S = 2.0


def _stream_durations(path: Path) -> list[float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return [float(x) for x in out.stdout.split() if x not in ("", "N/A")]


def _remux(src: Path, dest: Path) -> Path:
    """Same streams, one shared video timescale, so the copy join keeps every timestamp."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c", "copy", "-video_track_timescale", str(JOIN_TIMESCALE),
         str(dest)],
        check=True, capture_output=True,
    )
    return dest


def concat(parts: list[Path], out: Path) -> Path:
    """Join parts without re-encoding. Footballia halves are often encoded differently (timescale,
    frame rate, size); each is remuxed to one timescale first, and the join must last as long as
    its parts together, or it raises BadJoin."""
    expected = sum(max(_stream_durations(p), default=0.0) for p in parts)
    listing = out.with_suffix(".txt")
    remuxed = [out.with_name(f"{out.stem}.join{i}.mp4") for i in range(len(parts))]
    try:
        joined = [_remux(p, r) for p, r in zip(parts, remuxed)]
        listing.write_text("".join(f"file '{p.resolve()}'\n" for p in joined))
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", "-movflags", "+faststart", str(out)],
            check=True, capture_output=True,
        )
    finally:
        listing.unlink(missing_ok=True)
        for r in remuxed:
            r.unlink(missing_ok=True)
    got = _stream_durations(out)
    if not got or any(abs(d - expected) > JOIN_TOLERANCE_S for d in got):
        out.unlink(missing_ok=True)
        raise BadJoin(f"joined streams last {[round(d) for d in got]} s; parts add up to {expected:.0f} s")
    return out


def fetch_match(url: str, dest_dir: Path, *, client: httpx.Client, min_minutes: float = MIN_MINUTES) -> Path:
    """Download every part of a match and join them into dest_dir/<slug>.mp4."""
    dest_dir = Path(dest_dir)
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    parts_dir = dest_dir / f".parts-{slug}"
    page = client.get(url)
    page.raise_for_status()
    parts = [download_file(client, u, parts_dir / f"part{i}.mp4") for i, u in enumerate(video_urls(page.text), 1)]
    out = dest_dir / f"{slug}.mp4"
    tmp = dest_dir / f"{slug}.tmp.mp4"
    try:
        concat(parts, tmp)
        minutes = probe_duration_s(tmp) / 60.0
        if minutes < min_minutes:
            raise IncompleteVideo(f"{slug}: {minutes:.1f} min is under {min_minutes} min")
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
        shutil.rmtree(parts_dir, ignore_errors=True)
    return out
