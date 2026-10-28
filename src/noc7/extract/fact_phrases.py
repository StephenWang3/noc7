"""有限的明确归因和 RFO 定位写法；返回原文子串，不补主体或地名。"""

import re


def responsibility_claims(text: str) -> list[str]:
    claims = []
    for match in re.finditer(r"客户(?:侧)?原因|责任归属[：:]\s*[^。；;\n，,]+", text):
        left = re.split(r"[。；;\n，,]", text[:match.start()])[-1]
        right = re.split(r"[。；;\n，,]", text[match.end():])[0]
        if re.search(r"非|不|未|疑似|可能|怀疑|排查|核查|确认是否|是否|假设|若|如果", left):
            continue
        if re.search(r"排除|否认|未确认|待确认|待核实|待查|尚待|不成立|可能", right):
            continue
        value = match.group().strip()
        # 标签值本身也可能是占位、否定或疑似，不能升级为归因记载。
        if re.search(r"未知|待定|待查|待确认|未定|无责任|无关|疑似|可能|不是|并非", value):
            continue
        claims.append(value)
    return claims


def rfo_fault_points(text: str) -> list[str]:
    # 只看当前正文，转发／引用的旧 RFO 不用作本次定位。
    current = re.split(r"(?:\n|<br\s*/?>)\s*(?:From:|发件人[：:]|[- ]*Original Message)", text, maxsplit=1, flags=re.I)[0]
    points = []
    for match in re.finditer(r"\bLocation\s*:\s*(?P<point>Between\s+[^\n\r<>;]+)", current, re.I):
        point = match.group("point").strip().rstrip(".")
        # 故障段必须有两个命名位置及地区；笼统的中心设备到客户端不满足。
        if not re.fullmatch(r"Between\s+\S[^,]*?\s+and\s+\S[^,]*,\s*\S.+", point, re.I):
            continue
        section = current[max(0, match.start() - 1800):match.end() + 250]
        reason = re.search(r"Reason\s+for\s+(?:Failure|Outage)\s*:\s*([^\n\r<>]+)", section, re.I)
        if not reason or not re.search(r"fiber|fibre|cut|break|fault|failure|damage", reason.group(1), re.I):
            continue
        if re.search(r"\b(?:no|not|without|unknown|possible|suspected)\b|ruled out", reason.group(1), re.I):
            continue
        if re.search(r"\b(?:unknown|pending|tbd|undetermined|suspect\w*|possible|locating|measurements|await\w*)\b|to be (?:confirmed|determined)|not (?:yet )?(?:confirmed|located)|no (?:fault|cut|failure)", section, re.I):
            continue
        if re.search(r"\b(?:client|customer|endpoint|ping|test|our|your)\b|\b(?:\d{1,3}\.){3}\d{1,3}\b", point, re.I):
            continue
        points.append(point)
    return points
