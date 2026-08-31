import type {
  ChatApiResponseTransport,
  ChatApiWithdrawalResult,
  ChatApiWithdrawalScenario,
} from '../../api/chat-response'
import type {
  ConditionalImpact,
  MoneyValue,
  WithdrawalDecisionInput,
  WithdrawalDecisionViewModel,
  WithdrawalEvidence,
  WithdrawalOptionId,
  WithdrawalOptionResult,
} from './withdrawal-decision-view-model'
import { validateWithdrawalDecisionViewModel } from './withdrawal-decision-validator'

export class WithdrawalChatAdapterError extends Error {
  constructor(reason: string) {
    super(`Withdrawal chat response adaptation failed: ${reason}`)
    this.name = 'WithdrawalChatAdapterError'
  }
}

const presentation: Record<ChatApiWithdrawalScenario['scenario'], {
  id: WithdrawalOptionId
  label: string
  periodLabel: string
}> = {
  lump_sum: { id: 'lump_sum', label: '일시금', periodLabel: '한 번에 수령' },
  annuity_10_years: { id: 'pension_10y', label: '10년 연금', periodLabel: '10년 분할 수령' },
  annuity_21_plus_years: { id: 'pension_21y_plus', label: '21년 이상 연금', periodLabel: '21년 이상 분할 수령' },
}

const unavailableMoney = (label: string): MoneyValue => ({ amount: null, currency: 'KRW', basis: 'unavailable', label })
const exactMoney = (amount: number, label: string): MoneyValue => ({ amount, currency: 'KRW', basis: 'exact', label })
const unavailableImpact = (description: string): ConditionalImpact => ({
  basis: 'unavailable', status: 'unavailable', amount: null, description,
})

const emptyViewModel = (input: WithdrawalDecisionInput): WithdrawalDecisionViewModel => ({
  status: 'limited',
  scenarioTitle: '퇴직급여 수령 방식 비교',
  input,
  missingFields: [],
  summary: '',
  limitations: [],
  options: [],
  assumptions: [],
  evidence: [],
  baselineOptionId: null,
  highlightedOptionId: null,
  highlightReason: null,
  canCompare: false,
  canRetry: false,
})

const slotFields: Record<string, keyof WithdrawalDecisionInput> = {
  retirement_amount_won: 'retirementBenefitAmount',
  expected_tax_won: 'expectedTaxWon',
  age: 'currentAge',
  current_age: 'currentAge',
  pension_start_age: 'pensionStartAge',
}

const validateWithdrawalResult = (result: ChatApiWithdrawalResult) => {
  const scenarioIds = result.comparison.scenarios.map((scenario) => scenario.scenario)
  const expected = Object.keys(presentation)
  if (scenarioIds.length !== expected.length || new Set(scenarioIds).size !== expected.length
    || expected.some((id) => !scenarioIds.includes(id as ChatApiWithdrawalScenario['scenario']))) {
    throw new WithdrawalChatAdapterError('withdrawal result must contain each supported scenario exactly once')
  }

  const evidenceIds = new Set(result.evidence.map((item) => item.evidence_id))
  for (const scenario of result.comparison.scenarios) {
    if (scenario.evidence_ids.some((id) => !evidenceIds.has(id))) {
      throw new WithdrawalChatAdapterError('scenario references unknown evidence')
    }
    if (!result.applied_rules.some((rule) => rule.rule_id === scenario.rule_id
      && (rule.rule_version === null || rule.rule_version === scenario.rule_version))) {
      throw new WithdrawalChatAdapterError('scenario rule is absent from applied_rules')
    }
  }

  const unsupported = result.claim_validation.validations.filter((item) => !item.supported).length
  const total = result.claim_validation.validations.length
  const expectedRate = total === 0 ? 0 : unsupported / total
  if (unsupported !== result.claim_validation.unsupported_claim_count
    || total !== result.claim_validation.validated_claim_count
    || Math.abs(expectedRate - result.claim_validation.unsupported_claim_rate) > 1e-9) {
    throw new WithdrawalChatAdapterError('claim validation counters are inconsistent')
  }
}

