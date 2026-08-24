export type ChatApiResponseType = 'clarification' | 'result' | 'limitation' | 'error'

export interface ChatApiRequiredSlot {
  name: string
  prompt: string
  reason: string | null
}

export interface ChatApiCitation {
  id: string
  document_id: string
  page: number | null
  section: string | null
  source: string
  excerpt: string
  url: string | null
}

export interface ChatApiComparisonRow {
  label: string
  values: Record<string, string>
}

export interface ChatApiComparisonResult {
  title: string
  options: string[]
  rows: ChatApiComparisonRow[]
  note: string | null
}

export interface ChatApiWithdrawalScenario {
  scenario: 'lump_sum' | 'annuity_10_years' | 'annuity_21_plus_years'
  tax_value: number
  applicable_rate: number
  difference_vs_lump_sum: number
  formula: string
  rule_id: string
  rule_version: string
  evidence_ids: string[]
  assumptions: string[]
  warnings: string[]
}

export interface ChatApiWithdrawalComparison {
  scenarios: ChatApiWithdrawalScenario[]
  result_type: 'exact'
  unit: 'KRW'
}

export interface ChatApiWithdrawalEvidence {
  evidence_id: string
  chunk_id: string
  document_id: string
  page: number | null
  section: string | null
  quote: string | null
  source_priority: number | null
  score: number
}

export interface ChatApiAppliedRule {
  rule_id: string
  rule_version: string | null
}

export interface ChatApiClaimValidationEntry {
  claim_id: string
  supported: boolean
  reasons: string[]
}

export interface ChatApiClaimValidation {
  validations: ChatApiClaimValidationEntry[]
  unsupported_claim_count: number
  validated_claim_count: number
  unsupported_claim_rate: number
}

export interface ChatApiWithdrawalResult {
  comparison: ChatApiWithdrawalComparison
  evidence: ChatApiWithdrawalEvidence[]
  applied_rules: ChatApiAppliedRule[]
  claim_validation: ChatApiClaimValidation
}

export interface ChatApiResponseTransport {
  type: ChatApiResponseType
  message: string
  required_slots: ChatApiRequiredSlot[]
  comparison: ChatApiComparisonResult | null
  withdrawal_result: ChatApiWithdrawalResult | null
  citations: ChatApiCitation[]
  request_id: string
}

export type ChatApiErrorCode =
  | 'validation_error'
  | 'out_of_scope'
  | 'tool_unavailable'
  | 'tool_argument_error'
  | 'upstream_timeout'
  | 'upstream_error'
  | 'verification_failed'
  | 'internal_error'

export interface ChatApiHttpErrorTransport {
  type: 'error'
  code: ChatApiErrorCode
  message: string
  request_id: string
}

export interface FastApiValidationErrorItem {
  type: string
  loc: Array<string | number>
  msg: string
  input?: unknown
  ctx?: Record<string, unknown>
  url?: string
}

export interface FastApiValidationErrorTransport {
  detail: FastApiValidationErrorItem[]
}

export type ChatApiHttpError = ChatApiHttpErrorTransport | FastApiValidationErrorTransport

export class ChatApiResponseValidationError extends Error {
  constructor(reason: string) {
    super(`Chat API response validation failed: ${reason}`)
    this.name = 'ChatApiResponseValidationError'
  }
}

const responseTypes = new Set<ChatApiResponseType>(['clarification', 'result', 'limitation', 'error'])
const errorCodes = new Set<ChatApiErrorCode>([
  'validation_error',
  'out_of_scope',
  'tool_unavailable',
  'tool_argument_error',
  'upstream_timeout',
  'upstream_error',
  'verification_failed',
  'internal_error',
])

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isString = (value: unknown): value is string => typeof value === 'string'
const isNonEmptyString = (value: unknown): value is string => isString(value) && value.trim().length > 0
const isNullableString = (value: unknown): value is string | null => value === null || isString(value)
const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString)

const isRequiredSlot = (value: unknown): value is ChatApiRequiredSlot => isRecord(value)
  && isNonEmptyString(value.name)
  && isNonEmptyString(value.prompt)
  && isNullableString(value.reason)

const isCitation = (value: unknown): value is ChatApiCitation => isRecord(value)
  && isNonEmptyString(value.id)
  && isNonEmptyString(value.document_id)
  && (value.page === null || Number.isSafeInteger(value.page))
  && isNullableString(value.section)
  && isString(value.source)
  && isString(value.excerpt)
  && isNullableString(value.url)

const isComparisonRow = (value: unknown, optionIds: Set<string>): value is ChatApiComparisonRow => {
  if (!isRecord(value) || !isString(value.label) || !isRecord(value.values)) return false
  const entries = Object.entries(value.values)
  return entries.length === optionIds.size
    && entries.every(([optionId, cell]) => optionIds.has(optionId) && isString(cell))
}

