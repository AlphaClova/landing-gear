import type { MoneyValue, WithdrawalDecisionInput, WithdrawalDecisionViewModel, WithdrawalOptionResult } from './withdrawal-decision-view-model'

// 이 데이터는 인출 의사결정 UI 검증용 예시이며 실제 세금 또는 연금 계산 결과가 아니다. 실제 연결 시 Rule Engine 응답으로 교체한다.
export const exampleWithdrawalInput: WithdrawalDecisionInput = {
  retirementBenefitAmount: 200000000,
  currentAge: 55,
  pensionStartAge: 60,
  desiredMonthlyIncome: null,
  expectedReturnRate: 2,
  otherPensionIncome: null,
  otherFinancialIncome: null,
  healthInsuranceStatus: 'unknown',
}

const exact = (amount: number, label: string): MoneyValue => ({ amount, currency: 'KRW', basis: 'exact', label })
const scenario = (amount: number, label: string): MoneyValue => ({ amount, currency: 'KRW', basis: 'scenario', label })
const unavailable = (label: string): MoneyValue => ({ amount: null, currency: 'KRW', basis: 'unavailable', label })
const healthImpact = { basis: 'conditional', status: 'unavailable', amount: null, description: '건강보험 자격과 다른 소득 정보가 없어 정확한 영향을 계산할 수 없습니다.' } as const
const financialImpact = { basis: 'conditional', status: 'possible', amount: null, description: '다른 금융소득과 수령 구조에 따라 과세 영향이 달라질 수 있습니다.' } as const

const options: WithdrawalOptionResult[] = [
  {
    id: 'lump_sum', label: '일시금', periodLabel: '한 번에 수령',
    confirmedAfterTaxAmount: exact(180000000, '확정 세후금액'),
    estimatedTotalCashflow: exact(180000000, '총 현금흐름'),
    estimatedMonthlyCashflow: unavailable('월 현금흐름'),
    retirementIncomeTax: exact(20000000, '퇴직소득세'),
    pensionTaxEffect: exact(0, '연금 수령 세금 효과'),
    healthInsuranceImpact: healthImpact, financialIncomeTaxImpact: financialImpact,
    differenceFromBaseline: null,
    reasons: ['한 번에 수령하는 방식', '연금 수령에 따른 세금 감면을 적용하지 않은 예시'],
    cautions: ['UI 검증용 예시이며 실제 계산 결과가 아닙니다.'], evidenceIds: [],
  },
  {
    id: 'pension_10y', label: '10년 연금', periodLabel: '10년 분할 수령',
    confirmedAfterTaxAmount: exact(186000000, '확정 세후금액'),
    estimatedTotalCashflow: scenario(205000000, '예상 총 현금흐름'),
    estimatedMonthlyCashflow: scenario(1708333, '예상 월 현금흐름'),
    retirementIncomeTax: exact(14000000, '퇴직소득세'),
    pensionTaxEffect: exact(6000000, '연금 수령 세금 효과'),
    healthInsuranceImpact: healthImpact, financialIncomeTaxImpact: financialImpact,
    differenceFromBaseline: exact(6000000, '일시금 대비 확정 세후금액 차이'),
    reasons: ['분할 수령 기간을 반영한 예시', '가정 기반 예상 현금흐름 포함'],
    cautions: ['UI 검증용 예시이며 실제 계산 결과가 아닙니다.'], evidenceIds: [],
  },
  {
    id: 'pension_21y_plus', label: '21년 이상 연금', periodLabel: '21년 이상 분할 수령',
    confirmedAfterTaxAmount: exact(190000000, '확정 세후금액'),
    estimatedTotalCashflow: scenario(225000000, '예상 총 현금흐름'),
    estimatedMonthlyCashflow: scenario(892857, '예상 월 현금흐름'),
    retirementIncomeTax: exact(10000000, '퇴직소득세'),
    pensionTaxEffect: exact(10000000, '연금 수령 세금 효과'),
    healthInsuranceImpact: healthImpact, financialIncomeTaxImpact: financialImpact,
    differenceFromBaseline: exact(10000000, '일시금 대비 확정 세후금액 차이'),
    reasons: ['장기 분할 수령을 반영한 예시', '예상수익률 가정의 영향이 더 길게 반영됨'],
    cautions: ['UI 검증용 예시이며 실제 계산 결과가 아닙니다.'], evidenceIds: [],
  },
]

