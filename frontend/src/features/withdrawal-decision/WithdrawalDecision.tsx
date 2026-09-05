import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { PageHeader, StatusBadge } from '../../components/ui'
import { ApiNetworkError, ApiTimeoutError } from '../../api/errors'
import { isMockWithdrawalMode, requestWithdrawalDecision } from './withdrawal-decision-adapter'
import { exampleWithdrawalInput } from './withdrawal-decision-mock'
import type { CalculationBasis, MoneyValue, WithdrawalDecisionInput, WithdrawalDecisionViewModel } from './withdrawal-decision-view-model'

const emptyInput: WithdrawalDecisionInput = { retirementBenefitAmount: null, expectedTaxWon: null, currentAge: null, pensionStartAge: null, desiredMonthlyIncome: null, expectedReturnRate: null, otherPensionIncome: null, otherFinancialIncome: null, healthInsuranceStatus: 'unknown' }
const fieldLabels: Record<keyof WithdrawalDecisionInput, string> = { retirementBenefitAmount: '퇴직급여 예상액', expectedTaxWon: '감면 전 기준 퇴직소득세', currentAge: '현재 나이', pensionStartAge: '연금 수령 시작 나이', desiredMonthlyIncome: '원하는 월 수령액', expectedReturnRate: '예상수익률', otherPensionIncome: '다른 연금소득', otherFinancialIncome: '다른 금융소득', healthInsuranceStatus: '건강보험 자격' }
const basisLabel: Record<CalculationBasis, string> = { exact: '확정 계산', scenario: '가정 기반 예상', conditional: '조건부 영향', unavailable: '계산 불가' }
const won = new Intl.NumberFormat('ko-KR')
const formatMoney = (money: MoneyValue, monthly = false) => money.amount === null ? '계산할 수 없음' : `${monthly ? '월 ' : ''}${won.format(money.amount)}원`
const formatRate = (rate: number | undefined) => rate === undefined ? '확인할 수 없음' : `${rate * 100}%`
const formatTaxSaving = (money: MoneyValue | undefined) => {
  if (!money || money.amount === null) return '확인할 수 없음'
  return money.amount === 0 ? '기준 (0원)' : `${won.format(money.amount)}원 절감`
}
const formatFormula = (formula: string, result: MoneyValue) => {
  const match = formula.match(/^\s*(\d+)\s*\*\s*(\d+(?:\.\d+)?)\s*$/)
  if (!match || result.amount === null) return formula
  const baseAmount = Number(match[1])
  const rate = Number(match[2])
  if (!Number.isSafeInteger(baseAmount) || !Number.isFinite(rate)) return formula
  return `${won.format(baseAmount)}원 × ${rate * 100}% = ${won.format(result.amount)}원`
}
const inputNumber = (value: string) => value === '' ? null : Number(value)
const expectedTaxHelp = (value: number | null, invalid: boolean) => {
  if (!invalid) return value === null ? '일시금 수령 시 기준이 되는 퇴직소득세를 입력해 주세요.' : `${won.format(value)}원`
  if (value === null) return '필수 입력입니다. 일시금 수령 시 기준이 되는 퇴직소득세를 입력해 주세요.'
  return '0원 이상의 정수 금액을 원 단위로 입력해 주세요.'
}

function BasisBadge({ basis }: { basis: CalculationBasis }) { return <span className={`basis-badge basis-badge--${basis}`}>{basisLabel[basis]}</span> }

export function WithdrawalDecision() {
  const [input, setInput] = useState<WithdrawalDecisionInput>(emptyInput)
  const [viewModel, setViewModel] = useState<WithdrawalDecisionViewModel | null>(null)
  const [loading, setLoading] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const [additionalOpen, setAdditionalOpen] = useState(false)
  const requestRef = useRef<AbortController | null>(null)
  const resultRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => () => requestRef.current?.abort(), [])
  useEffect(() => {
    if (!viewModel) return
    window.requestAnimationFrame(() => {
      if (viewModel.status === 'needs_input') {
        document.querySelector<HTMLElement>('.withdrawal-fields [aria-invalid="true"]')?.focus()
      } else {
        resultRef.current?.focus({ preventScroll: true })
      }
    })
  }, [viewModel])

  const update = <K extends keyof WithdrawalDecisionInput>(key: K, value: WithdrawalDecisionInput[K]) => setInput((current) => ({ ...current, [key]: value }))
  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    if (loading) return
    const controller = new AbortController()
    requestRef.current?.abort(); requestRef.current = controller
    setLoading(true); setCancelled(false)
    try { setViewModel(await requestWithdrawalDecision(input, controller.signal)) }
    catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        const summary = error instanceof ApiTimeoutError
          ? '응답 시간이 초과되었습니다. 입력한 조건을 유지한 채 다시 시도할 수 있습니다.'
          : error instanceof ApiNetworkError
            ? '네트워크 연결을 확인한 뒤 다시 시도해 주세요.'
            : emptyErrorViewModel.summary
        setViewModel({ ...emptyErrorViewModel, input, summary })
      }
    }
    finally { if (requestRef.current === controller) { requestRef.current = null; setLoading(false) } }
  }
  const cancel = () => { requestRef.current?.abort(); requestRef.current = null; setLoading(false); setCancelled(true) }
  const missing = new Set(viewModel?.status === 'needs_input' ? viewModel.missingFields : [])
  const hasResult = Boolean(viewModel && (viewModel.status === 'complete' || viewModel.status === 'limited'))

  return <section className="withdrawal-slice" aria-labelledby="withdrawal-title">
    <PageHeader label="인출 의사결정" title="수령 방식을 비교해 보세요" description="확정 계산과 가정 기반 예상 결과를 구분해 확인할 수 있습니다." titleId="withdrawal-title" />

    <details className="withdrawal-input-panel" open={!hasResult || undefined}><summary>{hasResult ? '입력 조건 확인·수정' : '비교 조건 입력'}</summary><form onSubmit={submit} noValidate>
      {viewModel?.status === 'needs_input' && <div className="withdrawal-input-alert" role="alert"><strong>{viewModel.summary}</strong><p>부족한 조건: {viewModel.missingFields.map((field) => fieldLabels[field]).join(', ')}</p></div>}
      <div className="withdrawal-fields">
        <label className={missing.has('retirementBenefitAmount') ? 'field-error' : ''}><span>퇴직급여 예상액</span><input type="number" min="0" inputMode="numeric" required aria-required="true" value={input.retirementBenefitAmount ?? ''} onChange={(e) => update('retirementBenefitAmount', inputNumber(e.target.value))} aria-invalid={missing.has('retirementBenefitAmount')} aria-describedby="retirement-benefit-help" /><small id="retirement-benefit-help">{missing.has('retirementBenefitAmount') ? '필수 입력입니다. ' : ''}{input.retirementBenefitAmount === null ? '원 단위로 입력' : `${won.format(input.retirementBenefitAmount)}원`}</small></label>
        <label className={missing.has('expectedTaxWon') ? 'field-error' : ''} htmlFor="expected-tax-won"><span>감면 전 기준 퇴직소득세</span><input id="expected-tax-won" type="number" min="0" step="1" inputMode="numeric" required aria-label="감면 전 기준 퇴직소득세" aria-required="true" value={input.expectedTaxWon ?? ''} onChange={(e) => update('expectedTaxWon', inputNumber(e.target.value))} aria-invalid={missing.has('expectedTaxWon')} aria-describedby="expected-tax-won-help" /><small id="expected-tax-won-help">{expectedTaxHelp(input.expectedTaxWon, missing.has('expectedTaxWon'))}</small></label>
        <label className={missing.has('currentAge') ? 'field-error' : ''}><span>현재 나이</span><input type="number" min="0" required aria-required="true" value={input.currentAge ?? ''} onChange={(e) => update('currentAge', inputNumber(e.target.value))} aria-invalid={missing.has('currentAge')} aria-describedby="current-age-help" /><small id="current-age-help">{missing.has('currentAge') ? '필수 입력입니다. ' : ''}세 단위로 입력</small></label>
        <label className={missing.has('pensionStartAge') ? 'field-error' : ''}><span>연금 수령 시작 나이</span><input type="number" min="0" required aria-required="true" value={input.pensionStartAge ?? ''} onChange={(e) => update('pensionStartAge', inputNumber(e.target.value))} aria-invalid={missing.has('pensionStartAge')} aria-describedby="pension-start-age-help" /><small id="pension-start-age-help">{missing.has('pensionStartAge') ? '필수 입력입니다. ' : ''}세 단위로 입력</small></label>
        <label><span>건강보험 자격</span><select value={input.healthInsuranceStatus} onChange={(e) => update('healthInsuranceStatus', e.target.value as WithdrawalDecisionInput['healthInsuranceStatus'])}><option value="employee">직장가입자</option><option value="regional">지역가입자</option><option value="dependent">피부양자</option><option value="unknown">잘 모르겠어요</option></select></label>
      </div>
      <button className="withdrawal-more" type="button" aria-expanded={additionalOpen} onClick={() => setAdditionalOpen((open) => !open)}>추가 조건 입력</button>
      {additionalOpen && <div className="withdrawal-fields withdrawal-fields--additional">
        <label><span>원하는 월 수령액</span><input type="number" min="0" inputMode="numeric" value={input.desiredMonthlyIncome ?? ''} onChange={(e) => update('desiredMonthlyIncome', inputNumber(e.target.value))} /><small>{input.desiredMonthlyIncome === null ? '원 단위로 입력' : `${won.format(input.desiredMonthlyIncome)}원`}</small></label>
        <label><span>예상수익률</span><input type="number" step="0.1" value={input.expectedReturnRate ?? ''} onChange={(e) => update('expectedReturnRate', inputNumber(e.target.value))} /><small>% · 결과를 프론트에서 재계산하지 않습니다.</small></label>
        <label><span>다른 연금소득</span><input type="number" min="0" inputMode="numeric" value={input.otherPensionIncome ?? ''} onChange={(e) => update('otherPensionIncome', inputNumber(e.target.value))} /><small>원</small></label>
        <label><span>다른 금융소득</span><input type="number" min="0" inputMode="numeric" value={input.otherFinancialIncome ?? ''} onChange={(e) => update('otherFinancialIncome', inputNumber(e.target.value))} /><small>원</small></label>
      </div>}
      <div className="withdrawal-form-actions">{isMockWithdrawalMode && <button type="button" className="secondary-button" onClick={() => { setInput(exampleWithdrawalInput); setAdditionalOpen(true) }}>예시 조건 불러오기</button>}<button type="submit" className="button" disabled={loading}>{loading ? '비교 중' : hasResult ? '조건을 바꿔 다시 비교' : '수령 방식 비교하기'}</button></div>
    </form></details>

    {loading && <section className="withdrawal-loading" role="status" aria-busy="true"><div aria-hidden="true"><i /><i /><i /></div><strong>비교 결과를 준비하고 있습니다</strong><button type="button" onClick={cancel}>요청 취소</button></section>}
    {cancelled && !loading && <p className="withdrawal-notice" role="status">요청을 취소했습니다. 입력한 조건은 유지됩니다.</p>}
    {viewModel && <div ref={resultRef} className="focus-target" tabIndex={-1} aria-label="비교 결과" aria-busy={loading || undefined}>{!loading && viewModel.status !== 'error' && viewModel.status !== 'needs_input' && <p className="sr-only" role="status">비교 결과가 준비되었습니다.</p>}<WithdrawalResult viewModel={viewModel} onRetry={submit} /></div>}
  </section>
}

const emptyErrorViewModel: WithdrawalDecisionViewModel = { status: 'error', scenarioTitle: '퇴직급여 수령 방식 비교', input: emptyInput, missingFields: [], summary: '비교 결과를 불러오지 못했습니다.', limitations: [], options: [], assumptions: [], evidence: [], baselineOptionId: null, highlightedOptionId: null, highlightReason: null, canCompare: false, canRetry: true }

function WithdrawalResult({ viewModel, onRetry }: { viewModel: WithdrawalDecisionViewModel; onRetry: () => void }) {
  if (viewModel.status === 'needs_input') return null
  if (viewModel.status === 'error') return <section className="withdrawal-state withdrawal-state--amber" role="alert"><h2>{viewModel.summary}</h2>{viewModel.diagnosticCode && <p className="withdrawal-diagnostic-code">오류 코드: {viewModel.diagnosticCode}</p>}{viewModel.canRetry && <button className="secondary-button" onClick={onRetry}>다시 시도</button>}</section>

  const hasEstimatedCashflow = viewModel.options.some((option) => option.estimatedTotalCashflow.amount !== null || option.estimatedMonthlyCashflow.amount !== null)
  const healthInsuranceDescriptions = [...new Set(viewModel.options.map((option) => option.healthInsuranceImpact.description))]
  const financialIncomeTaxDescriptions = [...new Set(viewModel.options.map((option) => option.financialIncomeTaxImpact.description))]
  const additionalChecks = [
    { label: '건강보험료', descriptions: healthInsuranceDescriptions },
    { label: '금융소득 과세', descriptions: financialIncomeTaxDescriptions },
  ].filter((item) => item.descriptions.length > 0)
  const visibleLimitations = viewModel.limitations.filter((item) => !item.includes('건강보험') && !item.includes('금융소득 과세') && !item.includes('예상 현금흐름'))

  return <div className="withdrawal-results">
    <section className="withdrawal-summary"><div>{isMockWithdrawalMode && <StatusBadge tone="gold">예시 시나리오</StatusBadge>}<h2>수령 방식별 차이를 확인하세요</h2><p>{viewModel.summary}</p></div>{isMockWithdrawalMode && <small>현재 화면의 금액은 UI 검증용이며 실제 계산 결과가 아닙니다.</small>}</section>
    <section><h2 className="withdrawal-section-title">수령 방식 비교</h2><div className="withdrawal-option-cards">{viewModel.options.map((option) => <article key={option.id}><header><h3>{option.label}</h3><p>{option.periodLabel}</p></header><div className="option-primary"><BasisBadge basis={option.retirementIncomeTax.basis} /><span>퇴직소득세</span><strong>{formatMoney(option.retirementIncomeTax)}</strong><small>{formatTaxSaving(option.taxSavingFromLumpSum)}</small></div><dl><div><dt>적용 비율</dt><dd>{formatRate(option.applicableRate)}</dd></div></dl></article>)}</div></section>
    <section className="withdrawal-table-section"><h2 className="withdrawal-section-title">확정 계산 비교</h2><p className="table-scroll-hint">표를 좌우로 스크롤해 비교할 수 있습니다.</p><div className="withdrawal-table-scroll" tabIndex={0} role="region" aria-label="확정 계산 비교표, 좌우로 스크롤 가능"><table><thead><tr><th scope="col">항목</th>{viewModel.options.map((option) => <th scope="col" key={option.id}>{option.label}</th>)}</tr></thead><tbody><tr><th scope="row">퇴직소득세</th>{viewModel.options.map((option) => <td key={option.id}>{formatMoney(option.retirementIncomeTax)} <BasisBadge basis={option.retirementIncomeTax.basis} /></td>)}</tr><tr><th scope="row">적용 비율</th>{viewModel.options.map((option) => <td key={option.id}>{formatRate(option.applicableRate)}</td>)}</tr><tr><th scope="row">일시금 대비 세액 절감액</th>{viewModel.options.map((option) => <td key={option.id}>{formatTaxSaving(option.taxSavingFromLumpSum)}</td>)}</tr></tbody></table></div></section>
    {hasEstimatedCashflow && <section className="withdrawal-table-section"><h2 className="withdrawal-section-title">가정 기반 예상 현금흐름</h2><p className="table-scroll-hint">표를 좌우로 스크롤해 비교할 수 있습니다.</p><div className="withdrawal-table-scroll" tabIndex={0} role="region" aria-label="가정 기반 예상 현금흐름 표, 좌우로 스크롤 가능"><table><thead><tr><th scope="col">항목</th>{viewModel.options.map((option) => <th scope="col" key={option.id}>{option.label}</th>)}</tr></thead><tbody><tr><th scope="row">예상 총 현금흐름</th>{viewModel.options.map((option) => <td key={option.id}>{formatMoney(option.estimatedTotalCashflow)} <BasisBadge basis={option.estimatedTotalCashflow.basis} /></td>)}</tr><tr><th scope="row">예상 월 현금흐름</th>{viewModel.options.map((option) => <td key={option.id}>{formatMoney(option.estimatedMonthlyCashflow, true)}</td>)}</tr></tbody></table></div></section>}
    {viewModel.options.some((option) => option.reasons.length > 0) && <section className="withdrawal-reasons"><h2 className="withdrawal-section-title">차이가 발생한 이유</h2><div>{viewModel.options.filter((option) => option.reasons.length > 0).map((option) => <article key={option.id}><h3>{option.label}</h3><ul>{option.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></article>)}</div></section>}
    {viewModel.options.some((option) => option.cautions.length > 0) && <section className="withdrawal-cautions"><h2 className="withdrawal-section-title">주의사항</h2><ul>{viewModel.options.flatMap((option) => option.cautions).map((caution) => <li key={caution}>{caution}</li>)}</ul></section>}
    {additionalChecks.length > 0 && <section className="withdrawal-additional-checks"><h2 className="withdrawal-section-title">추가 확인 사항</h2>{additionalChecks.map((item) => <article key={item.label}><BasisBadge basis="conditional" /><h3>{item.label}</h3>{item.descriptions.map((description) => <p key={description}>{description}</p>)}</article>)}</section>}
    {visibleLimitations.length > 0 && <section className="withdrawal-state withdrawal-state--amber"><h2>확인할 조건</h2><ul>{visibleLimitations.map((item) => <li key={item}>{item}</li>)}</ul></section>}
    {viewModel.assumptions.length > 0 && <section className="withdrawal-assumptions"><h2 className="withdrawal-section-title">적용된 가정</h2><dl>{viewModel.assumptions.map((item) => <div key={item.id}><dt>{item.label}</dt><dd>{item.value}<span>{item.source === 'scenario' ? '시나리오' : item.source === 'rule' ? '규칙' : '사용자 입력'}</span></dd></div>)}</dl></section>}
    <section className="withdrawal-calculation-details"><h2 className="withdrawal-section-title">계산 근거</h2><div>{viewModel.options.filter((option) => option.formula && option.ruleId && option.ruleVersion).map((option) => <article key={option.id}><h3>{option.label}</h3><dl><div><dt>계산식</dt><dd>{formatFormula(option.formula!, option.retirementIncomeTax)}</dd></div><div><dt>적용 Rule</dt><dd>{option.ruleId} · v{option.ruleVersion}</dd></div></dl></article>)}</div></section>
    {viewModel.evidence.length === 0
      ? <section className="withdrawal-evidence-empty"><h2 className="withdrawal-section-title">근거와 출처</h2><p>계산 근거가 제공되면 이곳에서 확인할 수 있습니다.</p></section>
      : <section className="withdrawal-evidence"><h2 className="withdrawal-section-title">근거와 출처</h2><div>{viewModel.evidence.map((evidence) => <article key={evidence.id}><header>{evidence.organization && <span>{evidence.organization}</span>}<h3>{evidence.title}</h3><p>{evidence.documentId ?? evidence.location}{evidence.page !== null && evidence.page !== undefined && <span> · p.{evidence.page}</span>}</p></header><blockquote>{evidence.summary}</blockquote>{evidence.url && <a href={evidence.url} target="_blank" rel="noreferrer">원문 보기</a>}</article>)}</div></section>}
    <a className="withdrawal-edit-link" href="#withdrawal-title">조건 수정하기</a>
  </div>
}
