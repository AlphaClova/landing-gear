import { apiClientConfig } from './config'

export type ChatApiPlanType = 'DB' | 'DC' | 'IRP'
export type ChatApiExtraValue = string | number | boolean

export interface ChatApiProfile {
  age?: number
  retirement_amount_won?: number
  expected_tax_won?: number
  plan_type?: ChatApiPlanType
  extra?: Record<string, ChatApiExtraValue>
}

export interface ChatApiRequest {
  session_id: string
  question: string
  profile?: ChatApiProfile
}

export interface ChatRequestProfileInput {
  age?: number | null
  retirementAmountWon?: number | null
  expectedTaxWon?: number | null
  planType?: ChatApiPlanType | null
  extra?: Record<string, unknown> | null
}

export interface BuildChatApiRequestInput {
  sessionId: string
  question: string
  profile?: ChatRequestProfileInput | null
}

export class ChatApiRequestValidationError extends TypeError {
  constructor(field: string, reason: string) {
    super(`Invalid chat API request field '${field}': ${reason}`)
    this.name = 'ChatApiRequestValidationError'
  }
}

const planTypes = new Set<ChatApiPlanType>(['DB', 'DC', 'IRP'])

const validateWon = (field: string, value: number) => {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new ChatApiRequestValidationError(field, 'must be a non-negative safe integer in won')
  }
}

const validateAge = (age: number) => {
  if (!Number.isInteger(age) || age < 1 || age > 120) {
    throw new ChatApiRequestValidationError('age', 'must be an integer from 1 through 120')
  }
}

const mapExtra = (extra: Record<string, unknown> | null | undefined) => {
  if (!extra || Object.keys(extra).length === 0) return undefined
  const mapped: Record<string, ChatApiExtraValue> = {}
  for (const [key, value] of Object.entries(extra)) {
    if (typeof value !== 'string' && typeof value !== 'number' && typeof value !== 'boolean') {
      throw new ChatApiRequestValidationError(`profile.extra.${key}`, 'must be a string, number, or boolean')
    }
    if (typeof value === 'number' && !Number.isFinite(value)) {
      throw new ChatApiRequestValidationError(`profile.extra.${key}`, 'must be a finite number')
    }
    mapped[key] = value
  }
  return mapped
}

const buildProfile = (input: ChatRequestProfileInput | null | undefined): ChatApiProfile | undefined => {
  if (!input) return undefined
  const profile: ChatApiProfile = {}

  if (input.age !== null && input.age !== undefined) {
    validateAge(input.age)
    profile.age = input.age
  }
  if (input.retirementAmountWon !== null && input.retirementAmountWon !== undefined) {
    validateWon('retirementAmountWon', input.retirementAmountWon)
    profile.retirement_amount_won = input.retirementAmountWon
  }
  if (input.expectedTaxWon !== null && input.expectedTaxWon !== undefined) {
    validateWon('expectedTaxWon', input.expectedTaxWon)
    profile.expected_tax_won = input.expectedTaxWon
  }
  if (input.planType !== null && input.planType !== undefined) {
    if (!planTypes.has(input.planType)) {
      throw new ChatApiRequestValidationError('planType', 'must be DB, DC, or IRP')
    }
    profile.plan_type = input.planType
  }
  const extra = mapExtra(input.extra)
  if (extra) profile.extra = extra

  return Object.keys(profile).length > 0 ? profile : undefined
}

export function buildChatApiRequest(input: BuildChatApiRequestInput): ChatApiRequest {
  const sessionId = input.sessionId.trim()
  if (!sessionId) throw new ChatApiRequestValidationError('sessionId', 'must not be empty')

  const question = input.question.trim()
  if (!question) throw new ChatApiRequestValidationError('question', 'must not be empty')

  const profile = buildProfile(input.profile)
  return {
    session_id: sessionId,
    question,
    ...(profile ? { profile } : {}),
  }
}

export function getChatApiUrl(baseUrl: string = apiClientConfig.baseUrl): string {
  return `${baseUrl.replace(/\/+$/, '')}/v1/chat`
}
