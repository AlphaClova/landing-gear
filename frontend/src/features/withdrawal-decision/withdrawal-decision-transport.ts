export type WithdrawalScenarioId =
  | 'lump_sum'
  | 'annuity_10_years'
  | 'annuity_21_plus_years'

export interface WithdrawalComparisonInputs {
  retirement_amount: number
  deferred_retirement_tax: number
}

export interface WithdrawalComparisonScenario {
  scenario: WithdrawalScenarioId
  tax_value: number
  applicable_rate: number
  difference_vs_lump_sum: number
  formula: string
  rule_id: string
  rule_version: string
  evidence_ids: string[]
  assumptions: unknown[]
  warnings: unknown[]
}

export interface WithdrawalComparison {
  result_type: 'exact'
  unit: 'KRW'
  scenarios: WithdrawalComparisonScenario[]
}

export interface WithdrawalEvidenceCitation {
  evidence_id: string
  chunk_id: string
  document_id: string
  page: number | null
  section: string
  quote: string
  source_priority: number
  score: number
}

export interface WithdrawalAppliedRule {
  rule_id: string
  rule_version: string
}

export interface WithdrawalClaimValidationItem {
  claim_id: string
  supported: boolean
  reasons: string[]
}

export interface WithdrawalClaimValidation {
  validations: WithdrawalClaimValidationItem[]
  unsupported_claim_count: number
  validated_claim_count: number
  unsupported_claim_rate: number
}

export interface WithdrawalComparisonResponse {
  inputs: WithdrawalComparisonInputs
  comparison: WithdrawalComparison
  evidence: WithdrawalEvidenceCitation[]
  applied_rules: WithdrawalAppliedRule[]
  claim_validation: WithdrawalClaimValidation
}

export type WithdrawalApiErrorFamily = 'MISSING_INPUT' | 'RULE_ERROR'

export interface WithdrawalErrorInputs {
  retirement_amount?: number | null
  deferred_retirement_tax?: number | null
  actual_pension_year?: number | null
  rule_version?: string
  [key: string]: unknown
}

export interface WithdrawalTransportError {
  case: string
  inputs: WithdrawalErrorInputs
  error_type: string
  message: string
  api_error_family: WithdrawalApiErrorFamily
}

export interface WithdrawalErrorResponse {
  errors: WithdrawalTransportError[]
}

export type WithdrawalTransportResponse = WithdrawalComparisonResponse | WithdrawalErrorResponse

export class WithdrawalTransportValidationError extends Error {
  constructor(reason: string) {
    super(`Withdrawal transport response validation failed: ${reason}`)
    this.name = 'WithdrawalTransportValidationError'
  }
}

const scenarioIds = new Set<WithdrawalScenarioId>([
  'lump_sum',
  'annuity_10_years',
  'annuity_21_plus_years',
])
const errorFamilies = new Set<WithdrawalApiErrorFamily>(['MISSING_INPUT', 'RULE_ERROR'])

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isString = (value: unknown): value is string => typeof value === 'string'
const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString)
const isIntegerWon = (value: unknown): value is number => Number.isSafeInteger(value)
const isUnitRate = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1

const isInputs = (value: unknown): value is WithdrawalComparisonInputs => isRecord(value)
  && isIntegerWon(value.retirement_amount)
  && isIntegerWon(value.deferred_retirement_tax)

const isScenario = (value: unknown): value is WithdrawalComparisonScenario => isRecord(value)
  && scenarioIds.has(value.scenario as WithdrawalScenarioId)
  && isIntegerWon(value.tax_value)
  && isUnitRate(value.applicable_rate)
  && isIntegerWon(value.difference_vs_lump_sum)
  && isString(value.formula)
  && isString(value.rule_id)
  && isString(value.rule_version)
  && isStringArray(value.evidence_ids)
  && Array.isArray(value.assumptions)
  && Array.isArray(value.warnings)

const isComparison = (value: unknown): value is WithdrawalComparison => isRecord(value)
  && value.result_type === 'exact'
  && value.unit === 'KRW'
  && Array.isArray(value.scenarios)
  && value.scenarios.every(isScenario)

const isEvidence = (value: unknown): value is WithdrawalEvidenceCitation => isRecord(value)
  && isString(value.evidence_id)
  && isString(value.chunk_id)
  && isString(value.document_id)
  && (value.page === null || (typeof value.page === 'number' && Number.isFinite(value.page)))
  && isString(value.section)
  && isString(value.quote)
  && Number.isSafeInteger(value.source_priority)
  && isUnitRate(value.score)

const isAppliedRule = (value: unknown): value is WithdrawalAppliedRule => isRecord(value)
  && isString(value.rule_id)
  && isString(value.rule_version)

const isClaimValidationItem = (value: unknown): value is WithdrawalClaimValidationItem => isRecord(value)
  && isString(value.claim_id)
  && typeof value.supported === 'boolean'
  && isStringArray(value.reasons)

const isClaimValidation = (value: unknown): value is WithdrawalClaimValidation => isRecord(value)
  && Array.isArray(value.validations)
  && value.validations.every(isClaimValidationItem)
  && Number.isSafeInteger(value.unsupported_claim_count)
  && Number.isSafeInteger(value.validated_claim_count)
  && isUnitRate(value.unsupported_claim_rate)

export const isWithdrawalComparisonResponse = (value: unknown): value is WithdrawalComparisonResponse =>
  isRecord(value)
  && !Object.hasOwn(value, 'errors')
  && isInputs(value.inputs)
  && isComparison(value.comparison)
  && Array.isArray(value.evidence)
  && value.evidence.every(isEvidence)
  && Array.isArray(value.applied_rules)
  && value.applied_rules.every(isAppliedRule)
  && isClaimValidation(value.claim_validation)

const isErrorInputs = (value: unknown): value is WithdrawalErrorInputs => {
  if (!isRecord(value)) return false
  const integerOrNull = (item: unknown) => item === null || isIntegerWon(item)
  return (!Object.hasOwn(value, 'retirement_amount') || integerOrNull(value.retirement_amount))
    && (!Object.hasOwn(value, 'deferred_retirement_tax') || integerOrNull(value.deferred_retirement_tax))
    && (!Object.hasOwn(value, 'actual_pension_year') || integerOrNull(value.actual_pension_year))
    && (!Object.hasOwn(value, 'rule_version') || isString(value.rule_version))
}

const isTransportError = (value: unknown): value is WithdrawalTransportError => isRecord(value)
  && isString(value.case)
  && isErrorInputs(value.inputs)
  && isString(value.error_type)
  && isString(value.message)
  && errorFamilies.has(value.api_error_family as WithdrawalApiErrorFamily)

export const isWithdrawalErrorResponse = (value: unknown): value is WithdrawalErrorResponse =>
  isRecord(value)
  && !Object.hasOwn(value, 'comparison')
  && Array.isArray(value.errors)
  && value.errors.length > 0
  && value.errors.every(isTransportError)

export function parseWithdrawalTransportResponse(value: unknown): WithdrawalTransportResponse {
  if (isWithdrawalComparisonResponse(value)) return value
  if (isWithdrawalErrorResponse(value)) return value
  throw new WithdrawalTransportValidationError('payload does not match the comparison or error contract')
}
