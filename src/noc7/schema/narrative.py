"""成文结果：模型只改写已核验的事实，本地核对后才进入公司格式报告。"""

from pydantic import Field

from .common import CandidateId, Model


class NarrativeLine(Model):
    step_refs: list[CandidateId] = Field(min_length=1, description="这一行概括了哪些处理步骤")
    text: str = Field(min_length=1)
    rewritten: bool = Field(default=True, description="False 表示改写未通过核对，退回步骤原文")


class ReportNarrative(Model):
    """现象、处理过程、原因的成文表述；时间不由模型写，报告层取所引步骤的时间。"""

    phenomenon: str | None = None
    cause: str | None = None
    process: list[NarrativeLine] = Field(default_factory=list)
    prompt_version: str
    replaced: int = Field(default=0, ge=0, description="未通过本地核对而退回原文或丢弃的条数")
