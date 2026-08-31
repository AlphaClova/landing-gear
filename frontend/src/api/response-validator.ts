import type { ChatResponse, ComparisonResult, RequiredSlot } from '../types/api'
import { ApiResponseError } from './errors'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isString = (value: unknown): value is string => typeof value === 'string'
const isNullableString = (value: unknown): value is string | null => value === null || isString(value)
const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString)

const isRequiredSlot = (value: unknown): value is RequiredSlot => isRecord(value)
  && isString(value.key)
  && isString(value.label)
  && ['text', 'number', 'select'].includes(String(value.inputType))
  && isNullableString(value.unit)
  && (value.options === null || isStringArray(value.options))

const isCitation = (value: unknown) => isRecord(value)
  && isString(value.id)
  && isString(value.documentTitle)
  && (isNullableString(value.page) || Number.isSafeInteger(value.page))
  && isNullableString(value.excerpt)

const isComparison = (value: unknown): value is ComparisonResult => {
  if (!isRecord(value) || !isString(value.title) || !Array.isArray(value.rows)
    || !isStringArray(value.reasons) || !isStringArray(value.checks)
    || !isNullableString(value.formula) || !Array.isArray(value.citations)
    || !value.citations.every(isCitation)) return false

  return value.rows.every((row) => isRecord(row)
    && isString(row.id) && isString(row.label)
    && isNullableString(row.optionA) && isNullableString(row.optionB)
    && isNullableString(row.unit)
    && ['rule', 'user-input', 'assumption', 'needs-confirmation'].includes(String(row.valueSource)))
}

export function parseChatResponse(value: unknown): ChatResponse {
  if (!isRecord(value) || !isString(value.type)) throw new ApiResponseError('API response is missing a valid discriminator')

  if (value.type === 'clarification'
    && isString(value.requestId)
    && Array.isArray(value.requiredSlots)
    && value.requiredSlots.every(isRequiredSlot)) return value as unknown as ChatResponse

  if (value.type === 'result'
    && isString(value.requestId)
    && (value.mode === 'pension-chat' || value.mode === 'withdrawal-decision')
    && isString(value.conclusion)
    && isString(value.explanation)
    && (value.comparison === null || isComparison(value.comparison))
    && Array.isArray(value.citations)
    && value.citations.every(isCitation)) return value as unknown as ChatResponse

  if (value.type === 'limitation'
    && isString(value.requestId)
    && isNullableString(value.availableAnswer)
    && isString(value.message)
    && isStringArray(value.requiredConditions)) return value as unknown as ChatResponse

  if (value.type === 'error'
    && isNullableString(value.requestId)
    && isString(value.code)
    && isString(value.message)
    && typeof value.retryable === 'boolean') return value as unknown as ChatResponse

  throw new ApiResponseError()
}
