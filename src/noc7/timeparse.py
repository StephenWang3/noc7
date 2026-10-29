"""把一个时间原文解析成 TimeValue。

规则（PRD §6）：
- 原文写明时区 → explicit，按该时区归一（保留原偏移，不强制转成 UTC）；
- 原文没写时区 → 有系统口径时按口径解析并标 assumed；没有口径则 unknown、不带偏移；
- 不根据城市猜时区；
- “NA”、空串、{{end_time}} 这类占位符 → iso 为空，占位符另外标记，交给规则报 TIME_PLACEHOLDER。

只解析单个时间原文；从长文本里找时间是 A1 抽取模块的事。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .schema.timeval import TimePrecision, TimeValue, TimeZoneSource

_PLACEHOLDER = re.compile(r"\{\{\s*[\w.]+\s*\}\}")
_EMPTY = {"", "na", "n/a", "none", "null", "-", "--", "无", "暂无", "空"}
_LOCAL_ZONES = {"北京时间": "+08:00", "香港时间": "+08:00"}

_MAIN = re.compile(
    r"""^
    (?P<zone_prefix>北京时间|香港时间)?\s*
    (?P<y>\d{4})[-/.年](?P<m>\d{1,2})[-/.月](?P<d>\d{1,2})日?
    (?:[\sT]+(?P<H>\d{1,2})[:：时](?P<M>\d{2})(?:分|[:：分](?P<S>\d{2})秒?)?)?
    \s*\(?\s*
    (?P<tz>
        (?:GMT|UTC)\s*[+-]\s*\d{1,2}(?::?\d{2})?
      | GMT | UTC | Z
      | [+-]\d{2}:?\d{2}
      | 北京时间 | 香港时间
    )?
    \s*\)?$""",
    re.VERBOSE | re.IGNORECASE,
)
_GMT_OFFSET = re.compile(r"(?:GMT|UTC)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?", re.IGNORECASE)


def _offset_str(td: timedelta) -> str:
    total = int(td.total_seconds() // 60)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def _parse_tz(token: str) -> str:
    token = token.strip()
    if token in _LOCAL_ZONES:
        return _LOCAL_ZONES[token]
    if token.upper() in {"GMT", "UTC", "Z"}:
        return "+00:00"
    m = _GMT_OFFSET.fullmatch(token)
    if not m:
        raise ValueError(f"无法识别的时区: {token!r}")
    sign, hh, mm = m.group(1), int(m.group(2)), int(m.group(3) or 0)
    return f"{sign}{hh:02d}:{mm:02d}"


def _tzinfo(offset: str) -> timezone:
    sign = 1 if offset[0] == "+" else -1
    hh, mm = int(offset[1:3]), int(offset[4:6])
    return timezone(sign * timedelta(hours=hh, minutes=mm))


def parse_time(raw: str | None, default_offset: str | None = None) -> TimeValue:
    """解析单个时间原文。default_offset 是工单包声明的系统口径（如 '+08:00'）。"""
    text = re.sub(r"\s+", " ", (raw or "").strip()).replace("：", ":")
    text = re.sub(r"(?<=日)(?=\d{1,2}:)", " ", text)
    if _PLACEHOLDER.search(text):
        return TimeValue(raw=raw or "", placeholder=True)
    if text.lower() in _EMPTY:
        return TimeValue(raw=raw or "")

    # RFO 的日.月.四位年格式；不猜有歧义的斜杠短日期。
    day_first = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})([ T]+.*)?", text)
    if day_first:
        normalized = f"{day_first[3]}-{int(day_first[2]):02d}-{int(day_first[1]):02d}" + (day_first[4] or "")
        return parse_time(normalized, default_offset).model_copy(update={"raw": raw or ""})
    m = _MAIN.match(text)
    if m:
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        if m["H"] is None:
            return TimeValue(
                raw=raw or "",
                iso=f"{y:04d}-{mo:02d}-{d:02d}",
                precision=TimePrecision.DAY,
                tz_source=TimeZoneSource.UNKNOWN,
            )
        sec = int(m["S"]) if m["S"] else 0
        dt = datetime(y, mo, d, int(m["H"]), int(m["M"]), sec)
        precision = TimePrecision.SECOND if m["S"] else TimePrecision.MINUTE
        zone = m["tz"] or m["zone_prefix"]
        if zone:
            offset, source = _parse_tz(zone), TimeZoneSource.EXPLICIT
        elif default_offset:
            offset, source = default_offset, TimeZoneSource.ASSUMED
        else:
            offset, source = None, TimeZoneSource.UNKNOWN
        return _build(raw or "", dt, offset, source, precision)

    # 邮件头格式：Tue, 06 Oct 2026 17:30:00 +0000
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return TimeValue(raw=raw or "")
    precision = TimePrecision.SECOND
    if dt.tzinfo is None:
        if default_offset:
            return _build(raw or "", dt, default_offset, TimeZoneSource.ASSUMED, precision)
        return _build(raw or "", dt, None, TimeZoneSource.UNKNOWN, precision)
    return _build(raw or "", dt.replace(tzinfo=None), _offset_str(dt.utcoffset()), TimeZoneSource.EXPLICIT, precision)


def _build(
    raw: str, naive: datetime, offset: str | None, source: TimeZoneSource, precision: TimePrecision
) -> TimeValue:
    timespec = "seconds"
    if offset is None:
        return TimeValue(raw=raw, iso=naive.isoformat(timespec=timespec), tz_source=source, precision=precision)
    aware = naive.replace(tzinfo=_tzinfo(offset))
    return TimeValue(
        raw=raw,
        iso=aware.isoformat(timespec=timespec),
        tz_source=source,
        utc_offset=offset,
        precision=precision,
    )
