import base64
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from flopstats.detect.gemini import DECISIONS_URL, DecisionClockReader, DecisionError, DecisionScorer

KEY = "gem-test-key"


@pytest.fixture
def segment(tmp_path):
    p = tmp_path / "seg.mp4"
    p.write_bytes(b"fake-mp4")
    return p


def _resp(answers, tokens=2000):
    return httpx.Response(200, json={"answers": answers, "usage": {"total_input_tokens": tokens, "total_output_tokens": 0}})


@respx.mock
def test_decision_scorer_maps_probability_and_cost(segment):
    route = respx.post(DECISIONS_URL).mock(return_value=_resp({"flop": {"type": "noul", "noul": 0.83, "confidence": 0.83}}, tokens=2000))
    r = DecisionScorer(KEY).score(segment)
    assert r.p_flop == 0.83
    assert r.usd == Decimal("2000") * Decimal("0.10") / Decimal(1_000_000)
    assert r.raw["usage"]["total_input_tokens"] == 2000
    req = route.calls[0].request
    assert req.headers["x-goog-api-key"] == KEY
    body = json.loads(req.content)
    assert body["model"] == "gemini-decision-1"
    assert body["questions"]["flop"]["type"] == "noul"
    assert "diving" in body["questions"]["flop"]["instructions"]
    video = [b for b in body["input"] if b.get("type") == "video"][0]
    assert video["mime_type"] == "video/mp4" and base64.b64decode(video["data"]) == b"fake-mp4"


@respx.mock
def test_decision_scorer_custom_price(segment):
    respx.post(DECISIONS_URL).mock(return_value=_resp({"flop": {"type": "noul", "noul": 0.2, "confidence": 0.8}}, tokens=1_000_000))
    assert DecisionScorer(KEY, usd_per_m_input=Decimal("0.25")).score(segment).usd == Decimal("0.25")


@respx.mock
def test_decision_error_is_raised_without_key(segment):
    respx.post(DECISIONS_URL).respond(400, json={"error": {"code": "safety", "message": "blocked"}})
    with pytest.raises(DecisionError) as exc:
        DecisionScorer(KEY).score(segment)
    assert "safety" in str(exc.value) and KEY not in str(exc.value)


@respx.mock
def test_decision_retries_429_then_succeeds(segment):
    sleeps = []
    respx.post(DECISIONS_URL).mock(side_effect=[httpx.Response(429), httpx.Response(503),
                                                 _resp({"flop": {"type": "noul", "noul": 0.5, "confidence": 0.5}})])
    assert DecisionScorer(KEY, sleep=sleeps.append).score(segment).p_flop == 0.5
    assert len(sleeps) == 2


@respx.mock
def test_clock_reader_reads_minute_and_second(tmp_path):
    png = tmp_path / "f.png"
    png.write_bytes(b"\x89PNG fake")
    route = respx.post(DECISIONS_URL).mock(return_value=_resp({
        "visible": {"type": "noul", "noul": 0.97, "confidence": 0.97},
        "minute": {"type": "choice", "choice": "m067", "confidence": 0.9, "probabilities": {}},
        "second": {"type": "choice", "choice": "s08", "confidence": 0.8, "probabilities": {}},
    }))
    r = DecisionClockReader(KEY).read(png)
    assert (r.minute, r.second) == (67, 8)
    assert r.confidence == pytest.approx(0.8 * 0.9 * 0.97)
    body = json.loads(route.calls[0].request.content)
    assert len(body["questions"]["minute"]["criteria"]) == 131 and len(body["questions"]["second"]["criteria"]) == 60
    assert [b for b in body["input"] if b.get("type") == "image"][0]["mime_type"] == "image/png"


@respx.mock
def test_clock_reader_no_clock_visible(tmp_path):
    png = tmp_path / "f.png"
    png.write_bytes(b"\x89PNG fake")
    respx.post(DECISIONS_URL).mock(return_value=_resp({
        "visible": {"type": "noul", "noul": 0.1, "confidence": 0.9},
        "minute": {"type": "choice", "choice": "m010", "confidence": 0.3, "probabilities": {}},
        "second": {"type": "choice", "choice": "s10", "confidence": 0.3, "probabilities": {}},
    }))
    assert DecisionClockReader(KEY).read(png) is None


@respx.mock
def test_rate_limit_waits_as_long_as_the_api_asks(segment):
    sleeps = []
    limited = httpx.Response(429, json={"error": {"code": "too_many_requests",
                                                  "message": "Rate limit exceeded ... Please retry in 37s or upgrade your tier"}})
    respx.post(DECISIONS_URL).mock(side_effect=[limited, httpx.Response(429, headers={"Retry-After": "12"}),
                                                 _resp({"flop": {"type": "noul", "noul": 0.5, "confidence": 0.5}})])
    DecisionScorer(KEY, sleep=sleeps.append).score(segment)
    assert sleeps == [38.0, 13.0]  # the asked-for wait plus 1 s of slack


@respx.mock
def test_rate_limit_retries_more_than_server_errors(segment):
    sleeps = []
    limited = httpx.Response(429, json={"error": {"code": "too_many_requests", "message": "retry in 1s"}})
    respx.post(DECISIONS_URL).mock(side_effect=[limited] * 8 + [_resp({"flop": {"type": "noul", "noul": 0.5, "confidence": 0.5}})])
    assert DecisionScorer(KEY, sleep=sleeps.append).score(segment).p_flop == 0.5
    assert len(sleeps) == 8
