from datetime import date
from database import db


class BudgetExceededError(Exception):
    """Raised when the daily LLM budget has been exceeded."""


class CostTrackingService:
    def __init__(self, daily_limit_usd: float = 1.0):
        self.daily_limit_usd = daily_limit_usd
        self._warning_threshold = daily_limit_usd * 0.95

    def record(self, model: str, tokens_in: int, tokens_out: int, cost_usd: float) -> None:
        today = date.today().isoformat()
        with db() as conn:
            conn.execute(
                "INSERT INTO llm_cost_log (date, model, tokens_in, tokens_out, cost_usd) "
                "VALUES (?, ?, ?, ?, ?)",
                (today, model, tokens_in, tokens_out, cost_usd),
            )

    def get_today_cost(self) -> float:
        today = date.today().isoformat()
        with db() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_cost_log WHERE date = ?",
                (today,),
            ).fetchone()
        return float(row[0])

    def is_budget_exceeded(self) -> bool:
        return self.get_today_cost() >= self.daily_limit_usd

    def is_warning_threshold(self) -> bool:
        return self.get_today_cost() >= self._warning_threshold

    def raise_if_exceeded(self) -> None:
        if self.is_budget_exceeded():
            raise BudgetExceededError(
                f"Daily LLM budget of ${self.daily_limit_usd} exceeded. "
                "Falling back to keyword search."
            )
