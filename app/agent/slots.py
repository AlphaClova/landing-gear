"""Slot Manager (A5): 필수 입력 정의, 세션 병합, 최대 3개 역질문."""

from dataclasses import dataclass
import re

from app.api.schemas import RequiredSlot, UserProfile
from app.agent.router import Intent
from app.core.query_normalization import has_alias, is_closed_tax_faq, is_generic_pension_receiving_question, is_tax_deduction_question, needs_retirement_benefit_clarification

MAX_CLARIFICATION_SLOTS = 3


@dataclass(frozen=True)
class SlotSpec:
    name: str
    prompt: str
    reason: str


REQUIRED_SLOTS_BY_INTENT: dict[Intent, tuple[SlotSpec, ...]] = {
    "제도": (),
    "세제": (
        SlotSpec("retirement_amount_won", "예상 퇴직급여(퇴직금) 총액이 얼마인가요?", "퇴직소득세 계산에 필요"),
        SlotSpec("expected_tax_won", "예상 퇴직소득세를 알고 계신가요? (모르면 생략 가능)", "실수령액 비교에 사용"),
    ),
    "종합": (
        SlotSpec("retirement_amount_won", "예상 퇴직급여(퇴직금) 총액이 얼마인가요?", "일시금/연금 비교 계산에 필요"),
        SlotSpec("expected_tax_won", "예상 퇴직소득세가 얼마인가요?", "실수령액 비교 계산에 필요"),
    ),
    "상품": (SlotSpec("plan_type", "IRP·DC 중 어떤 계좌 기준으로 비교할까요?", "상품 검색 필터에 필요"),),
    "절차": (),
    "범위 밖": (),
}


class SlotManager:
    def merge(self, profile: UserProfile, session_slots: dict[str, object]) -> dict[str, object]:
        merged: dict[str, object] = dict(session_slots)
        for name, value in profile.model_dump(exclude={"extra"}).items():
            if value is not None:
                merged[name] = value
        merged.update(profile.extra)
        return merged

    def required(self, intent: Intent, slots: dict[str, object], question: str = "") -> list[RequiredSlot]:
        effective_slots = {**slots, **self.extract(question)}
        # 연금수령에 따른 퇴직소득세 절감액은 이연퇴직소득세만으로 계산된다.
        # 퇴직금 총액은 실수령액 비교에는 필요하지만 세액 차이 계산에는 필요하지 않다.
        if intent == "종합" and "절세액 계산" in question:
            if effective_slots.get("expected_tax_won") is not None:
                return []
            return [RequiredSlot(name="expected_tax_won", prompt="예상 퇴직소득세가 얼마인가요?", reason="연금수령 절세액 계산에 필요")]
        if intent == "세제" and needs_retirement_benefit_clarification(question):
            return [
                RequiredSlot(
                    name="benefit_type",
                    prompt="해당 지급금의 공식 명칭이 명예퇴직수당·퇴직수당·퇴직위로금 중 무엇인가요?",
                    reason="수당의 법적 성격과 적용 가능한 세제 규칙 확인",
                )
            ]
        if intent == "제도" and is_generic_pension_receiving_question(question):
            if effective_slots.get("pension_kind") is None:
                return [
                    RequiredSlot(
                        name="pension_kind",
                        prompt="퇴직연금, 연금저축, IRP 중 어떤 연금을 기준으로 안내할까요?",
                        reason="연금 종류에 따라 수령 시점이 다릅니다",
                    )
                ]
            return []
        if intent == "세제":
            return []
        if intent == "종합" and not any(x in question for x in ("일시금", "연금 비교", "절세액 계산", "실수령액")):
            if not any(x in question for x in ("상품 선택", "상품 추천", "추천", "하나만", "찍어")):
                return []
        if intent == "종합" and any(x in question for x in ("상품 선택", "상품 추천", "추천", "하나만", "찍어")):
            specs = (
                SlotSpec("plan_type", "IRP·DC 중 어떤 계좌 기준인가요?", "가입 가능한 상품 범위 확인"),
                SlotSpec("investment_horizon", "예상 투자기간은 얼마나 되나요?", "투자기간 조건 확인"),
                SlotSpec("risk_tolerance", "감수할 수 있는 손실 수준은 어느 정도인가요?", "위험등급 기준 확인"),
            )
            missing = [spec for spec in specs if effective_slots.get(spec.name) is None]
            return [RequiredSlot(name=s.name, prompt=s.prompt, reason=s.reason) for s in missing[:MAX_CLARIFICATION_SLOTS]]
        if intent == "상품":
            if self._is_specific_product_question(question):
                return []
            if any(marker in question for marker in ("추천", "좋은", "괜찮은", "골라", "정해", "최적", "하나만", "찍어", "어떤 정보가 더 필요")):
                if effective_slots.get("plan_type") is None:
                    inferred_plan_type = self._plan_type_from_question(question)
                    if inferred_plan_type is not None:
                        effective_slots["plan_type"] = inferred_plan_type
                if effective_slots.get("investment_horizon") is None and (
                    effective_slots.get("investment_horizon_months") is not None
                    or effective_slots.get("investment_horizon_label")
                ):
                    effective_slots["investment_horizon"] = (
                        effective_slots.get("investment_horizon")
                        or effective_slots.get("investment_horizon_months")
                        or 1
                    )
                if effective_slots.get("risk_tolerance") is None and effective_slots.get("principal_guarantee_required"):
                    effective_slots["risk_tolerance"] = "principal_protection"
                specs = (
                    SlotSpec("plan_type", "IRP·DC 중 어떤 계좌 기준인가요?", "가입 가능한 상품 범위 확인"),
                    SlotSpec("investment_horizon", "예상 투자기간은 얼마나 되나요?", "만기·변동성 기준 확인"),
                    SlotSpec("risk_tolerance", "감수할 수 있는 손실 수준은 어느 정도인가요?", "위험등급 기준 확인"),
                )
                missing = [spec for spec in specs if effective_slots.get(spec.name) is None]
                return [RequiredSlot(name=s.name, prompt=s.prompt, reason=s.reason) for s in missing[:MAX_CLARIFICATION_SLOTS]]
            return []
        specs = REQUIRED_SLOTS_BY_INTENT.get(intent, ())
        missing = [spec for spec in specs if effective_slots.get(spec.name) is None]
        limited = missing[:MAX_CLARIFICATION_SLOTS]
        return [RequiredSlot(name=s.name, prompt=s.prompt, reason=s.reason) for s in limited]

    @classmethod
    def extract(cls, question: str) -> dict[str, object]:
        extracted: dict[str, object] = {}
        plan = cls._plan_type_from_question(question)
        if plan: extracted["plan_type"] = plan
        amounts = list(re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(억|천만|백만|만)?\s*원", question))
        for match in amounts:
            value=float(match.group(1).replace(",","")); unit=match.group(2)
            value*= {"억":100_000_000,"천만":10_000_000,"백만":1_000_000,"만":10_000}.get(unit,1)
            prefix=question[max(0,match.start()-12):match.start()]
            key="expected_tax_won" if any(x in prefix for x in ("세금","소득세")) else "retirement_amount_won"
            extracted[key]=int(value)
        horizon = re.search(r"(\d+)\s*년(?:\s*(?:이상|이하))?\s*(?:투자|운용)", question)
        if horizon:
            extracted["investment_horizon"] = int(horizon.group(1))
            extracted["investment_horizon_label"] = f"{horizon.group(1)}년"
        else:
            year_use = re.search(r"(\d+)\s*년\s*(?:내|안|이내)", question)
            months = re.search(r"(\d+)\s*개월(?:\s*(?:이상|이하|내|안|이내))?", question)
            if months:
                extracted["investment_horizon_months"] = int(months.group(1))
                extracted["investment_horizon_label"] = f"{months.group(1)}개월"
            elif year_use:
                extracted["investment_horizon"] = int(year_use.group(1))
                extracted["investment_horizon_label"] = f"{year_use.group(1)}년"
        if has_alias(question, "principal_protection") or any(
            marker in question for marker in ("원금 보장", "손실 없는", "손실이 없는", "손실 안")
        ):
            extracted["principal_guarantee_required"] = True
        fee_ceiling = re.search(r"(?:보수|수수료)\s*(\d+(?:\.\d+)?)\s*%\s*이하", question)
        if fee_ceiling:
            extracted["fee_ceiling_percent"] = float(fee_ceiling.group(1))
        if any(x in question for x in ("안정형", "안정적", "낮은 위험", "저위험", "위험이 낮", "손실위험이 낮")):
            extracted["risk_tolerance"] = "stable"
        return extracted

    @staticmethod
    def _requires_tax_calculation(question: str) -> bool:
        return any(x in question for x in ("내 세금 계산", "절세액 계산", "실수령액 계산")) and not is_closed_tax_faq(question)

    @staticmethod
    def _is_specific_product_question(question: str) -> bool:
        return has_alias(question, "product_family") and (
            "솔로몬" in question or any(x in question for x in ("단기", "중장기", "장기", "기간별"))
        )

    @staticmethod
    def _plan_type_from_question(question: str) -> str | None:
        upper = question.upper()
        for plan_type in ("IRP", "DC", "DB"):
            if plan_type in upper:
                return plan_type
        return None