const isComparisonResult = (value: unknown): value is ChatApiComparisonResult => {
  if (!isRecord(value)
    || !isString(value.title)
    || !isStringArray(value.options)
    || !Array.isArray(value.rows)
    || !isNullableString(value.note)) return false
  const optionIds = new Set(value.options)
  return optionIds.size === value.options.length
    && value.rows.every((row) => isComparisonRow(row, optionIds))
}

const isNullableComparison = (value: unknown): value is ChatApiComparisonResult | null =>
  value === null || isComparisonResult(value)

const isAppliedRule = (value: unknown): value is ChatApiAppliedRule => isRecord(value)
  && isNonEmptyString(value.rule_id)
  && isNullableString(value.rule_version)

const scenarioIds = new Set(['lump_sum', 'annuity_10_years', 'annuity_21_plus_years'])
const isWon = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0
const isRate = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
const isWithdrawalScenario = (value: unknown): value is ChatApiWithdrawalScenario => isRecord(value)
  && scenarioIds.has(value.scenario as string)
  && isWon(value.tax_value)
  && isRate(value.applicable_rate)
  && isWon(value.difference_vs_lump_sum)
  && isString(value.formula)
  && isNonEmptyString(value.rule_id)
  && isNonEmptyString(value.rule_version)
  && isStringArray(value.evidence_ids)
  && isStringArray(value.assumptions)
  && isStringArray(value.warnings)

const isWithdrawalComparison = (value: unknown): value is ChatApiWithdrawalComparison => isRecord(value)
  && value.result_type === 'exact'
  && value.unit === 'KRW'
  && Array.isArray(value.scenarios)
  && value.scenarios.every(isWithdrawalScenario)

const isWithdrawalEvidence = (value: unknown): value is ChatApiWithdrawalEvidence => isRecord(value)
  && isNonEmptyString(value.evidence_id)
  && isNonEmptyString(value.chunk_id)
  && isNonEmptyString(value.document_id)
  && (value.page === null || Number.isSafeInteger(value.page))
  && isNullableString(value.section)
  && isNullableString(value.quote)
  && (value.source_priority === null || Number.isSafeInteger(value.source_priority))
  && typeof value.score === 'number'
  && Number.isFinite(value.score)

const isClaimValidationEntry = (value: unknown): value is ChatApiClaimValidationEntry => isRecord(value)
  && isNonEmptyString(value.claim_id)
  && typeof value.supported === 'boolean'
  && isStringArray(value.reasons)

const isClaimValidation = (value: unknown): value is ChatApiClaimValidation => isRecord(value)
  && Array.isArray(value.validations)
  && value.validations.every(isClaimValidationEntry)
  && isWon(value.unsupported_claim_count)
  && isWon(value.validated_claim_count)
  && isRate(value.unsupported_claim_rate)

const isWithdrawalResult = (value: unknown): value is ChatApiWithdrawalResult => isRecord(value)
  && isWithdrawalComparison(value.comparison)
  && Array.isArray(value.evidence)
  && value.evidence.every(isWithdrawalEvidence)
  && Array.isArray(value.applied_rules)
  && value.applied_rules.every(isAppliedRule)
  && isClaimValidation(value.claim_validation)

export const isChatApiResponseTransport = (value: unknown): value is ChatApiResponseTransport => isRecord(value)
  && responseTypes.has(value.type as ChatApiResponseType)
  && isString(value.message)
  && Array.isArray(value.required_slots)
  && value.required_slots.every(isRequiredSlot)
  && isNullableComparison(value.comparison)
  && (value.withdrawal_result === null || isWithdrawalResult(value.withdrawal_result))
  && Array.isArray(value.citations)
  && value.citations.every(isCitation)
  && isNonEmptyString(value.request_id)

export function parseChatApiResponse(value: unknown): ChatApiResponseTransport {
  if (isChatApiResponseTransport(value)) return value
  throw new ChatApiResponseValidationError('payload does not match the /v1/chat response contract')
}

const isChatApiHttpError = (value: unknown): value is ChatApiHttpErrorTransport => isRecord(value)
  && value.type === 'error'
  && errorCodes.has(value.code as ChatApiErrorCode)
  && isString(value.message)
  && isNonEmptyString(value.request_id)

const isFastApiValidationErrorItem = (value: unknown): value is FastApiValidationErrorItem => isRecord(value)
  && isString(value.type)
  && Array.isArray(value.loc)
  && value.loc.every((item) => isString(item) || Number.isInteger(item))
  && isString(value.msg)
  && (!Object.hasOwn(value, 'ctx') || isRecord(value.ctx))
  && (!Object.hasOwn(value, 'url') || isString(value.url))

const isFastApiValidationError = (value: unknown): value is FastApiValidationErrorTransport => isRecord(value)
  && Array.isArray(value.detail)
  && value.detail.length > 0
  && value.detail.every(isFastApiValidationErrorItem)

export function parseChatApiHttpError(value: unknown): ChatApiHttpError {
  if (isChatApiHttpError(value) || isFastApiValidationError(value)) return value
  throw new ChatApiResponseValidationError('payload does not match a supported HTTP error contract')
}
