from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.modules.routines.recurrence import RecurrenceRule, generate_occurrences

SP = "America/Sao_Paulo"


def rule(**over) -> RecurrenceRule:
    base = {
        "frequency": "daily",
        "time": "07:00",
        "timezone": SP,
        "start_date": "2026-11-03",
    }
    return RecurrenceRule(**{**base, **over})


def dates(r: RecurrenceRule, start: str, end: str) -> list[str]:
    window = generate_occurrences(r, datetime.fromisoformat(start), datetime.fromisoformat(end))
    return [
        i.astimezone(__import__("zoneinfo").ZoneInfo(r.timezone)).strftime("%m-%d %H:%M")
        for i in window
    ]


UTC_WIN = ("2026-11-01T00:00:00+00:00", "2027-03-01T00:00:00+00:00")


def test_daily_every_day_converts_local_time_to_utc():
    out = generate_occurrences(
        rule(), datetime(2026, 11, 3, tzinfo=UTC), datetime(2026, 11, 6, tzinfo=UTC)
    )
    assert out == [
        datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
        datetime(2026, 11, 4, 10, 0, tzinfo=UTC),
        datetime(2026, 11, 5, 10, 0, tzinfo=UTC),
    ]


def test_daily_interval_counts_from_start_date():
    r = rule(interval=3)
    assert dates(r, "2026-11-01T00:00:00+00:00", "2026-11-14T00:00:00+00:00") == [
        "11-03 07:00",
        "11-06 07:00",
        "11-09 07:00",
        "11-12 07:00",
    ]


def test_weekly_specific_days_and_not_before_start():
    r = rule(frequency="weekly", by_weekday=["mon", "wed", "fri"], start_date="2026-11-04")
    # 2026-11-02 é segunda (anterior ao início) e não conta
    assert dates(r, "2026-11-01T00:00:00+00:00", "2026-11-10T00:00:00+00:00") == [
        "11-04 07:00",
        "11-06 07:00",
        "11-09 07:00",
    ]


def test_weekly_interval_two_weeks():
    r = rule(frequency="weekly", interval=2, by_weekday=["tue"], start_date="2026-11-03")
    assert (
        dates(r, "2026-11-01T00:00:00+00:00", "2026-12-10T00:00:00+00:00")
        == [
            "11-03 07:00",
            "11-17 07:00",
            "12-01 07:00",
            "12-15 07:00",
        ][:3]
    )


def test_monthly_day_and_skipped_short_months():
    r = rule(frequency="monthly", by_month_day=[31], start_date="2026-01-01")
    assert dates(r, "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00") == [
        "01-31 07:00",
        "03-31 07:00",
        "05-31 07:00",
    ]


def test_monthly_last_day_handles_february_and_leap_year():
    r = rule(frequency="monthly", by_month_day=[-1], start_date="2027-12-01")
    got = dates(r, "2027-12-01T00:00:00+00:00", "2028-04-01T00:00:00+00:00")
    assert got == ["12-31 07:00", "01-31 07:00", "02-29 07:00", "03-31 07:00"]
    non_leap = dates(
        rule(frequency="monthly", by_month_day=[-1], start_date="2026-01-01"),
        "2026-02-01T00:00:00+00:00",
        "2026-03-01T00:00:00+00:00",
    )
    assert non_leap == ["02-28 07:00"]


def test_monthly_multiple_days_and_interval():
    r = rule(frequency="monthly", interval=2, by_month_day=[1, 15, -1], start_date="2026-11-01")
    got = dates(r, "2026-11-01T00:00:00+00:00", "2027-01-31T00:00:00+00:00")
    assert got == ["11-01 07:00", "11-15 07:00", "11-30 07:00", "01-01 07:00", "01-15 07:00"]


def test_end_date_inclusive_and_count():
    r = rule(end_date="2026-11-05")
    assert len(dates(r, *UTC_WIN)) == 3
    r = rule(count=2)
    assert dates(r, *UTC_WIN) == ["11-03 07:00", "11-04 07:00"]
    # count conta desde o início da série, mesmo com janela posterior
    assert dates(r, "2026-11-04T00:00:00+00:00", "2026-11-30T00:00:00+00:00") == ["11-04 07:00"]


def test_window_is_half_open_and_empty_when_inverted():
    r = rule()
    start = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
    assert generate_occurrences(r, start, datetime(2026, 11, 3, 10, 0, tzinfo=UTC)) == []
    assert generate_occurrences(r, start, datetime(2026, 11, 3, 10, 1, tzinfo=UTC)) == [start]
    assert generate_occurrences(r, datetime(2026, 11, 3, 10, 1, tzinfo=UTC), start) == []


def test_naive_window_rejected():
    with pytest.raises(ValueError):
        generate_occurrences(rule(), datetime(2026, 11, 3), datetime(2026, 11, 4))


def test_dst_zone_uses_wall_clock_time():
    r = rule(timezone="America/New_York", time="09:00", start_date="2026-03-07")
    out = generate_occurrences(
        r, datetime(2026, 3, 7, tzinfo=UTC), datetime(2026, 3, 10, tzinfo=UTC)
    )
    # antes do DST (UTC-5) e depois (UTC-4): mesmo horário local, instantes UTC distintos
    assert [i.hour for i in out] == [14, 13, 13]


@pytest.mark.parametrize(
    "over",
    [
        {"frequency": "yearly"},
        {"interval": 0},
        {"time": "25:00"},
        {"time": "07:00:30"},
        {"time": "07:00-03:00"},
        {"timezone": "Marte/Olympus"},
        {"timezone": ""},
        {"end_date": "2026-11-02"},
        {"count": 0},
        {"frequency": "weekly"},  # sem by_weekday
        {"frequency": "weekly", "by_weekday": []},
        {"frequency": "weekly", "by_weekday": ["mon", "mon"]},
        {"frequency": "weekly", "by_weekday": ["segunda"]},
        {"frequency": "monthly"},  # sem by_month_day
        {"frequency": "monthly", "by_month_day": [0]},
        {"frequency": "monthly", "by_month_day": [32]},
        {"frequency": "monthly", "by_month_day": [-2]},
        {"frequency": "monthly", "by_month_day": [5, 5]},
        {"frequency": "daily", "by_weekday": ["mon"]},
        {"frequency": "weekly", "by_weekday": ["mon"], "by_month_day": [1]},
        {"extra": 1},
    ],
)
def test_invalid_rules(over):
    with pytest.raises(ValidationError):
        rule(**over)


def test_rule_roundtrips_json():
    r = rule(frequency="monthly", by_month_day=[-1])
    assert RecurrenceRule.model_validate(r.model_dump(mode="json")) == r
    assert r.start_date == date(2026, 11, 3)
