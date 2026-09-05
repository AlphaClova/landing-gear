from app.api.schemas import (
    Citation,
    InternalAnswer,
    ThinkTrace,
    parse_retrieved_context,
    select_public_citations,
    to_eval_response,
)


def _citation(evidence_id: str, document_id: str, page: int, excerpt: str) -> Citation:
    return Citation(
        id=evidence_id,
        document_id=document_id,
        page=page,
        source="provided",
        excerpt=excerpt,
    )


def _answer(
    citations: list[Citation],
    *,
    claim_plan: list[dict[str, object]],
    product_facts: list[dict[str, object]] | None = None,
    message: str = "검증된 답변 본문",
    intent: str = "제도",
    answer_type: str = "result",
) -> InternalAnswer:
    return InternalAnswer(
        type=answer_type,  # type: ignore[arg-type]
        message=message,
        request_id="req-test",
        citations=citations,
        trace=ThinkTrace(
            intent=intent,
            route="fast_path",
            route_confidence=1.0,
            claim_plan=claim_plan,
            product_facts=product_facts or [],
        ),
    )


def _claim(*evidence_ids: str, product_fact_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "subtask": "test",
        "status": "answerable",
        "claims": [{
            "text": "검증된 사실",
            "evidence_ids": list(evidence_ids),
            "product_fact_ids": product_fact_ids or [],
        }],
    }


def test_public_context_reuses_claim_evidence_mapping_and_preserves_answer() -> None:
    db_dc = _citation("db-dc", "doc10", 1, "DB와 DC의 급여 결정 방식과 운용 주체")
    eligibility = _citation("eligibility", "doc11", 2, "퇴직연금 가입 대상")
    internal = _answer([db_dc, eligibility], claim_plan=[_claim("db-dc")])

    public = to_eval_response(internal, "Q-DB-DC", "DB형과 DC형의 차이는?")

    assert public.answer == internal.message
    assert parse_retrieved_context(public.retrieved_context) == [db_dc.excerpt]


def test_public_context_deduplicates_same_id_and_equivalent_excerpt() -> None:
    first = _citation("tax-limit", "doc41", 1, "연금저축 세액공제 한도는 연 600만원입니다.")
    same_id = first.model_copy(update={"excerpt": "연금저축 세액공제 한도는 연 600만원입니다."})
    equivalent = _citation("tax-limit-copy", "doc41", 1, "연금저축  세액공제 한도는 연 600만원입니다!")
    internal = _answer(
        [first, same_id, equivalent],
        claim_plan=[_claim("tax-limit", "tax-limit-copy")],
        message="연금저축 세액공제 한도는 연 600만원입니다.",
        intent="세제",
    )

    assert select_public_citations(internal, "연금저축과 IRP 세액공제 한도는?") == [first]


def test_similar_evidence_with_different_numbers_is_not_deduplicated() -> None:
    pension = _citation("pension", "doc41", 1, "연금저축 세액공제 한도는 연 600만원으로 적용됩니다.")
    combined = _citation("combined", "doc55", 10, "연금저축 세액공제 한도는 연 900만원으로 적용됩니다.")
    internal = _answer(
        [pension, combined],
        claim_plan=[_claim("pension", "combined")],
        message="연금저축 한도는 연 600만원, IRP 합산 한도는 연 900만원입니다.",
        intent="세제",
    )

    assert select_public_citations(internal, "연금저축과 IRP 세액공제 한도는?") == [pension, combined]


def test_c1_removes_eligibility_pages_and_keeps_db_dc_page() -> None:
    page1 = _citation("doc10-p1", "doc10", 1, "확정급여형(DB, Defined Benefit)은 무엇인가요? 확정기여형(DC)은 무엇인가요?")
    page2 = _citation("doc10-p2", "doc10", 2, "[표] 개인사업자 퇴직연금 가입 불가 / 가입 가능")
    page3 = _citation("doc10-p3", "doc10", 3, "근로자퇴직급여 보장법 제2조 근로자 정의와 가입대상")
    internal = _answer(
        [page1, page2, page3],
        claim_plan=[_claim("doc10-p1", "doc10-p2", "doc10-p3")],
        message="확정급여형(DB)은 퇴직금액이 사전에 확정되고 회사가 운용합니다. 확정기여형(DC)은 근로자가 직접 운용합니다.",
    )

    selected = select_public_citations(internal, "DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?")
    assert selected == [page1]


