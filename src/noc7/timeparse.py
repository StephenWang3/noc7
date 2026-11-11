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

# 整体匹配，防止正文提取时将 PM 丢掉或只取出其中的时钟。
TWELVE_TIME_PATTERN = (
    r"(?<![\d/])(?:\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|"
    r"\d{1,2}[/\.]\d{1,2}[/\.]\d{4})(?:\s+|T)"
    r"\d{1,2}[:：时]\d{2}(?:分|[:：分]\d{2}秒?)?\s*(?:AM|PM)\b"
)

_MAIN = re.compile(
    r"""^
    (?P<zone_prefix>北京时间|香港时间)?\s*
    (?P<y>\d{4})[-/.年](?P<m>\d{1,2})[-/.月](?P<d>\d{1,2})日?
    (?:[\sT]+(?P<H>\d{1,2})[:：时](?P<M>\d{2})(?:分|[:：分](?P<S>\d{2})秒?)?)?
    \s*(?P<ampm>AM|PM)?\s*\(?\s*
    (?P<tz>
        (?:GMT|UTC)\s*[+-]\s*\d{1,2}(?::?\d{2})?
      | GMT | UTC | Z
      | [+-]\d{2}:?\d{2}
      | 北京时间 | 香港时间
    )?
    \s*\)?$""",
    re.VERBOSE | re.IGNORECASE,
)
_MONTHS = {
    name: i + 1
    for i, names in enumerate(
        ["jan january", "feb february", "mar march", "apr april", "may", "jun june", "jul july",
         "aug august", "sep sept september", "oct october", "nov november", "dec december"]
    )
    for name in names.split()
}
_MONTH = "(?P<mon>" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_ORD = r"(?:st|nd|rd|th)?"
# RFO 里的英文日期：November 6, 2026 / 05 Nov 2026 / 5-Nov-2026。
_MONTH_DATES = (
    re.compile(rf"(?<![A-Za-z]){_MONTH}\s+(?P<d>\d{{1,2}}){_ORD}\s*,?\s*(?P<y>\d{{4}})(?!\d)", re.I),
    re.compile(rf"(?<!\d)(?P<d>\d{{1,2}}){_ORD}[\s-]+{_MONTH}[\s,-]+(?P<y>\d{{4}})(?!\d)", re.I),
)
_NUMERIC_DATE = re.compile(
    r"(?<![\d/.-])(?:\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{1,2}([/.])\d{1,2}\1\d{4})(?![\d/.-])"
)
_ZONE_ANY = re.compile(
    r"(?:GMT|UTC)\s*[+-]\s*\d{1,2}(?::?\d{2})?|GMT|UTC|(?<![A-Za-z])Z(?![A-Za-z])"
    r"|(?<![\d:])[+-]\d{2}:?\d{2}(?!\d)|北京时间|香港时间",
    re.I,
)
_CLOCK_ANY = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])\s*(AM|PM)?(?![A-Za-z])", re.I)
# 时间短语里不带信息的词：13:34 hrs、13:05 LT、22:17 on November 5。
_NOISE = re.compile(
    r"\b(?:hrs?|hours?|h|lt|local\s+time|on|at|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b\.?|[,()\[\]，（）\s]",
    re.I,
)
# 邮件头格式只认完整形状；其余文本不交给宽松的邮件解析，免得把 PM、GMT-6 悄悄丢掉。
_EMAIL_DATE = re.compile(
    r"(?:[A-Za-z]{3},\s*)?\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?"
    r"(?:\s*(?:[+-]\d{4}|GMT|UTC|UT|Z|[ECMP][SD]T))?(?:\s*\([A-Za-z ]+\))?",
    re.I,
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


def _reorder(text: str) -> str | None:
    """把“先时刻后日期”“英文月份名”等写法改排成 日期 时刻 [AM/PM] [时区]。

    只在整段文字除日期、时刻、时区和无信息词之外没有别的内容时才改排；有剩余就不猜。
    只有时刻、没有日期的写法不在这里处理。
    """
    rest, date = text, None
    for pattern in _MONTH_DATES:
        m = pattern.search(rest)
        if m:
            date = f"{int(m['y']):04d}-{_MONTHS[m['mon'].lower()]:02d}-{int(m['d']):02d}"
            rest = rest[: m.start()] + " " + rest[m.end():]
            break
    if date is None:
        m = _NUMERIC_DATE.search(rest)
        if not m:
            return None
        date = m.group()  # 斜杠日期的日月歧义留给 parse_time 原有规则判断
        rest = rest[: m.start()] + " " + rest[m.end():]
    zone = _ZONE_ANY.search(rest)
    if zone:
        rest = rest[: zone.start()] + " " + rest[zone.end():]
    clock = _CLOCK_ANY.search(rest)
    if clock:
        rest = rest[: clock.start()] + " " + rest[clock.end():]
    if _NOISE.sub("", rest):
        return None
    parts = [date]
    if clock:
        parts.append(clock.group().strip())
    if zone:
        parts.append(re.sub(r"\s+", "", zone.group()))
    return " ".join(parts)


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
    slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})([ T]+.*)?", text)
    if slash:
        first, second = int(slash[1]), int(slash[2])
        if (first > 12) == (second > 12):
            return TimeValue(raw=raw or "")
        month, day = (second, first) if first > 12 else (first, second)
        normalized = f"{slash[3]}-{month:02d}-{day:02d}" + (slash[4] or "")
        return parse_time(normalized, default_offset).model_copy(update={"raw": raw or ""})
    m = _MAIN.match(text)
    if m:
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        try:
            datetime(y, mo, d)
        except ValueError:
            return TimeValue(raw=raw or "")
        if m["H"] is None:
            if m["ampm"]:
                return TimeValue(raw=raw or "")
            return TimeValue(
                raw=raw or "",
                iso=f"{y:04d}-{mo:02d}-{d:02d}",
                precision=TimePrecision.DAY,
                tz_source=TimeZoneSource.UNKNOWN,
            )
        sec = int(m["S"]) if m["S"] else 0
        hour = int(m["H"])
        if m["ampm"]:
            if not 1 <= hour <= 12:
                return TimeValue(raw=raw or "")
            hour = hour % 12 + (12 if m["ampm"].upper() == "PM" else 0)
        try:
            dt = datetime(y, mo, d, hour, int(m["M"]), sec)
        except ValueError:
            return TimeValue(raw=raw or "")
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
    if not _EMAIL_DATE.fullmatch(text):
        reordered = _reorder(text)
        if reordered and reordered != text:
            return parse_time(reordered, default_offset).model_copy(update={"raw": raw or ""})
        return TimeValue(raw=raw or "")
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
