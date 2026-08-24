import { isMockApiEnabled, pensionApi } from '../../api'
import type { PensionApiClient } from '../../api'
import type { ChatResponse } from '../../types/api'
import { buildChatApiRequest } from '../../api/chat-request'
import type { ChatApiRequest } from '../../api/chat-request'
import type {
  ConditionalImpact,
  MoneyValue,
  WithdrawalAssumption,
  WithdrawalDecisionInput,
  WithdrawalDecisionViewModel,
  WithdrawalEvidence,
  WithdrawalOptionId,
  WithdrawalOptionResult,
} from './withdrawal-decision-view-model'
import { createErrorFixture, createLimitedFixture, createNeedsInputFixture, createUnavailableComparisonFixture, withdrawalComparisonTransportFixture } from './withdrawal-decision-mock'
import {
  isWithdrawalErrorResponse,
  parseWithdrawalTransportResponse,
  WithdrawalTransportValidationError,
} from './withdrawal-decision-transport'
import type {
  WithdrawalComparisonResponse,
  WithdrawalComparisonScenario,
  WithdrawalErrorResponse,
  WithdrawalEvidenceCitation,
} from './withdrawal-decision-transport'
import { validateWithdrawalDecisionViewModel } from './withdrawal-decision-validator'

export const isMockWithdrawalMode = isMockApiEnabled

const requiredFields: Array<keyof WithdrawalDecisionInput> = ['retirementBenefitAmount', 'expectedTaxWon', 'currentAge', 'pensionStartAge']

const isValidWonInput = (value: number | null) => Number.isSafeInteger(value) && (value ?? -1) >= 0

const invalidRequiredFields = (input: WithdrawalDecisionInput): Array<keyof WithdrawalDecisionInput> =>
  requiredFields.filter((field) => {
    if (field === 'retirementBenefitAmount' || field === 'expectedTaxWon') return !isValidWonInput(input[field])
    return input[field] === null
  })

const wait = (signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal.aborted) return reject(new DOMException('Request aborted', 'AbortError'))
  const timer = window.setTimeout(resolve, 900)
  signal.addEventListener('abort', () => { window.clearTimeout(timer); reject(new DOMException('Request aborted', 'AbortError')) }, { once: true })
})

export interface WithdrawalDecisionProvider {
  compare(input: WithdrawalDecisionInput, signal: AbortSignal): Promise<WithdrawalDecisionViewModel>
}

const scenarioPresentation: Record<WithdrawalComparisonScenario['scenario'], {
  id: WithdrawalOptionId
  label: string
  periodLabel: string
}> = {
  lump_sum: { id: 'lump_sum', label: '일시금', periodLabel: '한 번에 수령' },
  annuity_10_years: { id: 'pension_10y', label: '10년 연금', periodLabel: '10년 분할 수령' },
  annuity_21_plus_years: { id: 'pension_21y_plus', label: '21년 이상 연금', periodLabel: '21년 이상 분할 수령' },
}

const unavailableMoney = (label: string): MoneyValue => ({
  amount: null,
  currency: 'KRW',
  basis: 'unavailable',
  label,
})

const exactMoney = (amount: number, label: string): MoneyValue => ({
  amount,
  currency: 'KRW',
  basis: 'exact',
  label,
})

const unavailableImpact = (description: string): ConditionalImpact => ({
  basis: 'unavailable',
  status: 'unavailable',
  amount: null,
  description,
})

const assertStringItems = (items: unknown[], field: 'assumptions' | 'warnings'): string[] => {
  if (!items.every((item) => typeof item === 'string')) {
    throw new WithdrawalTransportValidationError(`${field} contains an unsupported non-string item`)
  }
  return items as string[]
}

const validateScenarioReferences = (response: WithdrawalComparisonResponse) => {
  const evidenceIds = new Set(response.evidence.map((item) => item.evidence_id))
  const appliedRules = new Set(response.applied_rules.map((rule) => `${rule.rule_id}\u0000${rule.rule_version}`))

  for (const scenario of response.comparison.scenarios) {
    const missingEvidenceId = scenario.evidence_ids.find((id) => !evidenceIds.has(id))
    if (missingEvidenceId) {
      throw new WithdrawalTransportValidationError(`scenario references unknown evidence: ${missingEvidenceId}`)
    }
    if (!appliedRules.has(`${scenario.rule_id}\u0000${scenario.rule_version}`)) {
      throw new WithdrawalTransportValidationError(`scenario rule is absent from applied_rules: ${scenario.rule_id}`)
    }
  }
}