def test_c2_removes_wrong_tax_scope_and_keeps_600_900() -> None:
    limit = _citation("doc41-p1", "doc41", 1, "세액공제 받을 수 있는 납입한도는 연금저축 연600만원, IRP 합산 연900만원이다.")
    rate = _citation("doc55-p10", "doc55", 10, "세액공제율 16.5% 13.2% 세액공제 한도 연금저축 단독 600만원 IRP 합산 900만원")
    retirement = _citation("doc51-p2", "doc51", 2, "이 감면은 퇴직소득세에만 적용된다. 연금소득세(3.3% ~ 5.5%)가 별도로 적용된다.")
    internal = _answer(
        [limit, rate, retirement],
        claim_plan=[],
        message="연금저축 세액공제 대상 납입한도는 연 600만원이고 합산 한도는 연 900만원입니다. 실제 세액공제 금액은 소득에 따른 공제율에 따라 달라집니다.",
        intent="세제",
    )

    selected = select_public_citations(internal, "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.")
    assert selected == [limit, rate]


def test_c3_keeps_60day_and_honor_benefit_and_drops_example() -> None:
    core = _citation(
        "doc26-p1-core",
        "doc26",
        1,
        "퇴직수당과 명예퇴직수당은 퇴직소득이다. 세후로 받은 경우 60일 내에 연금저축계좌나 IRP로 입금할 수 있다.",
    )
    deferral = _citation("doc55-p17", "doc55", 17, "60일 이내에 과세이연 신청을 하게 되면 퇴직소득세 환급의 업무가 발생")
    example = _citation("doc26-p1-ex", "doc26", 1, "예를 들어 30년 근무, 퇴직수당 1억원 (2002년 이후 기여분)이면 퇴직소득세는 26만 4천만원이다.")
    duplicate = core.model_copy(update={"id": "doc26-p1-dup"})
    internal = _answer(
        [core, deferral, example, duplicate],
        claim_plan=[_claim("doc26-p1-core", "doc26-p1-ex", "doc26-p1-dup")],
        message="명예퇴직수당은 퇴직소득이며 세후 수령일부터 60일 이내에 입금하고 퇴직소득세 환급·과세이연을 신청할 수 있습니다.",
        intent="세제",
    )

    selected = select_public_citations(
        internal,
        "명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.",
    )
    assert core in selected
    assert deferral in selected
    assert example not in selected
    assert duplicate not in selected


def test_c4_keeps_requested_products_and_drops_ultrashort() -> None:
    short = _citation("short-ev", "r2_short", 3, "미래에셋솔로몬단기국공채 투자위험등급 5등급 2. 투자전략 단기 국공채")
    mid = _citation("mid-ev", "r2_mid", 3, "미래에셋솔로몬중장기국공채 투자위험등급 5등급 2. 투자전략 중장기 국공채")
    long = _citation("long-ev", "r2_long", 3, "미래에셋솔로몬장기국공채 투자위험등급 5등급 2. 투자전략 장기 국공채")
    ultra = _citation("ultra-ev", "r2_ultra", 4, "미래에셋솔로몬초단기국공채 투자위험등급 6등급 2. 투자전략 초단기")
    extra_page = _citation("mid-hist", "r2_mid", 12, "2016.07.02 | 투자위험등급 분류체계 개편(5단계 체계→6단계 체계)")
    facts = [
        {"product_id": "short", "product_name": "미래에셋솔로몬단기국공채", "document_id": "r2_short", "page": 1},
        {"product_id": "mid", "product_name": "미래에셋솔로몬중장기국공채", "document_id": "r2_mid", "page": 1},
        {"product_id": "long", "product_name": "미래에셋솔로몬장기국공채", "document_id": "r2_long", "page": 1},
    ]
    message = "미래에셋솔로몬단기국공채와 미래에셋솔로몬중장기국공채와 미래에셋솔로몬장기국공채를 비교합니다."
    internal = _answer(
        [short, mid, long, ultra, extra_page],
        claim_plan=[_claim(product_fact_ids=["short", "mid", "long"])],
        product_facts=facts,
        message=message,
        intent="상품",
    )

    selected = select_public_citations(internal, "솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요?")
    assert selected == [short, mid, long]


