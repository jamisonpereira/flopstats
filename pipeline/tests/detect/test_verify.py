import json
from decimal import Decimal

import httpx
import pytest
import respx

from flopstats import costs
from flopstats.detect import verify
from flopstats.detect.gemini import GeminiVerifier, InvalidModelOutput, generate_url
from flopstats.detect.verify import FlopAttrs, LineupPlayer, PlayerGuess, VerifyContext, VerifyResult

KEY = "gem-test-key"


def result(model_conf=0.8, **kw):
    base = dict(is_flop=True, type="dive", confidence=model_conf, start_s=3.0, end_s=9.0, is_replay=False,
                flopper=PlayerGuess(team="home", shirt_number=7, name="Mount", confidence=0.9), others=[],
                attrs=FlopAttrs(contact_level="light", fake_pain=6), ref_decision="foul", usd=Decimal("0.01"))
    base.update(kw)
    return VerifyResult(**base)


CTX = VerifyContext(lineups=[LineupPlayer(team="home", shirt_number=7, name="Mason Mount")],
                    home_team="Manchester United", away_team="Fulham", kit_notes=None)


class FakeVerifier:
    def __init__(self, name, res=None, exc=None):
        self.name, self.res, self.exc, self.calls = name, res, exc, 0

    def verify(self, segment, context):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.res


@pytest.fixture
def candidate(db):
    one = lambda sql, *p: db.execute(sql, p).fetchone()[0]
    v = one("insert into videos (source, source_url) values ('footballia', 'u') returning id")
    r = one("insert into detection_runs (name, config) values ('r', '{}') returning id")
    c = one("insert into candidates (run_id, video_id, start_s, end_s, final_score, status) values (%s, %s, 100, 140, 0.8, 'pending') returning id", r, v)
    return {"candidate": c, "run": r}


def test_verify_result_validates_ranges():
    with pytest.raises(ValueError):
        result(model_conf=1.5)
    with pytest.raises(ValueError):
        result(type="flop")
    with pytest.raises(ValueError):
        FlopAttrs(fake_pain=11)


def test_multiple_verifiers_each_stored(db, candidate, tmp_path):
    a, b = FakeVerifier("gemini-pro", result(0.8)), FakeVerifier("other-model", result(0.6))
    out = verify.run(db, candidate["candidate"], tmp_path / "seg.mp4", [a, b], CTX, run_id=candidate["run"])
    assert [r.confidence for r in out] == [0.8, 0.6]
    rows = db.execute("select model, confidence, usd from verifications order by model").fetchall()
    assert rows == [("gemini-pro", pytest.approx(0.8), Decimal("0.01")), ("other-model", pytest.approx(0.6), Decimal("0.01"))]
    assert costs.spent(db) == Decimal("0.02")
    assert verify.primary(out, "other-model").confidence == 0.6


def test_verify_skips_already_stored_model(db, candidate, tmp_path):
    first = FakeVerifier("gemini-pro", result(0.8))
    verify.run(db, candidate["candidate"], tmp_path / "s.mp4", [first], CTX, run_id=candidate["run"])
    again = FakeVerifier("gemini-pro", result(0.1))
    out = verify.run(db, candidate["candidate"], tmp_path / "s.mp4", [again], CTX, run_id=candidate["run"])
    assert again.calls == 0  # no second paid call
    assert out[0].confidence == 0.8 and out[0].flopper.shirt_number == 7  # rebuilt from the stored row
    assert costs.spent(db) == Decimal("0.01")
    assert db.execute("select count(*) from verifications").fetchone()[0] == 1


def test_invalid_output_is_stored_as_rejected_and_not_retried(db, candidate, tmp_path):
    bad = FakeVerifier("gemini-pro", exc=InvalidModelOutput("bad JSON twice", usd=Decimal("0.02")))
    assert verify.run(db, candidate["candidate"], tmp_path / "s.mp4", [bad], CTX, run_id=candidate["run"]) == []
    answers, conf = db.execute("select answers, confidence from verifications").fetchone()
    assert answers["invalid"] is True and conf is None
    assert costs.spent(db) == Decimal("0.02")  # the failed calls were still paid for
    again = FakeVerifier("gemini-pro", res=result())
    assert verify.run(db, candidate["candidate"], tmp_path / "s.mp4", [again], CTX, run_id=candidate["run"]) == []
    assert again.calls == 0
    with pytest.raises(LookupError):
        verify.primary([], "gemini-pro")


# --- the Gemini adapter -------------------------------------------------------------------

def _gen(text, prompt_tokens=10_000, out_tokens=500):
    return httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": prompt_tokens, "candidatesTokenCount": out_tokens, "thoughtsTokenCount": 100},
    })


def _good_json():
    r = result().model_dump(mode="json")
    r.pop("usd")
    return json.dumps(r)


@respx.mock
def test_gemini_verifier_parses_structured_output_and_cost(tmp_path):
    seg = tmp_path / "s.mp4"
    seg.write_bytes(b"vid")
    route = respx.post(generate_url("gemini-pro-latest")).mock(return_value=_gen(_good_json()))
    v = GeminiVerifier(KEY, "gemini-pro-latest", usd_per_m_input=Decimal("2"), usd_per_m_output=Decimal("12"), prompt_version="v1")
    r = v.verify(seg, CTX)
    assert r.type == "dive" and r.flopper.shirt_number == 7
    assert r.usd == Decimal("10000") * 2 / 1_000_000 + Decimal("600") * 12 / 1_000_000  # thinking billed as output
    body = json.loads(route.calls[0].request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "Mason Mount" in json.dumps(body["contents"]) and "usd" not in json.dumps(body["generationConfig"]["responseJsonSchema"])


@respx.mock
def test_invalid_model_json_retried_once_then_rejected(tmp_path):
    seg = tmp_path / "s.mp4"
    seg.write_bytes(b"vid")
    route = respx.post(generate_url("gemini-pro-latest")).mock(side_effect=[_gen("not json"), _gen('{"is_flop": "maybe"}')])
    v = GeminiVerifier(KEY, "gemini-pro-latest", usd_per_m_input=Decimal("2"), usd_per_m_output=Decimal("12"))
    with pytest.raises(InvalidModelOutput) as exc:
        v.verify(seg, CTX)
    assert route.call_count == 2
    assert exc.value.usd > 0


@respx.mock
def test_invalid_json_then_valid_on_retry(tmp_path):
    seg = tmp_path / "s.mp4"
    seg.write_bytes(b"vid")
    respx.post(generate_url("m")).mock(side_effect=[_gen("```oops"), _gen(_good_json())])
    r = GeminiVerifier(KEY, "m", usd_per_m_input=Decimal("1"), usd_per_m_output=Decimal("1")).verify(seg, CTX)
    assert r.is_flop and r.usd == Decimal(2 * 10_000 + 2 * 600) / 1_000_000  # both attempts paid


def test_nul_characters_in_model_text_are_dropped(db, candidate, tmp_path):
    # Pilot: a verifier returned the flopper name "Andr\u0000..."; Postgres text/jsonb can't hold NUL.
    raw = json.dumps({"is_flop": True, "type": "dive", "confidence": 0.9, "start_s": 1, "end_s": 4,
                      "flopper": {"team": "home", "shirt_number": 24, "name": "Andr\u0000é Onana"},
                      "attrs": {"clutched_part": "kn\u0000ee"}, "others": [{"name": "\u0000"}]})
    answer = verify.ModelAnswer.model_validate_json(raw)
    assert answer.flopper.name == "André Onana"
    assert answer.attrs.clutched_part == "knee"
    res = VerifyResult(**answer.model_dump(), usd=Decimal("0.01"), model="m")
    verify.run(db, candidate["candidate"], tmp_path / "seg.mp4", [FakeVerifier("m", res)], CTX, run_id=candidate["run"])
    stored = db.execute("select answers->'flopper'->>'name' from verifications").fetchone()[0]
    assert stored == "André Onana"


def test_a_blocked_verifier_call_is_stored_not_raised(db, candidate, tmp_path):
    from flopstats.detect.gemini import ContentBlocked
    blocked = FakeVerifier("m", exc=ContentBlocked("HTTP 400 (prohibited_content: Input blocked)"))
    out = verify.run(db, candidate["candidate"], tmp_path / "seg.mp4", [blocked], CTX, run_id=candidate["run"])
    assert out == []
    answers = db.execute("select answers from verifications").fetchone()[0]
    assert answers["invalid"] is True and answers["blocked"] is True
