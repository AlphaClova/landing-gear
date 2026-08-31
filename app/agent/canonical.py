"""Grounded canonical facts and generic false-premise contradiction checks.

User premises are compared to evidence-backed canonical claims. DB/DC wording is
not special-cased at the answer layer; only the grounded fact table is domain-specific.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.api.schemas import Citation
from app.core.query_normalization import has_alias, is_tax_deduction_question


_AFFIRM_OPENING = ("네", "예", "맞습니다", "맞아요", "그렇습니다", "그렇죠", "맞죠")


@dataclass(frozen=True)
class CanonicalClaim:
    key: str
    value: object
    text: str
    evidence_id: str


@dataclass(frozen=True)
class UserClaim:
    key: str
    value: object


@dataclass(frozen=True)
class FalsePremiseHit:
    user_claim: UserClaim
    canonical: CanonicalClaim
    correction: str
    evidence_id: str


def grounded_canonical_claims(evidence: list[Citation], products: list[dict] | None = None) -> list[CanonicalClaim]:
    claims: list[CanonicalClaim] = []
    doc10 = next((item for item in evidence if item.document_id == "doc10"), None)
    if doc10:
        claims.extend(
            [
                CanonicalClaim(
                    "DC.benefit_predefined",
                    False,
                    "확정기여형(DC)은 퇴직급여가 미리 확정되지 않고 운용 수익률에 따라 최종 퇴직급여가 달라집니다.",
                    doc10.id,
                ),
                CanonicalClaim(
                    "DC.operator",
                    "employee",
                    "확정기여형(DC)은 회사가 매년 일정 금액을 근로자의 계좌에 입금하고 근로자가 직접 운용합니다.",
                    doc10.id,
                ),
                CanonicalClaim(
                    "DC.final_depends_on_return",
                    True,
                    "확정기여형(DC)의 최종 퇴직급여는 운용 수익률에 따라 달라집니다.",
                    doc10.id,
                ),
                CanonicalClaim(
                    "DB.benefit_predefined",
                    True,
                    "확정급여형(DB)은 근로자가 받을 퇴직급여가 사전에 확정됩니다.",
                    doc10.id,
                ),
                CanonicalClaim(
                    "DB.operator",
                    "company",
                    "확정급여형(DB)은 회사가 적립금을 운용합니다.",
                    doc10.id,
                ),
                CanonicalClaim(
                    "DB.final_depends_on_return",
                    False,
                    "확정급여형(DB)은 운용 수익률이 낮아도 사전 확정된 퇴직급여가 줄어들지 않습니다.",
                    doc10.id,
                ),
            ]
        )
    tax_doc = next((item for item in evidence if item.document_id in {"doc41", "doc55"} and ("600만원" in item.excerpt or "900만원" in item.excerpt)), None)
    if tax_doc:
        claims.extend(
            [
                CanonicalClaim(
                    "TAX_CREDIT.unlimited",
                    False,
                    "연금저축 세액공제 대상 납입한도는 연 600만원이고, IRP를 포함한 연금계좌 합산 한도는 연 900만원입니다.",
                    tax_doc.id,
                ),
                CanonicalClaim(
                    "TAX_CREDIT.contribution_equals_tax_cut",
                    False,
                    "세액공제 대상 납입액과 실제 줄어드는 세금은 같은 뜻이 아닙니다.",
                    tax_doc.id,
                ),
            ]
        )
    risk = next((item for item in evidence if "6등급(매우 낮은 위험)" in item.excerpt), None)
    if risk:
        claims.append(
            CanonicalClaim(
                "RISK.grade_6_highest",
                False,
                "제공된 Product Fact의 위험등급 체계에서 6등급은 매우 낮은 위험입니다.",
                risk.id,
            )
        )
    protection = next((item for item in evidence if "예금자보호" in item.excerpt), None)
    if protection and any("집합투자" in item.excerpt or "예금자보호 대상이 아닙니다" in item.excerpt for item in evidence):
        claims.append(
            CanonicalClaim(
                "PRODUCT.principal_guaranteed",
                False,
                "현재 조회된 집합투자증권은 예금자보호 대상이 아니며 원금이 보장되지 않습니다.",
                protection.id,
            )
        )
    lump = next(
        (
            item for item in evidence
            if "일시금" in item.excerpt and "퇴직소득세" in item.excerpt and "100%" in item.excerpt
        ),
        None,
    )
    if lump:
        claims.append(
            CanonicalClaim(
                "TAX.lump_sum_flat_rate",
                "100",
                "일시금으로 받으면 퇴직소득세를 100% 납부하며, 세액공제율과 같은 단일 세율로 단정하지 않습니다.",
                lump.id,
            )
        )
    return claims


def extract_user_claims(question: str) -> list[UserClaim]:
    claims: list[UserClaim] = []
    if has_alias(question, "dc"):
        if any(marker in question for marker in ("미리 확정", "미리 정", "사전에 확정", "지급액이 확정", "급여가 사전에")):
            claims.append(UserClaim("DC.benefit_predefined", True))
        if any(marker in question for marker in ("회사가 투자", "회사가 운용", "고용주가 투자", "고용주가 운용", "회사가 수익률", "회사 책임", "수익률 책임", "책임이 전부 회사", "책임지는", "고용주가 운용을 책임", "회사가 보장")):
            claims.append(UserClaim("DC.operator", "company"))
        if "보장" in question and any(marker in question for marker in ("회사", "고용주", "수익률")):
            claims.append(UserClaim("DC.operator", "company"))
    if has_alias(question, "db"):
        if any(marker in question for marker in ("제가 직접 운용", "근로자가 직접 운용", "가입자가 직접 운용", "근로자가 운용")):
            claims.append(UserClaim("DB.operator", "employee"))
        if any(marker in question for marker in ("수익률이 낮으면 퇴직금도 줄", "운용성과에 따라", "수익률에 따라 퇴직급여", "최종 급여가 변동", "운용해서 최종 급여가 변동", "줄어드는 거죠")):
            claims.append(UserClaim("DB.final_depends_on_return", True))
    if any(marker in question for marker in ("무제한", "한도는 무제한")):
        claims.append(UserClaim("TAX_CREDIT.unlimited", True))
    if any(marker in question for marker in ("전부 세금에서 빠", "전액 세액공제", "무조건 전부", "1,800만원", "1800만원")) and has_alias(question, "irp"):
        claims.append(UserClaim("TAX_CREDIT.contribution_equals_tax_cut", True))
        if any(marker in question for marker in ("1,800", "1800", "무제한", "전액 세액공제")):
            claims.append(UserClaim("TAX_CREDIT.unlimited", True))
    if "6등급" in question and any(marker in question for marker in ("제일 위험", "가장 위험", "제일 위험한")):
        claims.append(UserClaim("RISK.grade_6_highest", True))
    if has_alias(question, "product_family") and has_alias(question, "principal_protection") and any(
        marker in question for marker in ("원금보장되", "원금이 100%", "무조건 원금")
    ):
        claims.append(UserClaim("PRODUCT.principal_guaranteed", True))
    if (
        "무조건" in question
        and any(marker in question for marker in ("일시금", "퇴직금"))
        and not is_tax_deduction_question(question)
        and "세액공제" not in question
    ):
        for rate in re.findall(r"(\d+(?:\.\d+)?)\s*%", question):
            claims.append(UserClaim("TAX.lump_sum_flat_rate", rate))
    return claims


def detect_false_premise(question: str, evidence: list[Citation], products: list[dict] | None = None) -> FalsePremiseHit | None:
    grounded = {item.key: item for item in grounded_canonical_claims(evidence, products)}
    for user_claim in extract_user_claims(question):
        canonical = grounded.get(user_claim.key)
        if canonical is None:
            continue
        if user_claim.value == canonical.value:
            continue
        if canonical.key.startswith("DC."):
            correction = (
                "아닙니다. 확정기여형(DC)은 회사가 매년 일정 금액을 근로자의 계좌에 입금하고 "
                "근로자가 직접 운용하므로, 퇴직급여가 미리 확정되지 않고 운용 수익률에 따라 최종 퇴직급여가 달라집니다."
            )
        elif canonical.key.startswith("DB."):
            correction = "아닙니다. 확정급여형(DB)은 근로자가 받을 퇴직급여가 사전에 확정되고 회사가 적립금을 운용합니다."
        elif canonical.key.startswith("TAX_CREDIT."):
            correction = (
                "아닙니다. 제공된 세액공제 안내에 따르면 연금저축의 세액공제 대상 납입한도는 연 600만원이고, "
                "IRP를 포함한 연금계좌 합산 한도는 연 900만원입니다. 납입액만큼 세금이 줄어든다는 뜻이 아닙니다."
            )
        elif canonical.key == "TAX.lump_sum_flat_rate":
            correction = (
                f"아닙니다. {canonical.text} "
                "제공된 자료만으로 해당 세율을 세액공제율과 같은 값으로 확인할 수 없습니다."
            )
        else:
            correction = f"아닙니다. {canonical.text}"
        return FalsePremiseHit(user_claim=user_claim, canonical=canonical, correction=correction, evidence_id=canonical.evidence_id)
    return None


def answer_affirms_false_premise(message: str) -> bool:
    opening = message.lstrip(" \t\r\n[]().,!")[:24]
    return opening.startswith(_AFFIRM_OPENING)


def answer_asserts_false_numeric_premise(message: str, value: object) -> bool:
    """True when a contradicted numeric premise is stated as an applied fact."""
    rate = str(value).rstrip("%")
    if not rate:
        return False
    pattern = re.compile(rf"{re.escape(rate)}\s*%")
    for match in pattern.finditer(message):
        window = message[max(0, match.start() - 24):match.end() + 18]
        if any(marker in window for marker in ("아닙", "않", "아닙니다", "확인할 수 없", "단정할 수 없")):
            continue
        if any(marker in window for marker in ("적용", "기본", "입니다", "맞", "무조건", "세율은")):
            return True
    return False