def test_c5_clarification_removes_specific_product_evidence() -> None:
    general = _citation("general", "doc-guide", 3, "상품 선택에는 투자기간과 위험성향 확인이 필요합니다.")
    prospectus = _citation("fund", "r2_short", 1, "솔로몬 단기국공채 투자설명서 수수료선취-오프라인(A) 파생상품")
    internal = _answer(
        [general, prospectus],
        claim_plan=[_claim("general")],
        product_facts=[{
            "product_id": "short",
            "product_name": "미래에셋솔로몬단기국공채증권자투자신탁",
            "document_id": "r2_short",
            "page": 1,
        }],
        message="IRP 혹은 DC 중 어떤 계좌 기준인지, 예상 투자기간과 감수 가능한 손실 수준을 알려주세요.",
        intent="상품",
    )

    assert select_public_citations(internal, "좋은 연금 상품 하나 추천해 주세요.") == [general]


def test_c6_out_of_scope_keeps_empty_public_context_and_answer() -> None:
    leaked = _citation("noise", "doc10", 1, "확정급여형(DB) 설명")
    internal = _answer(
        [leaked],
        claim_plan=[],
        message="이 질문은 은퇴 자금(퇴직연금) 의사결정 범위를 벗어나 답변드리기 어렵습니다.",
        intent="범위 밖",
        answer_type="limitation",
    )

    public = to_eval_response(internal, "Q-OOS", "비트코인 가격을 예측해줘")

    assert public.answer == internal.message
    assert public.retrieved_context == ""


def test_pruning_does_not_drop_last_numeric_support() -> None:
    support = _citation("hours", "doc10", 2, "1주일 평균 근로시간이 15시간 이상이고 1년 이상 계속 근무")
    other = _citation("elig", "doc10", 3, "공무원, 군인, 사립학교 교직원은 일반 퇴직연금 가입대상이 아닙니다.")
    message = "1주일 평균 근로시간이 15시간 이상이고 1년 이상 계속 근무하는 경우 퇴직연금 가입 대상입니다."
    internal = _answer([support, other], claim_plan=[_claim("hours", "elig")], message=message)

    selected = select_public_citations(internal, "주 14시간 근무자도 퇴직연금 대상인가요?")
    assert support in selected
    assert "15시간" in " ".join(item.excerpt for item in selected)


def test_answer_text_and_five_string_contract_unchanged_by_pruning() -> None:
    db_dc = _citation("db-dc", "doc10", 1, "확정급여형(DB)과 확정기여형(DC)의 운용 주체")
    extra = _citation("tax", "doc51", 2, "연금소득세(3.3% ~ 5.5%)가 별도로 적용된다.")
    internal = _answer(
        [db_dc, extra],
        claim_plan=[_claim("db-dc")],
        message="확정급여형(DB)은 회사가 운용하고 확정기여형(DC)은 근로자가 직접 운용합니다.",
    )
    before = [item.model_copy() for item in internal.citations]
    public = to_eval_response(internal, "Q-DB-DC", "DB형과 DC형의 차이는?")

    assert public.answer == internal.message
    assert set(public.model_dump()) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
    assert all(isinstance(value, str) for value in public.model_dump().values())
    assert internal.citations == before
    assert extra.excerpt not in public.retrieved_context


def test_unresolved_general_recommendation_hides_incidental_product_prospectus() -> None:
    general = _citation("general", "doc-guide", 3, "상품 선택에는 투자기간과 위험성향 확인이 필요합니다.")
    prospectus = _citation("fund", "r2_short", 1, "솔로몬 단기국공채 투자설명서")
    internal = _answer(
        [general, prospectus],
        claim_plan=[_claim("general")],
        product_facts=[{
            "product_id": "short",
            "product_name": "미래에셋솔로몬단기국공채증권자투자신탁",
            "document_id": "r2_short",
            "page": 1,
        }],
        message="투자기간과 위험성향을 먼저 알려주세요.",
        intent="상품",
    )

    assert select_public_citations(internal, "IRP 상품을 추천해줘") == [general]


def test_confirmed_product_comparison_keeps_each_claimed_prospectus() -> None:
    short = _citation("short-evidence", "r2_short", 1, "솔로몬 단기국공채 위험등급 투자전략")
    long = _citation("long-evidence", "r2_long", 1, "솔로몬 장기국공채 위험등급 투자전략")
    facts = [
        {"product_id": "short", "product_name": "솔로몬 단기국공채", "document_id": "r2_short", "page": 1},
        {"product_id": "long", "product_name": "솔로몬 장기국공채", "document_id": "r2_long", "page": 1},
    ]
    internal = _answer(
        [short, long],
        claim_plan=[_claim(product_fact_ids=["short", "long"])],
        product_facts=facts,
        message="솔로몬 단기국공채와 솔로몬 장기국공채를 비교합니다.",
        intent="상품",
    )

    assert select_public_citations(internal, "솔로몬 단기/장기 상품 비교") == [short, long]


def test_r11_drops_unrelated_doc55_ops_and_keeps_direct_tax_or_transfer() -> None:
    tax = _citation(
        "doc51-tax",
        "doc51",
        1,
        "법정퇴직금을 IRP(개인형 퇴직연금계좌)로 의무 이전해야 한다. 일시금과 연금의 과세 체계가 다르다.",
    )
    credit = _citation("doc41-limit", "doc41", 1, "연금저축은 연600만원, IRP는 합산 연900만원까지 세액공제")
    promo = _citation("doc55-promo", "doc55", 18, "임원 승진 시 퇴직금 추계액 재산정 업무")
    register = _citation("doc55-reg", "doc55", 32, "개인정보들로 당사에 고객등록, 계좌개설이 되기 때문에")
    account = _citation("doc55-acct", "doc55", 11, "IRP계좌번호는 가입자부담금을 입금하는 용도로 사용되며")
    db_ops = _citation("doc55-db", "doc55", 12, "DB는 회사가 적립금을 운용하고 확정된 퇴직금을 지급한다")
    internal = _answer(
        [tax, credit, promo, register, account, db_ops],
        claim_plan=[_claim("doc51-tax", "doc41-limit", "doc55-promo", "doc55-reg", "doc55-acct", "doc55-db")],
        message="[한계] 퇴직금을 IRP로 이전하면 과세 체계가 달라질 수 있습니다.",
        intent="세제",
    )
    selected = select_public_citations(internal, "퇴직금을 IRP에 넣으면 세금은 어떻게 되나요?")
    assert tax in selected
    assert credit not in selected
    assert promo not in selected
    assert register not in selected
    assert account not in selected
    assert db_ops not in selected


def test_r15_does_not_generalize_teacher_only_or_keep_pii() -> None:
    teacher = _citation(
        "doc26-p1",
        "doc26",
        1,
        "교사·공무원의 명예퇴직수당은 세후 수령일부터 60일 내에 연금계좌에 입금할 수 있다.",
    )
    pii = _citation("doc55-pii", "doc55", 32, "개인정보들로 당사에 고객등록, 계좌개설이 되기 때문에")
    account = _citation("doc55-acct", "doc55", 11, "IRP계좌번호는 가입자부담금을 입금하는 용도로 사용되며")
    general = _citation("doc51-receipt", "doc51", 1, "퇴직금을 수령하는 방식은 일시금과 연금계좌(IRP·연금저축) 이전이다.")
    internal = _answer(
        [teacher, pii, account, general],
        claim_plan=[_claim("doc26-p1", "doc55-pii", "doc55-acct", "doc51-receipt")],
        message="[한계] 일반 명퇴수당을 연금계좌에 넣을 수 있는지는 제공 문서만으로 확정할 수 없습니다.",
        intent="세제",
    )
    selected = select_public_citations(internal, "명퇴수당을 받은 뒤 연금계좌에 넣을 수 있나요?")
    assert selected == []


