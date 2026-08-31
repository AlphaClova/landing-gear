# Full manual review pack

- Cases: **6**

## G039

- Category: combined
- Latency: 8200.278 ms
- HCX invoked/success: True / True

### Question

퇴직금 3억원, 예상세금 2400만원, DB인데 일시금과 연금 비교해줘

### Answer

Rule Result에 포함된 수령 시나리오별 퇴직소득세입니다.
- lump_sum: 퇴직소득세 24000000KRW, 적용 비율 1.0
- annuity_10_years: 퇴직소득세 16800000KRW, 적용 비율 0.7
- annuity_21_plus_years: 퇴직소득세 12000000KRW, 적용 비율 0.5

### Retrieved context

- | 55세 미만 | 55세 이상
DC법정퇴직금 | IRP 의무이전 | IRP·일반계좌 선택가능
(IRP 수령 시 연금저축으로 계약이전 가능)
DB법정퇴직금 | IRP 의무이전 | IRP·연금저축·일반계좌 선택 가능
법정외퇴직금
(퇴직위로금 등) | IRP·연금저축·일반계좌 선택 가능 | IRP·연금저축·일반계좌 선택 가능
- 퇴직금 IRP 또는 연금저축펀드에 입금해서 연금수령 시 절세혜택
- 퇴직금 일시수령과 연금계좌 입금 후 연금수령에 대한 세금 차이
- 법정퇴직금은 근퇴법에서 의무적으로 지급하도록 정한 퇴직금이다. 이 금액은 반드시 IRP로만 이전할 수 있다. 반면, 법정외퇴직금은 회사가 내부 규정에 따라 법정기준을 초과해 추가로 지급하는 퇴직금이다. 이 금액은 IRP뿐아니라 연금저축에도 입금할 수 있다.
- 퇴직연금사업자에게 퇴직금 지급 청구
- 일시금으로 받으면 퇴직소득세를 100% 즉시 납부해야한다. 이후 남은 돈을 금융상품에 운용하면 발생하는 이자·배당은 금융소득으로 과세되고, 금융소득 종합과세 기준(연 2,000만원)에 포함된다. 또한 이자·배당이 연 1,000만원을 초과한다면 건강보험료 부과 대상 소득에 포함되어 건강보험료에 영향을 준다. 반면 연금으로 받으면 세 가지 혜택이 동시에 생긴다. 퇴직소득세를 30% ~ 50% 감면받고, IRP 내 운용수익은 연금을 받을 때까지 과세가 이연되며, 사적연금소득은 건강보험료 산정에서 제외된다. 먼저 이 차이를 한눈에 파악하자.
- 연금으로 받으면 퇴직소득세가 30% ~ 50% 감면된다는 말은, 원래 납부했어야 할 퇴직소득세의 일부만 내도 된다는 뜻이다. 이 감면율은 연금을 수령하는 기간에 따라 달라진다. 1 ~ 10년차에는 30% 감면(이연퇴직소득세율의 70% 납부), 11년차 ~ 20년차에는 40% 감면(이연퇴직소득세율의 60% 납부), 21년차부터는 50% 감면(이연퇴직소득세율의 50% 납부)이 적용된다. 오래 나눠 받을수록 세금이 더 줄어드는 구조다.

### Human checks

- Accuracy:
- Evidence completeness:
- Requirement coverage:
- Groundedness:
- Reasoning:
- Safety:
- Limit handling:
- Unsupported claim found:
- Wrong number found:
- Wrong evidence found:
- Overconfident recommendation:
- Unnecessary clarification:
- Overall pass:
- Reviewer:
- Comment:

## G041

- Category: combined
- Latency: 7299.98 ms
- HCX invoked/success: True / True

### Question

55세 DB 가입자입니다. 퇴직금 수령계좌와 세금 차이를 같이 설명해줘

### Answer

