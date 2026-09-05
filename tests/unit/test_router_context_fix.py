from app.agent.router import IntentRouter

router = IntentRouter()


def test_r05_dc_plan_type_is_institution() -> None:
    decision = router.classify("DC형에서는 제가 직접 투자하나요?")
    assert decision.intent == "제도"
    assert decision.intent != "범위 밖"


def test_r06_irp_account_definition_is_institution() -> None:
    assert router.classify("IRP는 어떤 계좌인가요?").intent == "제도"


def test_r07_irp_pension_savings_comparison_is_institution() -> None:
    assert router.classify("연금저축과 IRP는 뭐가 다른가요?").intent == "제도"
    assert router.classify("연금저축과 IRP는 어떻게 다른가요?").intent == "제도"


def test_principal_vs_performance_types_are_product_not_oos() -> None:
    decision = router.classify("원리금보장형과 실적배당형은 어떻게 비교해야 하나요?")
    assert decision.intent == "상품"
    assert decision.intent != "범위 밖"


def test_r14_irp_transfer_is_procedure() -> None:
    assert router.classify("퇴직한 뒤 IRP로 옮길 수 있나요?").intent == "절차"


def test_irp_product_controls_stay_product() -> None:
    questions = (
        "IRP에서 가입 가능한 상품 추천해줘",
        "IRP 상품 중 채권형 보여줘",
        "IRP에서 투자할 펀드 알려줘",
        "IRP 상품 비교해줘",
        "IRP에서 위험등급 낮은 상품 찾아줘",
        "IRP 상품 추천해줘",
        "IRP 채권형 상품 보여줘",
        "위험등급 낮은 IRP 상품 알려줘",
    )
    for question in questions:
        assert router.classify(question).intent == "상품", question


def test_non_pension_dc_is_not_institution() -> None:
    for question in ("DC모터가 뭐예요?", "DC 전압이 뭐예요?"):
        decision = router.classify(question)
        assert decision.intent != "제도", question


def test_c1_c6_and_receiving_intents_unchanged() -> None:
    expected = (
        ("DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?", "제도"),
        ("연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.", "세제"),
        ("명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.", "세제"),
        ("솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.", "상품"),
        ("좋은 연금 상품 하나 추천해 주세요.", "상품"),
        ("비트코인 가격을 예측해줘", "범위 밖"),
        ("연금은 언제부터 받을 수 있나요?", "제도"),
        ("퇴직연금은 몇 살부터 받을 수 있나요?", "제도"),
        ("퇴직금은 연금으로 받을 수 있나요?", "제도"),
    )
    for question, intent in expected:
        assert router.classify(question).intent == intent, question