def test_r16_generic_risk_question_drops_named_product_evidence() -> None:
    product = _citation(
        "product-gold",
        "r2_gold",
        1,
        "상품명: 한국투자 골드플랜 투자위험등급: 5등급",
    )
    internal = _answer(
        [product],
        claim_plan=[_claim(product_fact_ids=["gold"])],
        product_facts=[{
            "product_id": "gold",
            "product_name": "한국투자 골드플랜",
            "document_id": "r2_gold",
            "page": 1,
            "risk_level": 5,
        }],
        message="한국투자 골드플랜 위험등급 5등급(낮은 위험)",
        intent="상품",
    )
    selected = select_public_citations(internal, "위험등급 5등급은 어떤 의미인가요?")
    assert selected == []


def test_g019_restores_direct_irp_transfer_support_only() -> None:
    transfer = _citation(
        "doc51-dc-irp",
        "doc51",
        2,
        "반면 DC퇴직금은 나이와 무관하게 반드시 IRP로 이전해야 한다. 법정퇴직금은 IRP로만 이전할 수 있다.",
    )
    eligibility = _citation(
        "doc10-elig",
        "doc10",
        2,
        "개인사업 대표는 일반 IRP(개인형 퇴직연금)를 통해 자영업자로 가입할 수 있습니다. DC 퇴직연금 가입 대상",
    )
    internal = _answer(
        [eligibility, transfer],
        claim_plan=[_claim("doc10-elig", "doc51-dc-irp")],
        message="DC 법정퇴직금은 IRP로 이전할 수 있습니다.",
        intent="제도",
    )
    selected = select_public_citations(internal, "IRP와 DC는 같은 제도인가요?")
    assert transfer in selected
    assert eligibility not in selected


def test_g042_restores_year_rate_and_pension_income_tax_support() -> None:
    year_rate = _citation(
        "doc51-year",
        "doc51",
        1,
        "연금수령 시 이연퇴직소득세의 70% ~ 50%가 적용된다. 실제수령연차에 따라 70%, 60%, 50%다.",
    )
    mixed_tax = _citation(
        "doc51-mixed",
        "doc51",
        2,
        "세액공제를 받은 납입금과 운용수익에는 연금소득세(3.3% ~ 5.5%)가 별도로 적용된다.",
    )
    ops = _citation("doc55-ops", "doc55", 5, "※ 명예퇴직금과 잔여부담금은 퇴직신청 접수 시 입금이 가능합니다.")
    message = (
        "연금계좌 과세는 재원별로 구분합니다. 세액공제를 받지 않은 개인납입금, 퇴직금·이연퇴직소득, "
        "세액공제를 받은 개인납입금과 운용수익은 같은 세율로 취급하지 않습니다. "
        "퇴직금 재원의 연금수령에는 이연퇴직소득세의 70%·60%·50% 체계가 적용되며, "
        "3.3~5.5%는 퇴직금 재원 자체의 세율로 적용하지 않습니다."
    )
    internal = _answer(
        [ops, year_rate, mixed_tax],
        claim_plan=[_claim("doc55-ops", "doc51-year", "doc51-mixed")],
        message=message,
        intent="종합",
    )
    selected = select_public_citations(internal, "퇴직금과 개인납입금이 섞인 IRP의 과세를 구분해줘")
    excerpts = " ".join(item.excerpt for item in selected)
    assert year_rate in selected
    assert mixed_tax in selected
    assert ops not in selected
    assert "70%" in excerpts and "60%" in excerpts and "50%" in excerpts
    assert "3.3%" in excerpts and "5.5%" in excerpts


