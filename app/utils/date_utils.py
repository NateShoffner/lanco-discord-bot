import calendar
import datetime as dt


def next_nth_weekday(from_date: dt.date, weekday: int, n: int) -> dt.date:
    """Return the next (or current) nth occurrence of a weekday on or after from_date.

    Args:
        from_date: The date to search from (inclusive).
        weekday: Day of the week (0=Monday, 6=Sunday).
        n: 1-based occurrence (1=first, 2=second, etc.).
    """
    for delta_months in range(3):
        month = (from_date.month - 1 + delta_months) % 12 + 1
        year = from_date.year + (from_date.month - 1 + delta_months) // 12
        occurrences = [
            dt.date(year, month, week[weekday])
            for week in calendar.monthcalendar(year, month)
            if week[weekday] != 0
        ]
        if len(occurrences) >= n and occurrences[n - 1] >= from_date:
            return occurrences[n - 1]
    return from_date  # fallback


def relative_date_str(event_date: dt.date) -> str:
    """Return a human-friendly relative date string.

    Returns 'tonight' if today, 'tomorrow' if tomorrow, otherwise a formatted
    date string like 'Thursday, June 26th'.
    """
    delta = (event_date - dt.date.today()).days
    if delta == 0:
        return "tonight"
    if delta == 1:
        return "tomorrow"
    day = event_date.day
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        day % 10 if day % 100 not in (11, 12, 13) else 0, "th"
    )
    return event_date.strftime(f"%A, %B {day}{suffix}")
