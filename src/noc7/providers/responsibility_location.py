"""责任方和城市级故障点：模型判断语义，本地核验关系、覆盖和来源优先级。"""
from __future__ import annotations

import hashlib
import re

from ..quote_match import match_quote
from ..schema import ElementStatus, IssueCode, SpanRole
from ..schema.relations import BusinessCoverage, ConstraintCheck

NAMES = ("responsible_party", "location")
ROLE_FIELDS = {
    "responsible_party": {"vendor", "handler", "handling_dept"},
    "location": {"a_end", "z_end", "device_location", "device_name", "region", "shelf_slot_port"},
}
PRIORITY = {"rfo": 0, "vendor_feedback": 1, "branch_log": 2}
SOURCE_LABELS = {"rfo": "RFO", "vendor_feedback": "供应商反馈", "branch_log": "分公司处理日志", "system_field": "工单系统字段（兜底）", "unknown": "来源未明"}
PATH_LABELS = {"explicit_responsibility": "明确责任归属", "customer_self_check": "客户自查且未再追问",
               "vendor_onsite_contact": "联络供应商上门", "unicom_onsite_recovery": "联通上门处理后恢复",
               "equipment_ownership": "设备采购归属线索", "role_only": "仅角色", "system_field": "工单系统字段兜底",
               "rfo_cause": "供应商 RFO 所述故障原因", "unknown": "依据未明"}
RFO_CAUSE_NOTE = "原文没有直接写责任方，按供应商 RFO 所述本方网络故障原因推定为供应商，待核实。"
# 工单系统“故障区域”字段到责任方的映射；映射不出的（如“局方检测正常自恢”）不兜底。
AREA_FIELD = "fault_area"
AREA_PARTIES = (("运营商", "供应商"), ("用户", "客户"))
FALLBACK_TIER = "system_field"
# 两段式按层兜底时，来源不属于 RFO、供应商反馈、分公司处理日志的（NOC 记录、工单字段、其他）排在最后一层，
# 仍在故障区域字段兜底之前。
LOW_TIER = "unknown"
CUSTOMER_SPEAKER = "客户"
NEGATED_NOTE = "原文另有否定这一方故障的说法，怀疑不采用。"
LOW_NOTE = "来源层级最低（不属于 RFO、供应商反馈或分公司处理日志），待核实。"


def rank_of(tier):
    return PRIORITY.get(tier, len(PRIORITY))


# 地点先取城市；没有可采用的城市时才取省、州一级（业务口径 2026-11-12）。
_ADMIN_CN = re.compile(r"(?:省|自治区|自治州)$")
_ADMIN_EN = re.compile(r"\b(?:province|state|region|prefecture|oblast|governorate)\b", re.I)
_ADMIN_AFTER = re.compile(r"\s*(?:省|自治区|州|(?:province|state|region|prefecture|oblast|governorate)\b)", re.I)
# “奇瓦瓦州（Chihuahua）”：括号里的外文名跟在省、州名后面，也是省、州。
_ADMIN_BEFORE = re.compile(r"(?:省|自治区|州)\s*[（(]\s*$")
_PAREN_TAIL = re.compile(r"\s*[（(][^（()）]*[）)]\s*$")


def city_name(city, quote=""):
    """规整地点名，结果仍是原文的一部分。

    城市去掉“县”“市”后缀和美国州的两字母简写（“NEW BRUNSWICK, NJ”）；
    省、州保留原文里紧跟的“省／州／Province”等字样（“谅山”→“谅山省”），读者能看出只到省一级。
    """
    city = re.sub(r",\s*[A-Z]{2}$", "", city.strip())
    if admin_area(city, quote):
        if not admin_area(city):
            m = re.search(re.escape(city) + r"(?:\s*(?:province|state|region|prefecture|oblast|governorate)\b|省|自治区|州)",
                          quote or "", re.I)
            if m:
                return m.group(0)
        return city
    if len(city) >= 3 and city[-1] in "县市":
        city = city[:-1]
    return city


