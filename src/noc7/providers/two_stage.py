"""两段式文本提供方：抽事实（可配置多遍取并集）→ 本地核对与裁决 → 成文。"""

from __future__ import annotations

from ..extract.types import Extraction, ExtractionContext
from . import facts, narrative
from .text_config import TextProviderError
from .text_http import OpenAICompatibleTextProvider
from .text_prompt import prepare_evidence


class TwoStageTextProvider(OpenAICompatibleTextProvider):
    prompt_version = f"{facts.PROMPT_VERSION}+{narrative.PROMPT_VERSION}"

    def extract(self, ctx: ExtractionContext) -> Extraction:
        data_class = ctx.bundle.manifest.data_class
        clean_ctx, evidence = prepare_evidence(ctx, compact=True)
        audit = self.audit.begin(clean_ctx, evidence, self.prompt_version) if self.audit else None
        spans = {s.id: s for s in clean_ctx.evidence}
        kept, dropped = [], []
        try:
            for n in range(self.config.fact_passes):
                try:
                    raw = self._post(facts.SYSTEM_PROMPT if n == 0 else facts.RECHECK_PROMPT, evidence, data_class, audit)
                    if audit and n == 0:
                        audit.record(raw_response=raw.decode("utf-8", errors="replace"), outcome="response_received")
                    try:
                        more, bad = facts.check_facts(self._content(raw), spans)
                    except TextProviderError:
                        raise
                    except ValueError:
                        raise TextProviderError("模型事实列表结构不合格，已拒绝。") from None
                except TextProviderError:
                    if n == 0:
                        raise
                    # 补充遍失败不拖累第一遍已核对的事实。
                    dropped.append({"type": None, "reason": f"第 {n + 1} 遍抽取失败，未并入"})
                    continue
                kept = facts.merge_facts(kept, more)
                dropped += bad
            if audit:
                audit.record(facts_kept=kept, facts_dropped=dropped, fact_passes=self.config.fact_passes)
            data = self._decode_parsed(facts.compile_facts(kept, clean_ctx), clean_ctx, audit,
                                       adjudication="local_priority",
                                       extra_original={"facts_dropped": dropped, "not_fault": facts.not_fault(kept)})
        except Exception as exc:
            if audit:
                audit.record(outcome="rejected", error_type=type(exc).__name__)
            raise
        if audit:
            audit.record(outcome="accepted")
        return data.model_copy(update={"narrative": self._write(data, data_class, audit)})

    def _write(self, data: Extraction, data_class, audit):
        """成文失败不影响已核验的要素；报告退回本地拼接的写法。"""
        request = narrative.build_request(data.elements)
        if request is None:
            return None
        try:
            raw = self._post(narrative.INSTRUCTION, request, data_class)
            if audit:
                audit.record(narrative_request=request, narrative_response=raw.decode("utf-8", errors="replace"))
            result = narrative.verify(self._content(raw), data.elements)
        except ValueError:  # 含 TextProviderError
            if audit:
                audit.record(narrative_outcome="failed")
            return None
        if audit:
            audit.record(narrative_outcome="accepted", narrative_replaced=result.replaced)
        return result
