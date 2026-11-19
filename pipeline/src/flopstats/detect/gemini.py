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


def post_json(http: httpx.Client, url: str, body: dict, key: str, sleep: Callable[[float], None]) -> dict:
    """POST with retries: 429 waits as long as the API asks; 5xx/transport errors back off."""
    server_errors = rate_limits = 0
    while True:
        try:
            resp = http.post(url, json=body, headers={"x-goog-api-key": key})
        except httpx.TransportError as exc:
            server_errors += 1
            if server_errors > RETRIES:
                raise DecisionError(f"request failed ({type(exc).__name__})") from None
            sleep(2.0 ** (server_errors - 1))
            continue
        if resp.status_code == 429 and rate_limits < RATE_LIMIT_RETRIES:
            rate_limits += 1
            sleep(_retry_after_s(resp, default=2.0 ** min(rate_limits, 6)) + 1.0)
            continue
        if resp.status_code in (500, 502, 503, 504) and server_errors < RETRIES:
            server_errors += 1
            sleep(2.0 ** (server_errors - 1))
            continue
        if resp.status_code != 200:
            raise DecisionError(f"HTTP {resp.status_code} ({_error_detail(resp)})")
        return resp.json()


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
        return post_json(self._http, DECISIONS_URL, body, self._key, self._sleep)

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


# --- verifier (generateContent with structured JSON output) ------------------------------
# Docs: https://ai.google.dev/gemini-api/docs/structured-output (responseMimeType +
# responseJsonSchema) and https://ai.google.dev/gemini-api/docs/video-understanding
# (inline_data video). Usage: usageMetadata.promptTokenCount (input),
# candidatesTokenCount + thoughtsTokenCount (billed as output).

GENERATE_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_url(model: str) -> str:
    return f"{GENERATE_BASE}/{model}:generateContent"


class InvalidModelOutput(Exception):
    def __init__(self, message: str, usd: Decimal):
        super().__init__(message)
        self.usd = usd


def _inline_refs(schema: dict) -> dict:
    """Pydantic emits $defs/$ref; give the API one self-contained schema."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(dict(defs[node["$ref"].rsplit("/", 1)[-1]]))
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


VERIFY_PROMPT_V1 = """You are reviewing a short clip from a {home} (home) vs {away} (away) football match.
Decide whether a player in this clip flops: dives without contact, exaggerates light contact,
feigns an injury, or stays down to waste time. Genuine fouls with proportionate reactions and
genuine injuries are NOT flops.

Answer with JSON only, following the schema:
- is_flop, type (dive / exaggeration / feigned_injury / time_wasting, or null), confidence 0-1.
- start_s / end_s: when the flop starts and ends, in seconds from the start of this clip.
- is_replay: true if this is a replay or slow-motion repeat rather than live play.
- flopper: team (home/away), shirt number, name if you can tell, and your confidence.
- others: other players involved (e.g. the alleged fouler).
- attrs: time on the ground (s), rolls, fake pain 1-10, body part clutched vs where contact
  happened, contact level (none/light/real), miracle recovery and what triggered it, and the
  rough pitch position (x, y on 0-100 with the attacking team going left to right) with confidence.
- ref_decision: none / foul / yellow / red / penalty.
{kits}
Lineups (use them to name players by shirt number):
{lineups}
"""

PROMPTS = {"v1": VERIFY_PROMPT_V1}


class GeminiVerifier:
    def __init__(self, api_key: str, model: str, *, usd_per_m_input: Decimal, usd_per_m_output: Decimal,
                 prompt_version: str = "v1", http: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.name = model
        self._key = api_key
        self._in = Decimal(usd_per_m_input)
        self._out = Decimal(usd_per_m_output)
        self.prompt_version = prompt_version
        self._http = http or httpx.Client(timeout=300.0)
        self._sleep = sleep
        from flopstats.detect.verify import ModelAnswer

        self._schema = _inline_refs(ModelAnswer.model_json_schema())

    def _prompt(self, context) -> str:
        lineup = "\n".join(f"- {p.team}: #{p.shirt_number if p.shirt_number is not None else '?'} {p.name}"
                            for p in context.lineups) or "- (not available)"
        kits = f"Kits: {context.kit_notes}\n" if context.kit_notes else ""
        return PROMPTS[self.prompt_version].format(home=context.home_team, away=context.away_team,
                                                   lineups=lineup, kits=kits)

    def _usd(self, data: dict) -> Decimal:
        u = data.get("usageMetadata") or {}
        out_tokens = (u.get("candidatesTokenCount") or 0) + (u.get("thoughtsTokenCount") or 0)
        return (Decimal(u.get("promptTokenCount") or 0) * self._in + Decimal(out_tokens) * self._out) / Decimal(1_000_000)

    def verify(self, segment: Path, context):
        from pydantic import ValidationError

        from flopstats.detect.verify import ModelAnswer, VerifyResult

        body = {
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(Path(segment).read_bytes()).decode()}},
                {"text": self._prompt(context)},
            ]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": self._schema,
                                 "temperature": 0},
        }
        spent = Decimal(0)
        problem = ""
        for _attempt in range(2):  # one retry on invalid output
            data = post_json(self._http, generate_url(self.name), body, self._key, self._sleep)
            spent += self._usd(data)
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                answer = ModelAnswer.model_validate_json(text)
                return VerifyResult(**answer.model_dump(), usd=spent, model=self.name)
            except (KeyError, IndexError, TypeError, ValidationError, ValueError) as exc:
                problem = type(exc).__name__
        raise InvalidModelOutput(f"{self.name}: invalid output twice ({problem})", usd=spent)
