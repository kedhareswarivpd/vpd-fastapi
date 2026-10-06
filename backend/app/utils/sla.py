from datetime import UTC, datetime, timedelta

from app.models.enums import TicketPriority

# Workflow doc §12 ("Priority-Based Support"): "High Priority -> Resolution
# target within 1 business day". Only High is given a concrete number in the
# doc; the other three tiers are reasonable, standard support-desk multiples
# of that one anchor point (Critical tighter, Medium/Low looser) — there's no
# other source of truth to derive them from.
_SLA_BUSINESS_HOURS = {
    TicketPriority.critical: 4,
    TicketPriority.high: 8,   # 1 business day (8-hour business day)
    TicketPriority.medium: 24,  # 3 business days
    TicketPriority.low: 40,   # 5 business days
}

BUSINESS_DAY_START_HOUR = 9
BUSINESS_DAY_END_HOUR = 17


def _is_business_day(d: datetime) -> bool:
    return d.weekday() < 5  # Mon-Fri


def add_business_hours(start: datetime, hours: float) -> datetime:
    """Adds `hours` of business time (Mon-Fri, 09:00-17:00) to `start`,
    skipping weekends and after-hours entirely — a ticket filed Friday
    afternoon doesn't get "resolved" over the weekend by the clock alone.
    Simple day-stepping loop; ticket SLA windows are small (hours, not
    months) so this never iterates more than a handful of times."""
    remaining = timedelta(hours=hours)
    current = start

    # Clamp the starting point into business hours first.
    if not _is_business_day(current) or current.hour >= BUSINESS_DAY_END_HOUR:
        current = (current + timedelta(days=1)).replace(hour=BUSINESS_DAY_START_HOUR, minute=0, second=0, microsecond=0)
        while not _is_business_day(current):
            current += timedelta(days=1)
    elif current.hour < BUSINESS_DAY_START_HOUR:
        current = current.replace(hour=BUSINESS_DAY_START_HOUR, minute=0, second=0, microsecond=0)

    while remaining > timedelta(0):
        day_end = current.replace(hour=BUSINESS_DAY_END_HOUR, minute=0, second=0, microsecond=0)
        available_today = day_end - current
        if remaining <= available_today:
            return current + remaining
        remaining -= available_today
        current = (current + timedelta(days=1)).replace(hour=BUSINESS_DAY_START_HOUR, minute=0, second=0, microsecond=0)
        while not _is_business_day(current):
            current += timedelta(days=1)

    return current


def compute_sla_due_at(priority: TicketPriority, created_at: datetime | None = None) -> datetime:
    created_at = created_at or datetime.now(UTC)
    hours = _SLA_BUSINESS_HOURS.get(priority, _SLA_BUSINESS_HOURS[TicketPriority.medium])
    return add_business_hours(created_at, hours)