[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다.

### Retrieved context

- | 55세 미만 | 55세 이상
DC법정퇴직금 | IRP 의무이전 | IRP·일반계좌 선택가능
(IRP 수령 시 연금저축으로 계약이전 가능)
DB법정퇴직금 | IRP 의무이전 | IRP·연금저축·일반계좌 선택 가능
법정외퇴직금
(퇴직위로금 등) | IRP·연금저축·일반계좌 선택 가능 | IRP·연금저축·일반계좌 선택 가능
- 만 55세 이상이 되면 선택의 폭이 넓어진다. DB/퇴직금제도의 퇴직금은 IRP 뿐아니라 연금저축으로도 직접 수령이 가능하다. 반면 DC퇴직금은 나이와 무관하게 반드시 IRP로 이전해야 한다. 연금저축에서 운용하고 싶다면, 계약이전 제도를 활용하자. IRP로 퇴직금 수령 후 연금저축으로 계좌를 이전하는 것은 자유롭게 가능하다.
- - DB제도 & 퇴직금제도 : 원천징수의무자는 사용자(회사)
- ① 만 55세 이상 퇴직자, ② 퇴직금이 300만원 이하, ③ 사망으로 인한 당연 퇴직, ④ 법정 외 퇴직금
- - DB퇴직 시 IRP의무이전 대상이 아닌 퇴직자나 명예퇴직금을 급여계좌로 지급받은 퇴직자가

### Human checks

- Accuracy:
- Evidence completeness:
- Requirement coverage:
- Groundedness:
- Reasoning:
- Safety:
- Limit handling:
- Unsupported claim found:
- Wrong number found:
- Wrong evidence found:
- Overconfident recommendation:
- Unnecessary clarification:
- Overall pass:
- Reviewer:
- Comment:

## G043

- Category: combined
- Latency: 4000.513 ms
- HCX invoked/success: True / True

### Question

명예퇴직금과 법정퇴직금을 서로 다른 계좌로 받을 수 있나요?

### Answer

네, 명예퇴직금과 법정퇴직금은 서로 다른 계좌로 받을 수 있습니다.

명예퇴직수당은 전액이 퇴직소득세 과세대상이므로 세후 금액 전액을 연금계좌로 입금할 수 있고, 퇴직수당의 경우에는 입사일부터 퇴직일까지 쌓인 금액이지만 2002년을 기준으로 그 전 기여분은 비과세되고 이후 기여분만 퇴직소득 과세 대상이 됩니다. 따라서 2002년 전 입사자인 경우 퇴직수당 중 일부는 비과세가 되며, 퇴직소득으로 과세되는 금액만 연금계좌로 입금이 가능합니다. 이때 퇴직소득 원천징수영�수증에 적힌 세후 금액을 확인하고 해당 금액만큼만 연금계좌로 입금해야 합니다.

[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다.

### Retrieved context

- 공무원은 퇴직할 때 퇴직연금 월지급식을 가장 많이 선택한다. 종신까지 매월 공무원연금을 받을 수 있기 때문이다. 이 외에도 근무기간에 따라 퇴직수당과 정년 전 퇴직일 경우 명예퇴직수당을 일시금으로 지급받게 된다. 퇴직수당과 명예퇴직수당은 퇴직소득이다. 퇴직소득세 차감 후 일반계좌로 받게 되는데 세후로 퇴직소득을 받은 경우 60일 내에 연금저축계좌나 IRP로 입금할 수 있다. 공무원연금공단 등 담당부서로 퇴직소득세 환급을 신청해서 차감됐던 세금을 다시 돌려받으면 퇴직수당과 명예퇴직수당은 세전으로 연금계좌에 입금된 것과 동일하게 된다.
- - 퇴직연금 적립금은 이전 받을 사업자계좌로 직접 이체 (적립비율지급)
- ② (DB→DC이전) 사내적립금도 이전 받을 사업자계좌로 직접 이체 (DC는 100% 사외적립의무)
- 연금 수령 혜택을 받으려면 퇴직금을 연금계좌(IRP·연금저축)으로 받아야한다. 그런데 어느 계좌로 받을 수 있는지는 퇴직자의 나이와 퇴직금 종류에 따라 다르다. 퇴직 전에 반드시 본인의 상황에 맞는 경로를 먼저 파악하라.
- 퇴직수당으로 수령 받은 금액 중 일부 금액은 연금계좌로 입금이 안될 수 있다. 퇴직수당은 입사일부터 퇴직일까지 쌓인 금액인데 2002년을 기점으로 그 전 기여분은 비과세되고 이후 기여분만 퇴직소득 과세 대상이다. 2002년 전 입사자인 경우 퇴직수당 중 일부는 비과세되는데, 퇴직소득으로 과세되는 금액만 연금계좌로 입금할 수 있다. 퇴직소득 원천징수영수증에 적힌 세후 금액을 확인해서 그 금액만 연금계좌로 입금해야 한다. 명예퇴직수당은 전액이 퇴직소득세 과세대상이어서 세후 금액 전액을 연금계좌로 입금할 수 있다.

### Human checks

- Accuracy:
- Evidence completeness:
- Requirement coverage:
- Groundedness:
- Reasoning:
- Safety:
- Limit handling:
- Unsupported claim found:
- Wrong number found:
- Wrong evidence found:
- Overconfident recommendation:
- Unnecessary clarification:
- Overall pass:
- Reviewer:
- Comment:

## G044

- Category: combined
- Latency: 3138.26 ms
- HCX invoked/success: True / True

### Question

교직원인데 명퇴수당 1억원을 IRP에 넣으면 무조건 절세되나요?

### Answer

[주의] 큰 폭의 절세 효과가 있다고 일률적으로 단정하기보다 수당의 성격과 적용 조건을 먼저 확인해야 합니다. 제공된 교사·공무원 안내에 따르면 퇴직수당과 명예퇴직수당은 퇴직소득이며, 명예퇴직수당 전액은 퇴직소득세 과세대상입니다. 세후 수령 후 60일 이내에 연금저축 또는 IRP에 입금하고 퇴직소득세 환급을 신청할 수 있습니다. 실제 적용 여부는 수당의 법적 성격과 개인별 요건을 확인해야 합니다.

### Retrieved context

- 공무원은 퇴직할 때 퇴직연금 월지급식을 가장 많이 선택한다. 종신까지 매월 공무원연금을 받을 수 있기 때문이다. 이 외에도 근무기간에 따라 퇴직수당과 정년 전 퇴직일 경우 명예퇴직수당을 일시금으로 지급받게 된다. 퇴직수당과 명예퇴직수당은 퇴직소득이다. 퇴직소득세 차감 후 일반계좌로 받게 되는데 세후로 퇴직소득을 받은 경우 60일 내에 연금저축계좌나 IRP로 입금할 수 있다. 공무원연금공단 등 담당부서로 퇴직소득세 환급을 신청해서 차감됐던 세금을 다시 돌려받으면 퇴직수당과 명예퇴직수당은 세전으로 연금계좌에 입금된 것과 동일하게 된다.
- 60일 이내에 과세이연 신청을 하게 되면 퇴직소득세 환급의 업무가 발생
- 주의할 점이 있다. 이 감면은 퇴직소득에서 발생한 퇴직소득세에만 적용된다. 연금계좌 내에서 세액공제를 받은 납입금과 운용수익에는 연금소득세(3.3% ~ 5.5%)가 별도로 적용된다. 두 가지 세금이 섞이지 않도록 연금계좌 내 재원이 어떻게 구성되어 있는지 파악해두는 것이 중요하다.
- 공무원 · 교사 퇴직수당(명퇴수당) 연금계좌 절세 안내
- 퇴직수당으로 수령 받은 금액 중 일부 금액은 연금계좌로 입금이 안될 수 있다. 퇴직수당은 입사일부터 퇴직일까지 쌓인 금액인데 2002년을 기점으로 그 전 기여분은 비과세되고 이후 기여분만 퇴직소득 과세 대상이다. 2002년 전 입사자인 경우 퇴직수당 중 일부는 비과세되는데, 퇴직소득으로 과세되는 금액만 연금계좌로 입금할 수 있다. 퇴직소득 원천징수영수증에 적힌 세후 금액을 확인해서 그 금액만 연금계좌로 입금해야 한다. 명예퇴직수당은 전액이 퇴직소득세 과세대상이어서 세후 금액 전액을 연금계좌로 입금할 수 있다.

### Human checks

- Accuracy:
- Evidence completeness:
- Requirement coverage:
- Groundedness:
- Reasoning:
- Safety:
- Limit handling:
- Unsupported claim found:
- Wrong number found:
- Wrong evidence found:
- Overconfident recommendation:
- Unnecessary clarification:
- Overall pass:
- Reviewer:
- Comment:

## G047

- Category: combined
- Latency: 11919.544 ms
- HCX invoked/success: True / True

### Question

DB와 DC 급여 차이 및 퇴직 후 IRP 이전을 한 번에 설명해줘

### Answer

[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다.

### Retrieved context

- ① 일시금으로 퇴직금을 수령한 퇴직자가 수령일 기준 60일 이내에 세후 퇴직급여를 IRP계좌로 입금
- 원리금보장형 상품을 DC에서 퇴직급여지급 신청 시 특별중도해지1)가 적용되고, DC에서 IRP로 현물이전 후 중도해지 시 중도해지이자율이 적용됩니다.
- - 퇴직급여신청서에 대한 검토를 마친 후 지급업무를 수행, 지급금액을 IRP계좌로 송금.
- - 신청한 서류의 내용 확인 → 퇴직급여신청서와 IRP 가입확인서를 퇴직연금사업자에 제출
- ③ 사내대출이 있는 경우에도 DC 퇴직급여는 IRP로 전액 지급되어야 함(IRP 송금위임 활용)

### Human checks

- Accuracy:
- Evidence completeness:
- Requirement coverage:
- Groundedness:
- Reasoning:
- Safety:
- Limit handling:
- Unsupported claim found:
- Wrong number found:
- Wrong evidence found:
- Overconfident recommendation:
- Unnecessary clarification:
- Overall pass:
- Reviewer:
- Comment:

## G053

- Category: combined
- Latency: 5536.128 ms
- HCX invoked/success: True / True

### Question

퇴직금 100억원, 세금 20억원의 결과와 계산 근거를 보여줘

### Answer

Rule Result에 포함된 수령 시나리오별 퇴직소득세입니다.
- lump_sum: 퇴직소득세 2000000000KRW, 적용 비율 1.0
- annuity_10_years: 퇴직소득세 1400000000KRW, 적용 비율 0.7
- annuity_21_plus_years: 퇴직소득세 1000000000KRW, 적용 비율 0.5

### Retrieved context

- 퇴직금 일시수령과 연금계좌 입금 후 연금수령에 대한 세금 차이
- • 회사가 원천징수의무자로 세금계산, 원천징수영수증작성, 지급명세서 신고 등 모든 세금관련 업무 직접 처리. ‘퇴직소득원천징수영수증’ 작성하여 퇴직 신청 시 DC 사업자에 퇴직급여신청서와 함께 송부         → DC 사업자는 ‘세액정산’ 의무 수행
- 연금계좌 세액공제는 연말정산 세금이 정해지면 그 금액에서 세액공제액만큼 직접 차감해서 세금이 줄이는 방식이다. 연금계좌 세액공제액은 납입한 금액에 세액공제율 16.5% 또는 13.2%를 곱해서 계산한다. 소득에 따라 차등 적용되는데 소득이 낮으면 세액공제율이 더 높다. 직장인은 총급여 5,500만원, 종합소득이 있으면 종합소득금액 4,500만원이 기준이 되는데 그 금액 이하면 16.5%, 초과하면 13.2%가 적용된다. 세액공제 납입한도인 연900만원까지 납입하면 최대 148만 5천만원(=900만원 x 16.5%) 세금을 줄일 수 있다. 차감할 세금이 있으면 최대 금액까지 세액공제되지만 애초에 납부할 세금이 작으면 세액공제액도 그 금액만큼 줄어든다.
- 연금계좌에 퇴직금을 넣어두면 그 안에서 운용되는 수익에 대해 연금을 받기 전까지는 세금이 부과되지 않는다. 이를 ‘과세이연’이라고 한다. 세금을 떼지 않은 원금 전체가 복리로 굴러간다. 같은 수익률이라도 세금을 중간에 떼는 것과 떼지 않고 굴리다 나중에 한 번 내는 것의 차이는 기간이 길수록 크게 벌어진다. 그리고 연금을 받을 때 연금소득세는 5.5%~3.3%만 내면 된다. 이 세율은 금융소득세(15.4%)의 3분의1 수준이다.
- 법정퇴직금은 근퇴법에서 의무적으로 지급하도록 정한 퇴직금이다. 이 금액은 반드시 IRP로만 이전할 수 있다. 반면, 법정외퇴직금은 회사가 내부 규정에 따라 법정기준을 초과해 추가로 지급하는 퇴직금이다. 이 금액은 IRP뿐아니라 연금저축에도 입금할 수 있다.
- 일시금으로 받으면 퇴직소득세를 100% 즉시 납부해야한다. 이후 남은 돈을 금융상품에 운용하면 발생하는 이자·배당은 금융소득으로 과세되고, 금융소득 종합과세 기준(연 2,000만원)에 포함된다. 또한 이자·배당이 연 1,000만원을 초과한다면 건강보험료 부과 대상 소득에 포함되어 건강보험료에 영향을 준다. 반면 연금으로 받으면 세 가지 혜택이 동시에 생긴다. 퇴직소득세를 30% ~ 50% 감면받고, IRP 내 운용수익은 연금을 받을 때까지 과세가 이연되며, 사적연금소득은 건강보험료 산정에서 제외된다. 먼저 이 차이를 한눈에 파악하자.
- 연금으로 받으면 퇴직소득세가 30% ~ 50% 감면된다는 말은, 원래 납부했어야 할 퇴직소득세의 일부만 내도 된다는 뜻이다. 이 감면율은 연금을 수령하는 기간에 따라 달라진다. 1 ~ 10년차에는 30% 감면(이연퇴직소득세율의 70% 납부), 11년차 ~ 20년차에는 40% 감면(이연퇴직소득세율의 60% 납부), 21년차부터는 50% 감면(이연퇴직소득세율의 50% 납부)이 적용된다. 오래 나눠 받을수록 세금이 더 줄어드는 구조다.

### Human checks

- Accuracy:
- Evidence completeness:
- Requirement coverage:
- Groundedness:
- Reasoning:
- Safety:
- Limit handling:
- Unsupported claim found:
- Wrong number found:
- Wrong evidence found:
- Overconfident recommendation:
- Unnecessary clarification:
- Overall pass:
- Reviewer:
- Comment:
