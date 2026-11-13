"""两段式离线重放：用诊断记录里存下的模型回复重跑本地核对与裁决，不联网、不需要密钥。

两种模式：
- responses：记录里有每一遍事实抽取的原始回复（fact_responses），从原始回复开始重放，
  逐条核对、多遍合并、裁决、成文全部重走；
- facts：较早的记录只有第一遍原始回复和合并后的事实（facts_kept），从已核对的事实开始重放；
  第一遍原始回复按当前规则重新逐条核对，原先丢弃、现在能通过的事实并入（如引文匹配放宽后），
  第二遍以后的回复没存，那部分不重走。

成文一律使用记录里的成文回复，再按当前要素重新核验；要素变了对不上时退回本地拼接写法。
提示词改动不能靠重放验证，那时须真实调用模型。
"""

from __future__ import annotations

from .text_config import TextProviderError
from .text_prompt import prepare_evidence
from .text_replay import evidence_digest
from .two_stage import TwoStageTextProvider
from . import facts, narrative


class TwoStageReplayProvider(TwoStageTextProvider):
    def __init__(self, config, record: dict):
        super().__init__(config)
        self.record = record
        responses = record.get("fact_responses")
        self.mode = "responses" if isinstance(responses, list) and responses else "facts"
        if self.mode == "facts" and not isinstance(record.get("facts_kept"), list):
            raise TextProviderError("诊断记录里既没有逐遍回复也没有已核对的事实，不能重放。")
        self.name = f"replay:{self.mode}:{config.name}:{config.model}"
        # 记录时的提示词版本与当前不同：重放出的结论不代表当前提示词下模型的行为。
        self.prompt_changed = record.get("prompt_version") != self.prompt_version
        self._fact_responses = list(responses or [])

    def preflight(self, data_class):
        return None  # 不联网、不读密钥

    def extract(self, ctx):
        clean_ctx, _ = prepare_evidence(ctx, compact=True)
        if self.record.get("evidence_sha256") != evidence_digest(clean_ctx):
            raise TextProviderError("证据摘要与诊断记录不一致（工单材料或证据整理方式变了），不能重放。")
        return super().extract(ctx)

    def _collect_facts(self, evidence, data_class, spans, audit):
        if self.mode == "responses":
            return super()._collect_facts(evidence, data_class, spans, audit)
        kept = list(self.record["facts_kept"])
        dropped = list(self.record.get("facts_dropped") or [])
        first = self.record.get("raw_response")
        if isinstance(first, str):
            try:
                again, _ = facts.check_facts(self._content(first.encode("utf-8")), spans)
            except (TextProviderError, ValueError):
                again = []
            merged = facts.merge_facts(kept, again)
            for fact in merged[len(kept):]:  # 现在能通过的：从原丢弃记录里去掉一条同类的引文不匹配
                hit = next((d for d in dropped if d.get("type") == fact["type"]
                            and d.get("reason") == "引文不在证据原文中"), None)
                if hit:
                    dropped.remove(hit)
            kept = merged
        return kept, dropped

    def _post(self, system, user, data_class, audit=None):
        if system in (facts.SYSTEM_PROMPT, facts.RECHECK_PROMPT):
            if not self._fact_responses:
                raise TextProviderError("诊断记录里没有这一遍的事实回复。")
            raw = self._fact_responses.pop(0)
        elif system == narrative.INSTRUCTION:
            raw = self.record.get("narrative_response")
        else:
            raise TextProviderError("重放不支持这一类请求。")
        if not isinstance(raw, str):
            raise TextProviderError("诊断记录里这一次请求没有回复（原运行中失败）。")
        return raw.encode("utf-8")
