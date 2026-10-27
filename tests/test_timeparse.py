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
