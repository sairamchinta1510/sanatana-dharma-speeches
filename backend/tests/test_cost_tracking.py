import pytest
import os
import time
from unittest.mock import patch
from services.cost_tracking_service import CostTrackingService, BudgetExceededError

os.environ["DB_PATH"] = ":memory:"


@pytest.fixture
def tracker():
    import database
    database.init_db()
    # Clear any existing data from previous tests
    with database.db() as conn:
        conn.execute("DELETE FROM llm_cost_log")
    return CostTrackingService(daily_limit_usd=1.0)


def test_record_and_get_daily_cost(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.0001)
    assert tracker.get_today_cost() == pytest.approx(0.0001)


def test_accumulates_multiple_calls(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.40)
    tracker.record(model="haiku", tokens_in=600, tokens_out=200, cost_usd=0.35)
    assert tracker.get_today_cost() == pytest.approx(0.75)


def test_budget_not_exceeded_below_limit(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.50)
    assert tracker.is_budget_exceeded() is False


def test_budget_exceeded_at_limit(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=1.00)
    assert tracker.is_budget_exceeded() is True


def test_warning_threshold(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.96)
    assert tracker.is_warning_threshold() is True


def test_no_warning_below_threshold(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=0.50)
    assert tracker.is_warning_threshold() is False


def test_raise_if_exceeded(tracker):
    tracker.record(model="llama", tokens_in=300, tokens_out=150, cost_usd=1.01)
    with pytest.raises(BudgetExceededError):
        tracker.raise_if_exceeded()