const displayAmount = (amount: number | null) => amount === null ? '미입력' : amount === 200000000 ? '2억원' : `${new Intl.NumberFormat('ko-KR').format(amount)}원`
const insuranceLabels: Record<WithdrawalDecisionInput['healthInsuranceStatus'], string> = { employee: '직장가입자', regional: '지역가입자', dependent: '피부양자', unknown: '미확인' }

const base = (input: WithdrawalDecisionInput): Omit<WithdrawalDecisionViewModel, 'status' | 'summary' | 'limitations' | 'missingFields' | 'options' | 'canCompare' | 'canRetry'> => ({
  scenarioTitle: '퇴직급여 수령 방식 비교', input, assumptions: [
    { id: 'benefit', label: '퇴직급여 예상액', value: displayAmount(input.retirementBenefitAmount), source: 'user', editable: true },
    { id: 'age', label: '현재 나이', value: input.currentAge === null ? '미입력' : `${input.currentAge}세`, source: 'user', editable: true },
    { id: 'start-age', label: '연금 수령 시작 나이', value: input.pensionStartAge === null ? '미입력' : `${input.pensionStartAge}세`, source: 'user', editable: true },
    { id: 'return', label: '예상수익률', value: input.expectedReturnRate === null ? '미입력' : `연 ${input.expectedReturnRate}%`, source: 'scenario', editable: true },
    { id: 'insurance', label: '건강보험 자격', value: insuranceLabels[input.healthInsuranceStatus], source: 'user', editable: true },
    { id: 'rule-engine', label: '세금 계산 기준', value: 'Rule Engine 결과 연결 예정', source: 'rule', editable: false },
  ], evidence: [], baselineOptionId: 'lump_sum', highlightedOptionId: null, highlightReason: null,
})

export function createCompleteWithdrawalFixture(input: WithdrawalDecisionInput): WithdrawalDecisionViewModel {
  return { ...base(input), status: 'complete', summary: '확정 조건으로 계산한 금액과 가정을 사용한 예상 현금흐름을 분리해 보여드립니다.', limitations: ['건강보험료와 금융소득 과세 영향은 추가 조건에 따라 달라질 수 있습니다.'], missingFields: [], options, canCompare: true, canRetry: false }
}

export function createNeedsInputFixture(input: WithdrawalDecisionInput, missingFields: Array<keyof WithdrawalDecisionInput>): WithdrawalDecisionViewModel {
  return { ...base(input), status: 'needs_input', summary: '수령 방식의 일반적인 차이는 안내할 수 있지만 금액 비교를 위해 추가 조건이 필요합니다.', limitations: ['정확한 세후금액 비교를 위해 추가 조건이 필요합니다.'], missingFields, options: [], canCompare: false, canRetry: false }
}

export function createLimitedFixture(input: WithdrawalDecisionInput): WithdrawalDecisionViewModel {
  const limitedOptions = options.map((option) => ({ ...option, estimatedTotalCashflow: unavailable('예상 총 현금흐름'), estimatedMonthlyCashflow: unavailable('예상 월 현금흐름') }))
  return { ...base(input), status: 'limited', summary: '확정 조건의 비교는 가능하지만 예상 현금흐름은 현재 가정으로 계산할 수 없습니다.', limitations: ['예상수익률 가정을 확인해 주세요.'], missingFields: [], options: limitedOptions, canCompare: true, canRetry: false }
}

export function createErrorFixture(input: WithdrawalDecisionInput): WithdrawalDecisionViewModel {
  return { ...base(input), status: 'error', summary: '비교 결과를 불러오지 못했습니다.', limitations: [], missingFields: [], options: [], canCompare: false, canRetry: true }
}
