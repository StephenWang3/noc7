import pytest

from noc7.schema import TimePrecision, TimeZoneSource
from noc7.timeparse import parse_time


@pytest.mark.parametrize(
    "raw, default, iso, tz, precision",
    [
        ("2026-09-30 03:02:00", "+08:00", "2026-09-30T03:02:00+08:00", TimeZoneSource.ASSUMED, TimePrecision.SECOND),
        ("2026-09-30 03:02:00", None, "2026-09-30T03:02:00", TimeZoneSource.UNKNOWN, TimePrecision.SECOND),
        ("2026-09-30 02:40 (GMT+8)", None, "2026-09-30T02:40:00+08:00", TimeZoneSource.EXPLICIT, TimePrecision.MINUTE),
        ("北京时间 2026-09-12 01:06", "+00:00", "2026-09-12T01:06:00+08:00", TimeZoneSource.EXPLICIT, TimePrecision.MINUTE),
        ("2026/10/06 14:38 UTC", "+08:00", "2026-10-06T14:38:00+00:00", TimeZoneSource.EXPLICIT, TimePrecision.MINUTE),
        ("2026年10月6日 14时38分", None, "2026-10-06T14:38:00", TimeZoneSource.UNKNOWN, TimePrecision.MINUTE),
        ("2026-09-03", "+08:00", "2026-09-03", TimeZoneSource.UNKNOWN, TimePrecision.DAY),
        ("Tue, 06 Oct 2026 17:30:00 +0000", "+08:00", "2026-10-06T17:30:00+00:00", TimeZoneSource.EXPLICIT, TimePrecision.SECOND),
        ("Fri, 25 Sep 2026 09:16:42 +0800", None, "2026-09-25T09:16:42+08:00", TimeZoneSource.EXPLICIT, TimePrecision.SECOND),
    ],
)
def test_parse(raw, default, iso, tz, precision):
    v = parse_time(raw, default)
    assert (v.iso, v.tz_source, v.precision) == (iso, tz, precision)
    assert v.raw == raw


@pytest.mark.parametrize("raw", ["{{end_time}}", "restored at {{ end_time }}"])
def test_placeholder_is_not_a_time(raw):
    v = parse_time(raw, "+08:00")
    assert v.placeholder and v.iso is None


@pytest.mark.parametrize("raw", ["NA", "", "无", None, "昨天下午"])
def test_missing_or_unparsable(raw):
    v = parse_time(raw, "+08:00")
    assert v.iso is None and not v.placeholder


def test_utc_and_gmt8_cross_day_are_equal():
    a = parse_time("Tue, 06 Oct 2026 17:20:00 +0000").as_datetime()
    b = parse_time("2026-10-07 01:20", "+08:00").as_datetime()
    assert a == b


@pytest.mark.parametrize('raw,iso,precision', [
    ('09/23/2026 1:04:05 PM UTC', '2026-09-23T13:04:05+00:00', 'second'),
    ('23/09/2026 12:04 am UTC', '2026-09-23T00:04:00+00:00', 'minute'),
    ('2026-09-23 12:04 PM UTC', '2026-09-23T12:04:00+00:00', 'minute'),
    ('2026-09-23 1:04 pm +02:00', '2026-09-23T13:04:00+02:00', 'minute'),
    ('23.09.2026 1:04 PM UTC', '2026-09-23T13:04:00+00:00', 'minute'),
])
def test_twelve_hour_complete_dates(raw, iso, precision):
    value = parse_time(raw, '+08:00')
    assert (value.iso, value.precision, value.tz_source, value.raw) == (iso, precision, 'explicit', raw)


@pytest.mark.parametrize('raw', [
    '09/10/2026 1:04 PM UTC', '13/23/2026 1:04 PM UTC',
    '09/23/2026 00:04 PM UTC', '09/23/2026 13:04 PM UTC',
    '02/30/2026 1:04 PM UTC', '2026-09-23 1:60 PM UTC',
])
def test_invalid_or_ambiguous_twelve_hour_time(raw):
    assert parse_time(raw, '+08:00').iso is None


@pytest.mark.parametrize('raw', ['2026-09-23 PM', '2026-09-23 PM UTC'])
def test_meridiem_without_clock_is_not_a_date(raw):
    value = parse_time(raw, '+08:00')
    assert value.iso is None and value.precision is None and value.raw == raw


@pytest.mark.parametrize(
    "raw, iso, tz",
    [
        ("November 6, 2026, 5:26 PM GMT-6", "2026-11-06T17:26:00-06:00", TimeZoneSource.EXPLICIT),
        ("22:17 (GMT+8) on November 5, 2026", "2026-11-05T22:17:00+08:00", TimeZoneSource.EXPLICIT),
        ("2026-11-05, 20:12GMT", "2026-11-05T20:12:00+00:00", TimeZoneSource.EXPLICIT),
        ("Nov 5th 2026 08:00 UTC", "2026-11-05T08:00:00+00:00", TimeZoneSource.EXPLICIT),
        ("5-Nov-2026 08:00:10", "2026-11-05T08:00:10", TimeZoneSource.UNKNOWN),
        ("05 Nov 2026 17:15", "2026-11-05T17:15:00", TimeZoneSource.UNKNOWN),
        ("13:34 hrs 18/11/2026", "2026-11-18T13:34:00", TimeZoneSource.UNKNOWN),
        ("November 6, 2026", "2026-11-06", TimeZoneSource.UNKNOWN),
    ],
)
def test_english_and_time_first_formats(raw, iso, tz):
    v = parse_time(raw, None)
    assert (v.iso, v.tz_source, v.raw) == (iso, tz, raw)


@pytest.mark.parametrize(
    "raw",
    [
        "13:34 hrs 8/11/2026",  # 日月顺序有歧义，不猜
        "13:05 LT, (GMT+7)",  # 只有时刻，没有日期
        "call 5 Nov 2026 08:00",  # 有多余文字，不猜
        "restored November 6, 2026, 5:26 PM GMT-6",
    ],
)
def test_ambiguous_or_extra_text_is_not_guessed(raw):
    assert parse_time(raw, "+08:00").iso is None


def test_loose_email_parser_no_longer_drops_meridiem_or_zone():
    # 旧实现会得到 05:26 并套用系统时区。
    v = parse_time("November 6, 2026, 5:26 PM GMT-6", "+08:00")
    assert v.iso == "2026-11-06T17:26:00-06:00"