def admin_area(city, quote=""):
    """城市名其实是省、州一级行政区：名字本身带“省／州／Province”等，或原文里有一处明说它是省、州（紧跟着这类词，或是省州名后括号里的外文名）。同名的省和城市分不清时按省、州算。"""
    base = _PAREN_TAIL.sub("", city or "").strip()
    if not base:
        return False
    if _ADMIN_CN.search(base) or (base.endswith("州") and len(base) >= 3) or _ADMIN_EN.search(base):
        return True
    return any(_ADMIN_AFTER.match(quote[m.end():]) or _ADMIN_BEFORE.search(quote[:m.start()])
               for m in re.finditer(re.escape(base), quote or "", re.I))


_PLACE_SUFFIX = re.compile(r"(?:省|自治区|州|县|市|\b(?:province|state|region|prefecture|oblast|governorate|city)\b)$", re.I)
_COUNTRY_PREFIX = re.compile(r"^(?:中国|越南|老挝|泰国|缅甸|柬埔寨|马来西亚|新加坡|印度尼西亚|菲律宾|日本|韩国|俄罗斯|蒙古|"
                             r"哈萨克斯坦|美国|加拿大|墨西哥|巴西|英国|法国|德国|荷兰|意大利|西班牙|澳大利亚|印度|巴基斯坦)")


def _place_core(value):
    core = re.sub(r"[\s,，.、·'’\-]+", " ", (value or "").strip()).strip()
    core = _COUNTRY_PREFIX.sub("", core).strip()
    while _PLACE_SUFFIX.search(core):
        core = _PLACE_SUFFIX.sub("", core).strip()
    return core.lower()