const mapScenario = (scenario: ChatApiWithdrawalScenario): WithdrawalOptionResult => ({
  ...presentation[scenario.scenario],
  confirmedAfterTaxAmount: unavailableMoney('확정 세후금액'),
  estimatedTotalCashflow: unavailableMoney('예상 총 현금흐름'),
  estimatedMonthlyCashflow: unavailableMoney('예상 월 현금흐름'),
  retirementIncomeTax: exactMoney(scenario.tax_value, '퇴직소득세'),
  pensionTaxEffect: exactMoney(scenario.difference_vs_lump_sum, '일시금 대비 퇴직소득세 절감액'),
  taxSavingFromLumpSum: exactMoney(scenario.difference_vs_lump_sum, '일시금 대비 퇴직소득세 절감액'),
  applicableRate: scenario.applicable_rate,
  healthInsuranceImpact: unavailableImpact('현재 계산에는 건강보험료 영향이 포함되지 않았습니다.'),
  financialIncomeTaxImpact: unavailableImpact('현재 계산에는 금융소득 과세 영향이 포함되지 않았습니다.'),
  differenceFromBaseline: null,
  reasons: [...scenario.assumptions],
  cautions: [...scenario.warnings],
  evidenceIds: [...new Set(scenario.evidence_ids)],
  formula: scenario.formula || undefined,
  ruleId: scenario.rule_id,
  ruleVersion: scenario.rule_version || undefined,
})

const mapEvidence = (result: ChatApiWithdrawalResult): WithdrawalEvidence[] => [
  ...new Map(result.evidence.map((item) => [item.evidence_id, item])).values(),
].map((item) => ({
  id: item.evidence_id,
  title: item.section ?? item.document_id,
  location: item.page === null ? item.document_id : `${item.document_id} · ${item.page}페이지`,
  summary: item.quote ?? '',
  claimIds: [],
  documentId: item.document_id,
  chunkId: item.chunk_id,
  page: item.page,
}))

const adaptResult = (
  result: ChatApiWithdrawalResult,
  input: WithdrawalDecisionInput,
  forceLimited = false,
): WithdrawalDecisionViewModel => {
  validateWithdrawalResult(result)
  const hasUnsupportedClaim = result.claim_validation.unsupported_claim_count > 0
  const limited = forceLimited || hasUnsupportedClaim
  return validateWithdrawalDecisionViewModel({
    ...emptyViewModel(input),
    status: limited ? 'limited' : 'complete',
    summary: limited
      ? '일부 근거를 충분히 확인하지 못해 계산 결과를 제한적으로 표시합니다.'
      : '확정된 퇴직소득세 계산 결과를 수령 방식별로 비교합니다.',
    limitations: limited ? ['일부 계산 근거를 추가로 확인해야 합니다.'] : [],
    options: result.comparison.scenarios.map(mapScenario),
    evidence: mapEvidence(result),
    baselineOptionId: 'lump_sum',
    canCompare: true,
  })
}

export function adaptChatApiWithdrawalResponse(
  response: ChatApiResponseTransport,
  input: WithdrawalDecisionInput,
): WithdrawalDecisionViewModel {
  const boundary = emptyViewModel(input)
  if (response.type === 'clarification') {
    const missingFields = [...new Set(response.required_slots
      .map((slot) => slotFields[slot.name])
      .filter((field): field is keyof WithdrawalDecisionInput => field !== undefined))]
    return validateWithdrawalDecisionViewModel({
      ...boundary,
      status: 'needs_input',
      summary: missingFields.length > 0
        ? '금액 비교를 위해 입력한 내용을 확인해 주세요.'
        : '비교를 위해 추가 정보가 필요합니다.',
      missingFields,
    })
  }
  if (response.type === 'error') {
    return validateWithdrawalDecisionViewModel({
      ...boundary, status: 'error', summary: '비교 결과를 불러오지 못했습니다.',
    })
  }
  if (response.withdrawal_result) return adaptResult(response.withdrawal_result, input, response.type === 'limitation')
  if (response.type === 'result') throw new WithdrawalChatAdapterError('result response is missing withdrawal_result')
  return validateWithdrawalDecisionViewModel({
    ...boundary,
    status: 'limited',
    summary: '현재 조건으로는 인출 비교 결과를 제공하기 어렵습니다.',
  })
}
