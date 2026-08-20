"""Composer (A7): Tool 결과를 근거 안에서 설명하는 초안을 만든다.

LLM은 문장을 구성할 뿐 숫자를 계산하지 않는다 — 모든 수치는
tool_result.calculations에서 그대로 가져온다 (문서 9장 Failsafe).
"""

from dataclasses import dataclass, field

from app.agent.hcx_client import HCXClient
from app.agent.router import Intent
from app.agent.tools import ToolResult
from app.api.schemas import CalculationResult, Citation, ComparisonResult, ComparisonRow

_SYSTEM_PROMPT = (
    "당신은 은퇴 자금(퇴직연금) 의사결정을 돕는 어시스턴트입니다. "
    "제공된 근거(evidence)와 계산 결과(calculation)만 사용해 답하세요. "
    "제공되지 않은 숫자나 세율을 임의로 만들어내지 마세요. "
    "투자·상품을 단정적으로 추천하지 말고, 비교 정보를 근거와 함께 제시하세요."
)


@dataclass
class Draft:
    message: str
    citations: list[Citation] = field(default_factory=list)
    calculation_results: list[CalculationResult] = field(default_factory=list)
    comparison: ComparisonResult | None = None


class Composer:
    def __init__(self, hcx_client: HCXClient) -> None:
        self._hcx = hcx_client

    def compose(self, question: str, intent: Intent, tool_result: ToolResult) -> Draft:
        evidence_block = "\n".join(f"- ({c.source}) {c.excerpt}" for c in tool_result.evidence) or "(근거 없음)"
        calc_block = (
            "\n".join(f"- {c.label}: {c.value}{c.unit}" for c in tool_result.calculations) or "(계산 결과 없음)"
        )
        user_prompt = (
            f"질문: {question}\n\n[근거]\n{evidence_block}\n\n[계산 결과]\n{calc_block}\n\n"
            "위 근거와 계산 결과만 이용해 답변 문장을 작성하세요."
        )

        message = self._hcx.complete(_SYSTEM_PROMPT, user_prompt)

        comparison = self._build_comparison(intent, tool_result.calculations)

        return Draft(
            message=message,
            citations=tool_result.evidence,
            calculation_results=tool_result.calculations,
            comparison=comparison,
        )

    def _build_comparison(self, intent: Intent, calculations: list[CalculationResult]) -> ComparisonResult | None:
        if intent != "종합" or len(calculations) < 2:
            return None
        rows = [ComparisonRow(label=c.label, values={"value": f"{c.value}{c.unit}"}) for c in calculations]
        return ComparisonResult(
            title="옵션 비교",
            options=[c.rule_id for c in calculations],
            rows=rows,
            note="단정적인 추천이 아닌 참고용 비교입니다.",
        )