def _edits(a, b, limit=1):
    """编辑距离，超过 limit 就提前返回 limit + 1。"""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def same_place(a, b):
    """同一地点的不同写法：去掉国名前缀和省／县／Province 等后缀后相同、一方包含另一方，或外文名（6 个字母以上）只差一个字母。"""
    x, y = _place_core(a), _place_core(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = sorted((x, y), key=len)
    if short.isascii():
        if re.search(r"\b" + re.escape(short) + r"\b", long_):
            return True
        return len(short) >= 6 and _edits(x, y) <= 1
    return len(short) >= 2 and short in long_


def _coarse_level(candidate):
    """按层兜底时城市、省州之后的两层：线路段（两端地名）和国家。"""
    g, r = candidate.granularity, candidate.relation
    if g == "segment" and r.city_scope == "cross_city" and r.city.endswith("段") and r.city.count("–") == 1:
        return "segment"
    if g == "country" and r.city_scope == "unknown":
        return "country"
    return None


def _place_parts(candidate):
    """要在引文里逐一核对的地名：线路段是两端，其余是取值本身。"""
    if _coarse_level(candidate) == "segment":
        return candidate.relation.city[:-1].split("–")
    return [candidate.relation.city]


def place_level(candidate):
    """地点层级：0 城市，1 省州，2 线路段，3 国家。"""
    coarse = _coarse_level(candidate)
    if coarse:
        return 2 if coarse == "segment" else 3
    return 1 if admin_area(candidate.relation.city, candidate.relation.city_quote.quote) else 0


LEVEL_NOTES = {1: "原文没有具体城市，只到省、州一级。", 2: "原文只到线路段，未定位到单一城市。", 3: "原文只到国家。"}
LEVEL_DROPPED = {1: "已有可采用的城市，省、州一级不采用。", 2: "已有更具体的地点，线路段不采用。", 3: "已有更具体的地点，国家不采用。"}


def _segment_ends(value):
    if isinstance(value, str) and value.endswith("段") and value.count("–") == 1:
        return value[:-1].split("–")
    return None


def same_value(a, b, name):
    if a == b:
        return True
    if name != "location":
        return False
    x, y = _segment_ends(a), _segment_ends(b)
    if x or y:
        # 线路段两端相同（不论先后）才算同一段。
        return bool(x and y) and ((same_place(x[0], y[0]) and same_place(x[1], y[1]))
                                  or (same_place(x[0], y[1]) and same_place(x[1], y[0])))
    return same_place(a, b)


def area_party(text):
    return next((party for word, party in AREA_PARTIES if word in (text or "")), None)


def _area_fallback(el, spans):
    for c in el.candidates:
        r = c.relation
        span = spans.get(c.evidence_refs[0]) if len(c.evidence_refs) == 1 else None
        if (r and r.source_tier == FALLBACK_TIER and r.decision_path == FALLBACK_TIER and span is not None
                and span.locator.type == "field" and span.locator.field_key == AREA_FIELD
                and area_party(span.text) == r.category):
            return c, span
    return None, None


ANCHORS = ("responsibility_quote", "source_quote", "procurement_quote", "self_check", "vendor_contact", "unicom_onsite", "service_recovered", "city_quote")


def relation_quotes(relation):
    if relation:
        yield from relation.context
        for key in ANCHORS:
            quote = getattr(relation, key, None)
            if quote:
                yield quote


def _hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build_coverage(ctx):
    """只声明本包原始处理记录的覆盖，不声明源系统绝对完整。"""
    # 只有标点的占位记录（如“-”）没有可核对的内容，不计入覆盖范围。
    entries = [e for e in ctx.bundle.process_log.entries
               if e.entry_kind != "ai_summary" and any(ch.isalnum() for ch in e.content)]
    hashes = {str(e.seq): _hash(e.content) for e in entries}
    covered = {}
    for span in ctx.evidence:
        if span.locator.type == "log_entry" and reliable(span):
            seq = str(span.locator.seq)
            if hashes.get(seq) == _hash(span.text):
                covered[seq] = span.id
    related = {mid for e in entries for mid in [*e.emails, *e.attachments]}
    available = {s.material_id for s in ctx.evidence if reliable(s)}
    return BusinessCoverage(detail_status=ctx.bundle.ticket.status.detail_status,
                            log_hashes=hashes, covered_logs=covered,
                            related_materials_complete=related <= available)


def reliable(span):
    return (not span.needs_review and (span.quality is None or span.quality >= 0.7)
            and span.role not in {SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED})


def coverage_complete(coverage, spans):
    if not coverage or coverage.detail_status != "已结单" or not coverage.log_hashes or not coverage.related_materials_complete:
        return False
    if set(coverage.log_hashes) != set(coverage.covered_logs):
        return False
    for seq, ref in coverage.covered_logs.items():
        span = spans.get(ref)
        if (not span or not reliable(span) or span.locator.type != "log_entry"
            or str(span.locator.seq) != seq or _hash(span.text) != coverage.log_hashes[seq]):
            return False
    return True


def formal_value(candidate, name):
    if candidate.relation:
        return candidate.relation.category if name == "responsible_party" else candidate.relation.city
    return candidate.party if name == "responsible_party" else candidate.description


def pending_reason(candidate, name, spans, coverage=None, layered=False):
    """layered：两段式按“一层层兜底”取值，怀疑的责任归属也可采用（排在明确的之后）。"""
    r = candidate.relation
    if r is None:
        return "缺少完整结构化业务关系，保留待核对。"
    suspected = layered and name == "responsible_party" and r.modality == "suspected"
    if not r.current_event or (r.modality != "asserted" and not suspected):
        return "不是本次事件的明确断言。"
    if suspected and r.speaker == CUSTOMER_SPEAKER:
        return "客户（报障方）的猜测不算怀疑归属。"
    if r.source_tier == FALLBACK_TIER:
        return "工单系统字段只作兜底，不参与来源比较。"
    if r.source_tier not in PRIORITY and not (layered and r.source_tier == LOW_TIER):
        return "来源不属于 RFO、供应商反馈或分公司处理日志。"
    if r.source_quote is None:
        return "缺少来源层级的直接引文依据。"
    quotes = list(relation_quotes(r))
    for q in quotes:
        span = spans.get(q.evidence_id)
        if not span or match_quote(q.quote, span.text).status == "mismatch":
            return "业务关系引文不匹配或缺少来源，待核对。"
        if not reliable(span):
            return "业务关系依据仅为引用、摘要、签名或低质量材料。"
    support = [spans[ref] for ref in dict.fromkeys([*candidate.evidence_refs, *(q.evidence_id for q in quotes)]) if ref in spans]
    if support and all(span.locator.type == "field" and span.locator.field_key in ROLE_FIELDS[name] for span in support):
        return "依据仅为角色或端点／告警位置字段，保留候选待核对，不影响其他要素。"
    raw = candidate.party if name == "responsible_party" else candidate.description
    if not any(ref in spans and reliable(spans[ref]) and match_quote(raw, spans[ref].text).status != "mismatch"
               for ref in candidate.evidence_refs):
        return "候选原文缺少可靠直接来源。"
    if not any(match_quote(r.statement, q.quote).status != "mismatch" for q in r.context):
        return "关系上下文没有包含本条原文断言。"
    if match_quote(raw, r.statement).status == "mismatch":
        return "原文断言未包含候选摘录。"
    if name == "location":
        if candidate.role != "located_fault_point" or not r.located:
            return "不是已定位故障点，端点、告警位置和测试节点不能采用。"
        coarse = layered and _coarse_level(candidate) is not None
        if r.city_scope != "single_city" and not coarse:
            return "城市范围未明确为 single_city，跨城或范围未知只能留候选。"
        if candidate.granularity in {None, "country"} and not coarse:
            return "地点仅到国家、跨城段落或粒度未明，不能推测城市。"
        if not r.city or not r.city.strip() or not r.city_quote or not all(
                match_quote(part, r.city_quote.quote).status != "mismatch" for part in _place_parts(candidate)):
            return "没有可核验的明确城市归属。"
    else:
        if r.category not in {"客户", "供应商", "联通"}:
            return "其他主体、共同责任或分类未明，只保留候选。"
        if candidate.basis == "claimed":
            return "责任仅为某方主张，保留候选待核对。"
        if candidate.basis == "inferred_from_role":
            return "仅凭供应商、处理部门等角色不能定责。"
        path = r.decision_path
        if r.category == "客户" and (r.vendor_contact or r.unicom_onsite):
            return "客户侧设备仍有其他提供方上门处理线索，不能据设备故障直接采用客户责任。"
        if path == "explicit_responsibility":
            if candidate.basis != "formal_determination" or r.customer_device_fault is not False:
                return "明确归属须为 formal_determination 且 customer_device_fault is False；客户设备或前提未明须走完整上下文路径。"
            if r.self_check or r.vendor_contact or r.unicom_onsite:
                return "明确归属不能绕过自查或上门上下文路径。"
            if not r.responsibility_quote:
                return "明确归属路径缺少专门责任依据，不能把供应商角色或客户侧现象当成责任。"
            if not any(match_quote(r.responsibility_quote.quote, q.quote).status != "mismatch" for q in r.context):
                return "责任依据没有包含在本条关系上下文中。"
            return None
        if path == "rfo_cause":
            # 分层模式才有：供应商 RFO 写明了具体故障原因、但没写责任方，推定为供应商（排在明确与怀疑归属之后）。
            if not layered:
                return "按 RFO 故障原因推定责任只用于分层兜底。"
            if r.category != "供应商" or r.source_tier != "rfo" or not r.responsibility_quote:
                return "RFO 原因推定须为供应商且来源为 RFO。"
            return None
        if not r.customer_device_fault:
            return "上下文路径缺少客户侧设备故障前提。"
        if path == "customer_self_check":
            if r.category != "客户" or not r.self_check or r.no_followup is not True:
                return "客户责任路径缺少自查或未再追问关系。"
            if r.vendor_contact or r.unicom_onsite or r.procurement in {"供应商", "联通"}:
                return "仍有其他提供方或上门处理线索，不能采用客户自查路径。"
            if not coverage_complete(coverage, spans):
                return "输入未覆盖完整已结单处理记录及关联材料，不能判断未再追问。"
        elif path == "vendor_onsite_contact":
            if r.unicom_onsite:
                return "供应商与联通上门线索同时存在，责任待核对。"
            if r.category != "供应商" or not r.vendor_contact:
                return "供应商责任路径缺少联络供应商上门依据。"
        elif path == "unicom_onsite_recovery":
            if r.vendor_contact:
                return "供应商与联通上门线索同时存在，责任待核对。"
            if r.category != "联通" or not r.unicom_onsite or not r.service_recovered:
                return "联通责任路径缺少上门处理与业务恢复依据。"
        else:
            return "采购归属或角色本身不能替代明确责任或业务上下文路径。"
        if r.procurement != "unknown" and not r.procurement_quote:
            return "采购归属没有原文依据。"
    return None


def grounded_assertion(candidate, name, spans):
    """反证不必能成为正面结论，但原断言、上下文和出处都必须可靠。"""
    r = candidate.relation
    if not r or not r.source_quote:
        return False
    quotes = list(relation_quotes(r))
    if not all(q.evidence_id in spans and reliable(spans[q.evidence_id])
               and match_quote(q.quote, spans[q.evidence_id].text).status != "mismatch" for q in quotes):
        return False
    raw = candidate.party if name == "responsible_party" else candidate.description
    return (bool(candidate.evidence_refs)
            and all(ref in spans for ref in candidate.evidence_refs)
            and any(reliable(spans[ref]) and match_quote(raw, spans[ref].text).status != "mismatch"
                    for ref in candidate.evidence_refs)
            and match_quote(raw, r.statement).status != "mismatch"
            and any(match_quote(r.statement, q.quote).status != "mismatch" for q in r.context))


def evaluate(elements, spans, coverage, suggestions=(), layered=False):
    """纯函数，首次分析、完整证据校验及保存结果再加载共同调用。"""
    updates, checks = {}, []
    for name in NAMES:
        el = getattr(elements, name)
        eligible = []
        known = {c.id for c in el.candidates}
        for c in el.candidates:
            reason = pending_reason(c, name, spans, coverage, layered)
            if reason is None and any(q["evidence_id"] in c.evidence_refs
                                      and (q["evidence_id"] not in spans
                                           or match_quote(q["quote"], spans[q["evidence_id"]].text).status == "mismatch")
                                      for s in suggestions if s.element == name for q in s.quotes):
                reason = "该候选的显式业务引文不匹配，保留待核对。"
            if (reason is None and name == "responsible_party" and c.relation.category == "客户"
                and any(other.relation and other.id != c.id and other.relation.current_event
                        and (other.relation.event_id, other.relation.scope) == (c.relation.event_id, c.relation.scope)
                        and any(q and q.evidence_id in spans and reliable(spans[q.evidence_id])
                                and match_quote(q.quote, spans[q.evidence_id].text).status != "mismatch"
                                for q in (other.relation.vendor_contact, other.relation.unicom_onsite))
                        for other in el.candidates)):
                reason = "其他候选仍有同事件的提供方上门线索，不能据客户侧设备故障采用客户责任。"
            if c.relation and any(ref not in known or ref == c.id for ref in c.relation.contradicts):
                reason = "矛盾关系指向缺失、歧义或自身候选。"
            checks.append(ConstraintCheck(element=name, candidate_id=c.id,
                outcome="pending" if reason else "eligible", reason=reason or "结构及引文核验通过；业务语义未经人工审核。",
                evidence_refs=c.evidence_refs))
            if reason is None:
                eligible.append(c)
        suspected = False
        if name == "responsible_party" and layered:
            # 怀疑某一方、而原文另有可靠的说法否定这一方有故障（如“供应商反馈网内无作业”），怀疑不采用。
            denied = {formal_value(o, name) for o in el.candidates
                      if o.relation and o.relation.modality == "negated" and o.relation.current_event
                      and grounded_assertion(o, name, spans)}
            vetoed = {c.id for c in eligible if (c.relation.modality == "suspected" or c.relation.decision_path == "rfo_cause")
                      and formal_value(c, name) in denied}
            if vetoed:
                checks = [ConstraintCheck(element=name, candidate_id=k.candidate_id, outcome="pending",
                                          reason=NEGATED_NOTE, evidence_refs=k.evidence_refs)
                          if k.element == name and k.candidate_id in vetoed else k for k in checks]
                eligible = [c for c in eligible if c.id not in vetoed]
        if name == "responsible_party":
            # 有明确的责任归属就不取怀疑的；没有明确的才取怀疑的，再没有才用故障区域字段兜底。
            # 层次：明确的责任归属 → 按供应商 RFO 故障原因推定 → 怀疑的责任归属 → 故障区域字段。
            asserted = [c for c in eligible if c.relation.modality == "asserted" and c.relation.decision_path != "rfo_cause"]
            inferred = [c for c in eligible if c.relation.decision_path == "rfo_cause"]
            keep = asserted or inferred
            if keep and len(keep) < len(eligible):
                dropped = {c.id for c in eligible if c not in keep}
                reason = "已有明确的责任归属，推定或怀疑的不采用。" if asserted else "已有按 RFO 故障原因的推定，怀疑的不采用。"
                checks = [ConstraintCheck(element=name, candidate_id=k.candidate_id, outcome="pending",
                                          reason=reason, evidence_refs=k.evidence_refs)
                          if k.element == name and k.candidate_id in dropped else k for k in checks]
            suspected = bool(eligible) and not keep
            eligible = keep or eligible
        level = 0
        if name == "location" and eligible:
            # 城市 → 省、州 → 线路段 → 国家，取最具体的一层，不论各来自哪一级来源。
            levels = {c.id: place_level(c) for c in eligible}
            level = min(levels.values())
            dropped = {k: v for k, v in levels.items() if v > level}
            checks = [ConstraintCheck(element=name, candidate_id=k.candidate_id, outcome="pending",
                                      reason=LEVEL_DROPPED[dropped[k.candidate_id]], evidence_refs=k.evidence_refs)
                      if k.element == name and k.candidate_id in dropped else k for k in checks]
            eligible = [c for c in eligible if c.id not in dropped]
        update = dict(status=ElementStatus.UNKNOWN, value=None, selected=None, evidence_refs=[], note="依据不足，保留候选及原始回答待核对。" if el.candidates else None)
        if eligible:
            ranks = sorted({rank_of(c.relation.source_tier) for c in eligible})
            rank = ranks[0]
            top = [c for c in eligible if rank_of(c.relation.source_tier) == rank]
            opponents = _opponents(el, top, name, spans, layered)
            different = _differs(top, name, layered)
            fallback_note = ""
            if (different or opponents) and layered:
                # 按层兜底：最高层来源冲突时，退到下一层来源里结论一致的；都不行再取同层被摘到最多的，标“有冲突，待核实”。
                clash = list(dict.fromkeys(c.id for c in [*top, *opponents]))
                for lower_rank in ranks[1:]:
                    group = [c for c in eligible if rank_of(c.relation.source_tier) == lower_rank]
                    if not _differs(group, name, layered) and not _opponents(el, group, name, spans, layered):
                        rank, top = lower_rank, group
                        fallback_note = "较高层来源结论冲突（" + "、".join(clash) + "），取下一层来源，待核实。"
                        break
                else:
                    counts = [sum(same_value(formal_value(o, name), formal_value(c, name), name) for o in top) for c in top]
                    best = max(counts)
                    top = [next(c for c, n in zip(top, counts) if n == best)]
                    fallback_note = "同层来源结论冲突（" + "、".join(clash) + "），取被摘到最多、原文先出现的一条，待核实。"
                checks.append(ConstraintCheck(element=name, outcome="conflict", code=IssueCode.SEMANTIC_ASSERTIONS_CONFLICT,
                    reason=fallback_note, evidence_refs=list(dict.fromkeys(r for c in [*top, *opponents] for r in c.evidence_refs))))
                different, opponents = False, []
            opposing = bool(opponents)
            if different or opposing:
                update.update(status=ElementStatus.CONFLICTED, note="最高有效来源同层结论无法消解，正式留空。")
                checks.append(ConstraintCheck(element=name, outcome="conflict", code=IssueCode.SEMANTIC_ASSERTIONS_CONFLICT,
                    reason=update['note'], evidence_refs=list(dict.fromkeys(r for c in [*top, *opponents] for r in c.evidence_refs))))
            else:
                chosen = _fullest(top, name) if layered else top[0]
                variants = [v for v in dict.fromkeys(formal_value(c, name) for c in top) if v != formal_value(chosen, name)]
                refs = list(dict.fromkeys([*chosen.evidence_refs, *(q.evidence_id for q in relation_quotes(chosen.relation))]))
                lower = [c for c in el.candidates if c.relation
                         and (c.relation.source_tier in PRIORITY or (layered and c.relation.source_tier == LOW_TIER))
                         and rank_of(c.relation.source_tier) > rank
                         and (not same_value(formal_value(c, name), formal_value(chosen, name), name)
                              or c.id in chosen.relation.contradicts
                              or chosen.id in c.relation.contradicts)]
                note = SOURCE_LABELS[chosen.relation.source_tier] + "；有记录，未经人工审核。"
                if chosen.relation.source_tier == LOW_TIER:
                    note += LOW_NOTE
                if level:
                    note += LEVEL_NOTES[level]
                if suspected:
                    note += "原文仅为怀疑，待确认。"
                if variants:
                    note += "同一地点另有写法：" + "、".join(variants) + "。"
                note += fallback_note
                if name == "responsible_party":
                    note += "路径：" + PATH_LABELS[chosen.relation.decision_path] + "。"
                    if chosen.relation.decision_path == "rfo_cause":
                        note += RFO_CAUSE_NOTE
                    if chosen.relation.third_party:
                        note += "原文写明由第三方原因造成，按线路所属方记责。"
                    if chosen.relation.decision_path == "customer_self_check":
                        note += "未再追问仅指本次提供的完整已结单处理记录。"
                if lower:
                    note += "低优先级差异保留待核对：" + "、".join(c.id for c in lower) + "。"
                    checks.append(ConstraintCheck(element=name, candidate_id=chosen.id, outcome="downgraded",
                        reason="按来源优先级采用；" + note, evidence_refs=refs))
                update.update(status=ElementStatus.DOCUMENTED, value=formal_value(chosen, name),
                              selected=chosen.id, evidence_refs=refs, note=note)
        if name == "responsible_party":
            fallback, span = _area_fallback(el, spans)
            label = f"工单系统故障区域字段“{span.text.strip()}”" if fallback else ""
            if fallback and update["status"] == ElementStatus.UNKNOWN:
                update.update(status=ElementStatus.DOCUMENTED, value=fallback.relation.category, selected=fallback.id,
                              evidence_refs=list(fallback.evidence_refs),
                              note=f"兜底，待核实：原文没有可采用的责任依据，取自{label}。")
            elif fallback and update["status"] == ElementStatus.DOCUMENTED and update["value"] != fallback.relation.category:
                update["note"] += f"与{label}不一致，待核实。"
        updates[name] = el.model_copy(update=update)
    return updates, checks


def _opponents(el, top, name, spans, layered):
    return [b for b in el.candidates if any(
        b.id != a.id and b.relation
        and b.relation.source_tier == a.relation.source_tier
        and (b.relation.event_id, b.relation.scope) == (a.relation.event_id, a.relation.scope)
        # 按层兜底时否定说法只用来排除怀疑，不把明确结论打成冲突。
        and b.relation.current_event and b.relation.modality in ({"asserted"} if layered else {"asserted", "negated"})
        and grounded_assertion(b, name, spans)
        and (b.id in a.relation.contradicts or a.id in b.relation.contradicts
             or (b.relation.modality == "negated" and formal_value(b, name) == formal_value(a, name)))
        for a in top)]


def _differs(group, name, layered):
    """同组结论是否不一致；按层兜底时，同一地点的不同写法算一致。"""
    values = [formal_value(c, name) for c in group]
    if not layered:
        return len(set(values)) > 1
    return any(not same_value(a, b, name) for i, a in enumerate(values) for b in values[i + 1:])


def _fullest(group, name):
    """同一结论的几种写法里取被摘到最多的，次数一样取更完整（更长）的，再一样取原文先出现的。"""
    values = [formal_value(c, name) for c in group]
    return max(group, key=lambda c: (values.count(formal_value(c, name)), len(formal_value(c, name) or ""),
                                     -group.index(c)))


def apply_constraints(ctx, data):
    assessment = data.semantic_assessment
    if not assessment or not any(n in assessment.original for n in NAMES):
        return data  # 规则提供方和没有新关系的旧保存结果不重解释
    updates, checks = evaluate(data.elements, {s.id: s for s in ctx.evidence}, assessment.business_coverage, data.suggestions,
                               layered=assessment.adjudication == "local_priority")
    kept = [c for c in assessment.checks if c.element not in NAMES]
    return data.model_copy(update={"elements": data.elements.model_copy(update=updates),
                                  "semantic_assessment": assessment.model_copy(update={"checks": [*kept, *checks]})})


def validate_saved(elements, spans, assessment, suggestions=()):
    if not assessment or not any(n in assessment.original for n in NAMES):
        if any(c.relation is not None for name in NAMES for c in getattr(elements, name).candidates):
            raise ValueError("新增业务关系缺少本地原答审计，不能伪装成旧结果")
        return
    updates, _ = evaluate(elements, spans, assessment.business_coverage, suggestions,
                          layered=assessment.adjudication == "local_priority")
    for name in NAMES:
        actual, expected = getattr(elements, name), updates[name]
        if any(getattr(actual, k) != getattr(expected, k) for k in ("status", "value", "selected", "evidence_refs", "note")):
            raise ValueError("正式责任方或地点未遵守结构化业务约束")
