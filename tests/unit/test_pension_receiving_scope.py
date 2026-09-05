from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.core.query_normalization import pension_scope

IN_SCOPE_SPECIFIC_RECEIVING = (
    "퇴직금은 연금으로 받을 수 있나요?",
    "퇴직연금은 언제부터 받을 수 있나요?",
)

GENERIC_RECEIVING = (
    "연금은 언제부터 받을 수 있나요?",
    "연금은 몇 살부터 받나요?",
    "연금으로 받으려면 조건이 있나요?",
    "연금은 언제 받을 수 있죠?",
    "연금을 받을 수 있는 나이가 어떻게 되나요?",
)

NOT_AUTO_PENSION = (
    "언제부터 받을 수 있나요?",
    "몇 살부터 받을 수 있나요?",
    "지원금은 언제 받을 수 있나요?",
    "나중에 월급처럼 받을 수 있나요?",
    "언제 월급 받을 수 있나요?",
    "몇 살부터 운전할 수 있나요?",
    "비트코인은 언제 오르나요?",
    "주식 배당은 언제 받을 수 있나요?",
    "국민지원금은 언제 나오나요?",
)

C1_C6 = (
    ("C1", "DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?", "제도"),
    ("C2", "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.", "세제"),
    ("C3", "명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.", "세제"),
    ("C4", "솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.", "상품"),
    ("C5", "좋은 연금 상품 하나 추천해 주세요.", "상품"),
    ("C6", "비트코인 가격을 예측해줘", "범위 밖"),
)


def test_pension_receiving_with_specific_anchor_is_in_scope_institution() -> None:
    router = IntentRouter()
    for question in IN_SCOPE_SPECIFIC_RECEIVING:
        decision = router.classify(question)
        assert decision.intent != "범위 밖", question
        assert decision.intent == "제도", (question, decision.intent)
        assert decision.fallback_reason in {None, "pension_receiving_domain"}


def test_generic_pension_receiving_stays_institution_for_clarification() -> None:
    router = IntentRouter()
    slots = SlotManager()
    for question in GENERIC_RECEIVING:
        decision = router.classify(question)
        assert decision.intent == "제도", (question, decision.intent)
        assert decision.fallback_reason == "pension_receiving_generic"
        missing = slots.required(decision.intent, {}, question)
        assert missing and missing[0].name == "pension_kind", question


def test_receiving_terms_without_pension_anchor_are_not_auto_pension() -> None:
    router = IntentRouter()
    for question in NOT_AUTO_PENSION:
        decision = router.classify(question)
        assert decision.intent == "범위 밖", (question, decision.intent)


def test_c1_c6_intents_unchanged_by_pension_receiving_rescue() -> None:
    router = IntentRouter()
    for case_id, question, intent in C1_C6:
        assert router.classify(question).intent == intent, case_id
        assert pension_scope(question) != "NATIONAL_PENSION" or case_id == "unused"
