"""Gemini adapters. The only module that talks to Google's models.

Decisions API (gemini-decision-1): docs https://aistudio.google.com/docs/decisions-api and
https://aistudio.google.com/docs/models/gemini-decision-1 (read 2026-11-19).
REST: POST https://generativelanguage.googleapis.com/v1beta/decisions with header
x-goog-api-key and body {"model", "input": [content blocks], "questions": {key: question}}.
A yes/no question is {"type": "noul", "instructions", "criteria": {"true_description",
"false_description"}}; the answer is answers[key].noul = P(yes) in [0.01, 0.99]. A choice
question returns answers[key].choice and .confidence. Usage: usage.total_input_tokens.
Price: $0.10 per 1M input tokens, output not billed. Video goes inline as base64
(<= 100 MB per request), which our short segments always are.
We call REST with httpx (documented JSON) rather than the SDK's `client.decisions`.
"""

from __future__ import annotations

import base64
import re
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import httpx

from flopstats.detect.models import ScoreResult
from flopstats.video.timesync import ClockReading

DECISIONS_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
DECISION_MODEL = "gemini-decision-1"
DEFAULT_USD_PER_M_INPUT = Decimal("0.10")
RETRIES = 3

FLOP_QUESTION = {
    "type": "noul",
    "instructions": (
        "Does this clip show a player diving, exaggerating contact, feigning injury or "
        "time-wasting by staying down?"
    ),
    "criteria": {
        "true_description": "A player clearly goes down or stays down more than the contact (if any) justifies: "
        "a dive, an exaggerated reaction, a faked injury, or staying down to waste time.",
        "false_description": "No player does any of that: normal play, genuine fouls with proportionate reactions, "
        "genuine injuries, or no player on the ground.",
    },
}


class DecisionError(RuntimeError):
    pass


RATE_LIMIT_RETRIES = 10


def _error_detail(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        return f"{err.get('code')}: {err.get('message')}"
    except ValueError:
        return "no JSON body"


def _retry_after_s(resp: httpx.Response, default: float) -> float:
    """Seconds the API asks us to wait: Retry-After header, or "retry in 37s" in the message."""
    header = resp.headers.get("retry-after")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    m = re.search(r"retry in (\d+(?:\.\d+)?)\s*s", _error_detail(resp), re.I)
    return float(m.group(1)) if m else default


def _video_block(path: Path, resolution: str) -> dict:
    return {"type": "video", "data": base64.b64encode(Path(path).read_bytes()).decode(),
            "mime_type": "video/mp4", "resolution": resolution}


def _image_block(path: Path, resolution: str) -> dict:
    return {"type": "image", "data": base64.b64encode(Path(path).read_bytes()).decode(),
            "mime_type": "image/png", "resolution": resolution}


class _DecisionsClient:
    def __init__(self, api_key: str, model: str, usd_per_m_input: Decimal, http: httpx.Client | None,
                 sleep: Callable[[float], None]):
        self._key = api_key
        self.model = model
        self.usd_per_m_input = Decimal(usd_per_m_input)
        self._http = http or httpx.Client(timeout=120.0)
        self._sleep = sleep

    def decide(self, blocks: list[dict], questions: dict) -> dict:
        body = {"model": self.model, "input": blocks, "questions": questions}
        server_errors = rate_limits = 0
        while True:
            try:
                resp = self._http.post(DECISIONS_URL, json=body, headers={"x-goog-api-key": self._key})
            except httpx.TransportError as exc:
                server_errors += 1
                if server_errors > RETRIES:
                    raise DecisionError(f"decisions request failed ({type(exc).__name__})") from None
                self._sleep(2.0 ** (server_errors - 1))
                continue
            if resp.status_code == 429 and rate_limits < RATE_LIMIT_RETRIES:
                rate_limits += 1
                self._sleep(_retry_after_s(resp, default=2.0 ** min(rate_limits, 6)) + 1.0)
                continue
            if resp.status_code in (500, 502, 503, 504) and server_errors < RETRIES:
                server_errors += 1
                self._sleep(2.0 ** (server_errors - 1))
                continue
            if resp.status_code != 200:
                raise DecisionError(f"decisions HTTP {resp.status_code} ({_error_detail(resp)})")
            return resp.json()

    def usd(self, data: dict) -> Decimal:
        tokens = Decimal((data.get("usage") or {}).get("total_input_tokens") or 0)
        return tokens * self.usd_per_m_input / Decimal(1_000_000)


class DecisionScorer:
    """Wide-net window scorer: one yes/no question per window, P(yes) = p_flop."""

    def __init__(self, api_key: str, model: str = DECISION_MODEL, *, usd_per_m_input: Decimal = DEFAULT_USD_PER_M_INPUT,
                 resolution: str = "low", http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep):
        self._client = _DecisionsClient(api_key, model, usd_per_m_input, http, sleep)
        self.name = model
        self.resolution = resolution

    def score(self, segment: Path) -> ScoreResult:
        data = self._client.decide([_video_block(segment, self.resolution)], {"flop": FLOP_QUESTION})
        p = float(data["answers"]["flop"]["noul"])
        return ScoreResult(p_flop=p, usd=self._client.usd(data), raw=data)


class DecisionClockReader:
    """Reads the broadcast clock from a frame with three questions (visible? minute? second?)."""

    MIN_VISIBLE = 0.5

    def __init__(self, api_key: str, model: str = DECISION_MODEL, *, usd_per_m_input: Decimal = DEFAULT_USD_PER_M_INPUT,
                 resolution: str = "high", http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep):
        self._client = _DecisionsClient(api_key, model, usd_per_m_input, http, sleep)
        self.resolution = resolution
        self.spent_usd = Decimal(0)

    QUESTIONS = {
        "visible": {
            "type": "noul",
            "instructions": "Is a match clock (elapsed game time, e.g. 23:41) visible in the on-screen scoreboard?",
            "criteria": {"true_description": "A running game clock is readable on screen.",
                         "false_description": "No game clock is shown (replay, graphic, close-up, half-time) or it is unreadable."},
        },
        "minute": {
            "type": "choice",
            "instructions": "Read the minutes part of the on-screen match clock (the number before the colon).",
            "criteria": {f"m{m:03d}": f"{m} minutes" for m in range(131)},
        },
        "second": {
            "type": "choice",
            "instructions": "Read the seconds part of the on-screen match clock (the number after the colon).",
            "criteria": {f"s{s:02d}": f"{s} seconds" for s in range(60)},
        },
    }

    def read(self, png: Path) -> ClockReading | None:
        data = self._client.decide([_image_block(png, self.resolution)], self.QUESTIONS)
        self.spent_usd += self._client.usd(data)
        a = data["answers"]
        if float(a["visible"]["noul"]) < self.MIN_VISIBLE:
            return None
        minute = int(a["minute"]["choice"][1:])
        second = int(a["second"]["choice"][1:])
        conf = float(a["visible"]["noul"]) * float(a["minute"]["confidence"]) * float(a["second"]["confidence"])
        return ClockReading(minute=minute, second=second, confidence=conf)
