"""Slot Manager (A5): 필수 입력 정의, 세션 병합, 최대 3개 역질문."""

from dataclasses import dataclass

from app.api.schemas import RequiredSlot, UserProfile
from app.agent.router import Intent

MAX_CLARIFICATION_SLOTS = 3


@dataclass(frozen=True)
class SlotSpec:
    name: str
    prompt: str
    reason: str


REQUIRED_SLOTS_BY_INTENT: dict[Intent, tuple[SlotSpec, ...]] = {
    "제도": (SlotSpec("plan_type", "가입하신 퇴직연금 제도가 DB형인가요, DC형인가요?", "제도별 설명 분기에 필요"),),
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

    def required(self, intent: Intent, slots: dict[str, object]) -> list[RequiredSlot]:
        specs = REQUIRED_SLOTS_BY_INTENT.get(intent, ())
        missing = [spec for spec in specs if slots.get(spec.name) is None]
        limited = missing[:MAX_CLARIFICATION_SLOTS]
        return [RequiredSlot(name=s.name, prompt=s.prompt, reason=s.reason) for s in limited]
