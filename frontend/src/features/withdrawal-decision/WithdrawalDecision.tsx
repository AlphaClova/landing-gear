interface WithdrawalDecisionProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled: boolean
}

export function WithdrawalDecision({ value, onChange, onSubmit, disabled }: WithdrawalDecisionProps) {
  return (
    <section className="feature-panel compact-feature">
      <span className="eyebrow">인출 의사결정</span>
      <h1>수령 방식의 차이를 같은 기준으로 비교해 보세요.</h1>
      <p className="lead">판단에 필요한 조건을 확인한 뒤 비교 결과와 근거를 구분해 보여드립니다.</p>
      <div className="prompt-box"><label htmlFor="withdrawal-question">인출 의사결정 질문</label><textarea id="withdrawal-question" value={value} onChange={(event) => onChange(event.target.value)} placeholder="비교하려는 퇴직급여 인출 상황을 설명해 주세요." rows={3} /><button onClick={onSubmit} disabled={disabled || !value.trim()}>비교 시작</button></div>
      <ol className="decision-steps" aria-label="의사결정 흐름"><li><b>1</b><span>조건 입력</span></li><li><b>2</b><span>수령 방식 비교</span></li><li><b>3</b><span>차이 발생 이유</span></li><li><b>4</b><span>확인할 조건</span></li><li><b>5</b><span>근거와 출처</span></li></ol>
    </section>
  )
}
