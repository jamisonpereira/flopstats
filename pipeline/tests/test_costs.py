from decimal import Decimal

import pytest

from flopstats import costs


def _record(db, key, usd):
    return costs.record(
        db, service="gemini", model="gemini-decision-1", units={"input_tokens": 1000},
        usd=Decimal(usd), idempotency_key=key,
    )


def test_spent_is_zero_when_empty(db):
    assert costs.spent(db) == Decimal("0")


def test_cost_record_idempotent(db):
    assert _record(db, "window:1:42", "0.0125") is True
    assert costs.spent(db) == Decimal("0.0125")
    assert _record(db, "window:1:42", "0.0125") is False
    assert costs.spent(db) == Decimal("0.0125")
    assert _record(db, "window:1:43", "0.0100") is True
    assert costs.spent(db) == Decimal("0.0225")


def test_guard_raises_when_estimate_would_exceed_budget(db, settings):
    assert settings.budget_usd == Decimal("500")
    _record(db, "bulk", "499.50")
    with pytest.raises(costs.BudgetExceeded):
        costs.guard(db, settings, Decimal("0.60"))


def test_guard_allows_spend_up_to_budget(db, settings):
    _record(db, "bulk", "499.50")
    costs.guard(db, settings, Decimal("0.50"))  # exactly 500: allowed


def test_tiny_charges_are_not_rounded(db):
    for i in range(3):
        _record(db, f"w{i}", "0.0001649")
    assert costs.spent(db) == Decimal("0.0004947")
