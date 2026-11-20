import json
import subprocess
from pathlib import Path

import pytest

from flopstats.video import ffmpeg

TINY = Path(__file__).resolve().parents[1] / "fixtures" / "video" / "tiny.mp4"


def _streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return {s["codec_type"]: s for s in json.loads(out)["streams"]}


def test_probe_duration():
    assert ffmpeg.probe_duration(TINY) == pytest.approx(60, abs=0.2)


def test_cut_produces_expected_duration(tmp_path):
    out = ffmpeg.cut(TINY, 12.3, 30.0, tmp_path / "seg.mp4", reencode=True)
    assert ffmpeg.probe_duration(out) == pytest.approx(17.7, abs=0.5)
    streams = _streams(out)
    assert set(streams) == {"video"}  # model segments drop audio
    assert streams["video"]["codec_name"] == "h264" and streams["video"]["height"] == 720


def test_cut_clip_keeps_audio(tmp_path):
    out = ffmpeg.cut(TINY, 5, 15, tmp_path / "clip.mp4", reencode=True, audio=True)
    streams = _streams(out)
    assert streams["audio"]["codec_name"] == "aac"
    assert ffmpeg.probe_duration(out) == pytest.approx(10, abs=0.5)


def test_cut_stream_copy(tmp_path):
    out = ffmpeg.cut(TINY, 10, 20, tmp_path / "copy.mp4", reencode=False)
    assert ffmpeg.probe_duration(out) == pytest.approx(10, abs=0.5)
    assert _streams(out)["video"]["height"] == 90  # untouched


def test_cut_rejects_bad_range(tmp_path):
    with pytest.raises(ValueError):
        ffmpeg.cut(TINY, 20, 10, tmp_path / "x.mp4", reencode=True)


def test_frame_at_writes_png(tmp_path):
    out = ffmpeg.frame_at(TINY, 30.5, tmp_path / "f.png")
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_ffmpeg_error_is_raised(tmp_path):
    with pytest.raises(ffmpeg.FFmpegError):
        ffmpeg.frame_at(tmp_path / "missing.mp4", 1, tmp_path / "f.png")


def _keyframes(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-skip_frame", "nokey",
                          "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return [float(x.strip(",")) for x in out.split()]


@pytest.mark.parametrize("hw", [True, False])
def test_working_copy_has_keyframes_on_every_window_start(tmp_path, hw):
    if hw and not ffmpeg.has_videotoolbox():
        pytest.skip("no VideoToolbox on this machine")
    out = ffmpeg.working_copy(TINY, tmp_path / "work.mp4", keyframe_s=10, fps=5, height=72, hw=hw)
    s = _streams(out)
    assert set(s) == {"video"} and s["video"]["height"] == 72 and s["video"]["r_frame_rate"] == "5/1"
    assert ffmpeg.probe_duration(out) == pytest.approx(60, abs=0.5)
    keys = _keyframes(out)
    for start in range(0, 60, 10):
        assert any(start <= k < start + ffmpeg.KEY_NUDGE_S for k in keys), (start, keys)


def test_window_from_working_copy_is_an_exact_copy(tmp_path):
    work = ffmpeg.working_copy(TINY, tmp_path / "work.mp4", keyframe_s=10, fps=25, height=72, hw=False)
    seg = ffmpeg.window(work, 20, 40, tmp_path / "w.mp4")
    assert ffmpeg.probe_duration(seg) == pytest.approx(20, abs=0.3)