def test_g072_restores_fee_table_that_supports_each_rate() -> None:
    fee_table = _citation(
        "r2-long-fees",
        "r2_kr5153420105",
        27,
        "종류A 수수료선취-오프라인 집합투자업자 보수 0.12 판매회사 보수 0.19 신탁업자 보수 0.02 일반사무관리 0.02 총 보수 0.35",
    )
    purpose = _citation(
        "r2-long-purpose",
        "r2_kr5153420105",
        3,
        "투자목적 이 투자신탁은 국내 국공채에 주로 투자하는 모투자신탁",
    )
    ultrashort = _citation(
        "r2-ultra-fees",
        "r2_kr5153450658",
        4,
        "수수료미징구-오프라인 총 보수 0.45 초단기 0.35",
    )
    message = (
        "요청하신 총보수 0%의 상품에 대한 정보를 찾지 못했습니다. 대신, 제공된 문서에서 확인할 수 있는 상품의 보수는 다음과 같습니다.\n"
        "* 종류 A: 수수료 선취 - 오프라인\n"
        "   * 집합투자업자 보수: 0.12%\n"
        "   * 판매회사 보수: 0.19%\n"
        "   * 총 보수: 0.35%"
    )
    internal = _answer(
        [purpose, ultrashort, fee_table],
        claim_plan=[],
        product_facts=[{
            "product_id": "long",
            "product_name": "미래에셋솔로몬장기국공채증권자투자신탁1호(채권)",
            "document_id": "r2_kr5153420105",
            "page": 1,
        }],
        message=message,
        intent="상품",
    )
    selected = select_public_citations(internal, "총보수 0% 상품만 찾아줘")
    excerpts = " ".join(item.excerpt for item in selected)
    assert fee_table in selected
    assert purpose not in selected
    assert ultrashort not in selected
    assert "0.12" in excerpts and "0.19" in excerpts and "0.35" in excerpts


def test_empty_limitation_does_not_restore_arbitrary_first_citation() -> None:
    noise = _citation("noise", "doc10", 3, "근로자퇴직급여 보장법 제2조 근로자의 정의")
    internal = _answer(
        [noise],
        claim_plan=[],
        message="이연퇴직소득세의 70%가 적용됩니다. [한계] 확인되지 않은 내용은 단정할 수 없습니다.",
    )
    assert select_public_citations(internal, "IRP와 DC는 같은 제도인가요?") == []


def test_c5_clarification_does_not_auto_restore_product_evidence() -> None:
    prospectus = _citation("fund", "r2_short", 1, "솔로몬 단기국공채 투자설명서 수수료선취-오프라인(A) 0.66")
    internal = _answer(
        [prospectus],
        claim_plan=[_claim("fund")],
        product_facts=[{
            "product_id": "short",
            "product_name": "미래에셋솔로몬단기국공채증권자투자신탁",
            "document_id": "r2_short",
            "page": 1,
        }],
        message="IRP 혹은 DC 중 어떤 계좌 기준인지, 예상 투자기간과 감수 가능한 손실 수준을 알려주세요.",
        intent="상품",
    )
    assert select_public_citations(internal, "좋은 연금 상품 하나 추천해 주세요.") == []


def test_r15_limitation_does_not_restore_teacher_or_pii() -> None:
    teacher = _citation("doc26-p1", "doc26", 1, "교사·공무원의 명예퇴직수당은 세후 60일 내에 연금계좌에 입금할 수 있다.")
    pii = _citation("doc55-pii", "doc55", 32, "개인정보들로 당사에 고객등록, 계좌개설이 되기 때문에")
    internal = _answer(
        [teacher, pii],
        claim_plan=[_claim("doc26-p1", "doc55-pii")],
        message="[한계] 일반 명퇴수당을 연금계좌에 넣을 수 있는지는 제공 문서만으로 확정할 수 없습니다.",
        intent="세제",
    )
    assert select_public_citations(internal, "명퇴수당을 받은 뒤 연금계좌에 넣을 수 있나요?") == []


def test_r16_does_not_restore_named_product_for_generic_risk_question() -> None:
    product = _citation("product-gold", "r2_gold", 1, "상품명: 한국투자 골드플랜 투자위험등급: 5등급 총보수 0.35%")
    internal = _answer(
        [product],
        claim_plan=[_claim(product_fact_ids=["gold"])],
        product_facts=[{
            "product_id": "gold",
            "product_name": "한국투자 골드플랜",
            "document_id": "r2_gold",
            "page": 1,
        }],
        message="[한계] 비교할 특정 상품과 해당 상품의 Product Fact 또는 투자설명서 근거가 없어 설명할 수 없습니다.",
        intent="상품",
    )
    assert select_public_citations(internal, "위험등급 5등급은 어떤 의미인가요?") == []
