"""Unit tests for app/utils/sla.py — the business-hours SLA deadline
calculator backing the workflow doc's "High Priority -> Resolution target
within 1 business day" requirement (see docs/requirments/UAT_REPORT.md, D7)."""
from datetime import UTC, datetime

from app.models.enums import TicketPriority
from app.utils.sla import add_business_hours, compute_sla_due_at


def _dt(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


class TestAddBusinessHours:
    def test_same_day_within_business_hours(self):
        start = _dt(2026, 8, 24, 10, 0)  # Monday 10:00
        result = add_business_hours(start, 4)
        assert result == _dt(2026, 8, 24, 14, 0)

    def test_rolls_to_next_day_when_exceeding_business_hours(self):
        start = _dt(2026, 8, 24, 15, 0)  # Monday 15:00, 2h left in the day
        result = add_business_hours(start, 4)  # needs 2 more hours next day
        assert result == _dt(2026, 8, 25, 11, 0)  # Tuesday 09:00 + 2h

    def test_skips_weekend(self):
        friday_2pm = _dt(2026, 8, 21, 14, 0)
        assert friday_2pm.strftime("%A") == "Friday"
        result = add_business_hours(friday_2pm, 8)  # 1 business day
        assert result.strftime("%A") == "Monday"
        assert result == _dt(2026, 8, 24, 14, 0)

    def test_ticket_filed_after_hours_starts_next_business_day(self):
        friday_evening = _dt(2026, 8, 21, 22, 0)
        result = add_business_hours(friday_evening, 1)
        assert result.strftime("%A") == "Monday"
        assert result == _dt(2026, 8, 24, 10, 0)

    def test_ticket_filed_on_weekend_starts_next_monday(self):
        saturday = _dt(2026, 8, 22, 12, 0)
        result = add_business_hours(saturday, 1)
        assert result.strftime("%A") == "Monday"
        assert result == _dt(2026, 8, 24, 10, 0)

    def test_ticket_filed_before_business_hours_clamps_to_start(self):
        early_monday = _dt(2026, 8, 24, 6, 0)
        result = add_business_hours(early_monday, 1)
        assert result == _dt(2026, 8, 24, 10, 0)


class TestComputeSlaDueAt:
    def test_high_priority_is_one_business_day(self):
        monday_9am = _dt(2026, 8, 24, 9, 0)
        due = compute_sla_due_at(TicketPriority.high, monday_9am)
        assert due == _dt(2026, 8, 24, 17, 0)

    def test_critical_tighter_than_high(self):
        start = _dt(2026, 8, 24, 9, 0)
        critical_due = compute_sla_due_at(TicketPriority.critical, start)
        high_due = compute_sla_due_at(TicketPriority.high, start)
        assert critical_due < high_due

    def test_low_looser_than_medium(self):
        start = _dt(2026, 8, 24, 9, 0)
        medium_due = compute_sla_due_at(TicketPriority.medium, start)
        low_due = compute_sla_due_at(TicketPriority.low, start)
        assert low_due > medium_due

    def test_defaults_to_now_when_no_created_at_given(self):
        # Just confirm it doesn't raise and returns a real datetime with tz info.
        due = compute_sla_due_at(TicketPriority.medium)
        assert due.tzinfo is not None