const mapEvidence = (citation: WithdrawalEvidenceCitation): WithdrawalEvidence => ({
  id: citation.evidence_id,
  title: citation.section,
  location: citation.page === null
    ? citation.document_id
    : `${citation.document_id} · ${citation.page}페이지`,
  summary: citation.quote,
  claimIds: [],
  documentId: citation.document_id,
  chunkId: citation.chunk_id,
  page: citation.page,
})

const mapScenario = (scenario: WithdrawalComparisonScenario): WithdrawalOptionResult => {
  const presentation = scenarioPresentation[scenario.scenario]
  const assumptions = assertStringItems(scenario.assumptions, 'assumptions')
  const warnings = assertStringItems(scenario.warnings, 'warnings')

  return {
    ...presentation,
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
    reasons: assumptions,
    cautions: warnings,
    evidenceIds: [...scenario.evidence_ids],
    formula: scenario.formula,
    ruleId: scenario.rule_id,
    ruleVersion: scenario.rule_version,
  }
}

const mapComparisonResponse = (
  response: WithdrawalComparisonResponse,
  input: WithdrawalDecisionInput,
): WithdrawalDecisionViewModel => {
  validateScenarioReferences(response)
  const referencedEvidenceIds = new Set(response.comparison.scenarios.flatMap((scenario) => scenario.evidence_ids))
  const assumptions: WithdrawalAssumption[] = response.comparison.scenarios.flatMap((scenario) =>
    assertStringItems(scenario.assumptions, 'assumptions').map((value, index) => ({
      id: `${scenario.scenario}-assumption-${index}`,
      label: '계산 가정',
      value,
      source: 'rule' as const,
      editable: false,
    })))

  return {
    status: 'complete',
    scenarioTitle: '퇴직급여 수령 방식 비교',
    input,
    missingFields: [],
    summary: '확정된 퇴직소득세 계산 결과를 수령 방식별로 비교합니다.',
    limitations: ['예상 현금흐름, 건강보험 및 금융소득 과세 영향은 현재 계산 응답에 포함되지 않았습니다.'],
    options: response.comparison.scenarios.map(mapScenario),
    assumptions,
    evidence: response.evidence.filter((item) => referencedEvidenceIds.has(item.evidence_id)).map(mapEvidence),
    baselineOptionId: 'lump_sum',
    highlightedOptionId: null,
    highlightReason: null,
    canCompare: true,
    canRetry: false,
  }
}

const missingFieldsFromErrors = (response: WithdrawalErrorResponse): Array<keyof WithdrawalDecisionInput> => {
  const missing = new Set<keyof WithdrawalDecisionInput>()
  for (const error of response.errors) {
    if (error.api_error_family === 'MISSING_INPUT' && error.inputs.retirement_amount === null) {
      missing.add('retirementBenefitAmount')
    }
  }
  return [...missing]
}

const mapErrorResponse = (
  response: WithdrawalErrorResponse,
  input: WithdrawalDecisionInput,
): WithdrawalDecisionViewModel => {
  const hasRuleError = response.errors.some((error) => error.api_error_family === 'RULE_ERROR')
  const apiBoundary: WithdrawalDecisionViewModel = {
    status: hasRuleError ? 'error' : 'needs_input',
    scenarioTitle: '퇴직급여 수령 방식 비교',
    input,
    missingFields: hasRuleError ? [] : missingFieldsFromErrors(response),
    summary: hasRuleError
      ? '계산 규칙을 확인하지 못해 비교 결과를 제공할 수 없습니다.'
      : '금액 비교를 위해 추가 조건이 필요합니다.',
    limitations: hasRuleError ? [] : ['비교에 필요한 입력을 확인해 주세요.'],
    options: [],
    assumptions: [],
    evidence: [],
    baselineOptionId: null,
    highlightedOptionId: null,
    highlightReason: null,
    canCompare: false,
    canRetry: false,
  }
  return apiBoundary
}

/**
 * Pure B transport -> C view-model boundary.
 * TODO(A API contract): keep request-field mapping outside this function until
 * deferred_retirement_tax and the final /v1/chat envelope have canonical sources.
 */
export function adaptWithdrawalTransportResponse(
  payload: unknown,
  input: WithdrawalDecisionInput,
): WithdrawalDecisionViewModel {
  const response = parseWithdrawalTransportResponse(payload)
  const result = isWithdrawalErrorResponse(response)
    ? mapErrorResponse(response, input)
    : mapComparisonResponse(response, input)
  return validateWithdrawalDecisionViewModel(result)
}

export function buildWithdrawalDecisionChatRequest(
  question: string,
  sessionId: string,
  input: WithdrawalDecisionInput,
): ChatApiRequest {
  return buildChatApiRequest({
    question,
    sessionId,
    profile: {
      age: input.currentAge,
      retirementAmountWon: input.retirementBenefitAmount,
      expectedTaxWon: input.expectedTaxWon,
    },
  })
}

class MockWithdrawalDecisionProvider implements WithdrawalDecisionProvider {
  async compare(input: WithdrawalDecisionInput, signal: AbortSignal): Promise<WithdrawalDecisionViewModel> {
    await wait(signal)
    const missingFields = invalidRequiredFields(input)
    const result = missingFields.length
      ? createNeedsInputFixture(input, missingFields)
      : input.retirementBenefitAmount === 999
        ? createErrorFixture(input)
        : input.expectedReturnRate === -1
          ? createLimitedFixture(input)
          : input.retirementBenefitAmount === withdrawalComparisonTransportFixture.inputs.retirement_amount
              && input.expectedTaxWon === withdrawalComparisonTransportFixture.inputs.deferred_retirement_tax
            ? adaptWithdrawalTransportResponse(withdrawalComparisonTransportFixture, input)
            : createUnavailableComparisonFixture(input)
    return validateWithdrawalDecisionViewModel(result)
  }
}

export function adaptWithdrawalChatResponse(response: ChatResponse, input: WithdrawalDecisionInput): WithdrawalDecisionViewModel {
  const apiBoundary: WithdrawalDecisionViewModel = {
    status: 'limited', scenarioTitle: '퇴직급여 수령 방식 비교', input, missingFields: [],
    summary: '', limitations: [], options: [], assumptions: [], evidence: [],
    baselineOptionId: null, highlightedOptionId: null, highlightReason: null,
    canCompare: false, canRetry: false,
  }
  if (response.type === 'error') return { ...apiBoundary, status: 'error', summary: response.message, canRetry: response.retryable }
  if (response.type === 'clarification') return {
    ...apiBoundary, status: 'needs_input',
    summary: '금액 비교를 위해 추가 조건이 필요합니다.',
    missingFields: invalidRequiredFields(input),
  }
  return {
    ...apiBoundary,
    summary: response.type === 'limitation' ? response.availableAnswer ?? response.message : response.conclusion,
    limitations: [response.type === 'limitation' ? response.message : '현재 계산 결과를 화면에 표시할 수 없습니다.'],
  }
}

class HttpWithdrawalDecisionProvider implements WithdrawalDecisionProvider {
  constructor(private readonly client: PensionApiClient) {}

  async compare(input: WithdrawalDecisionInput, signal: AbortSignal) {
    const response = await this.client.answer(
      { mode: 'withdrawal-decision', message: JSON.stringify({ input }) },
      { signal },
    )
    // TODO(A/B): Replace this explicit limitation boundary only after the
    // canonical withdrawal payload and calculation/evidence IDs are finalized.
    return validateWithdrawalDecisionViewModel(adaptWithdrawalChatResponse(response, input))
  }
}

export function createWithdrawalDecisionProvider(
  useMockApi: boolean,
  client: PensionApiClient = pensionApi,
): WithdrawalDecisionProvider {
  return useMockApi ? new MockWithdrawalDecisionProvider() : new HttpWithdrawalDecisionProvider(client)
}

const withdrawalDecisionProvider = createWithdrawalDecisionProvider(isMockWithdrawalMode)

export function requestWithdrawalDecision(input: WithdrawalDecisionInput, signal: AbortSignal) {
  return withdrawalDecisionProvider.compare(input, signal)
}
