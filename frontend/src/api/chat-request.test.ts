import { describe, expect, it } from 'vitest'
import { buildChatApiRequest, ChatApiRequestValidationError, getChatApiUrl } from './chat-request'

const baseInput = { sessionId: '123e4567-e89b-42d3-a456-426614174000', question: '퇴직연금 질문' }

describe('/v1/chat request builder', () => {
  it('maps and trims session_id and question', () => {
    expect(buildChatApiRequest({ sessionId: `  ${baseInput.sessionId}  `, question: '  질문입니다  ' }))
      .toEqual({ session_id: baseInput.sessionId, question: '질문입니다' })
  })

  it.each(['', '   '])('rejects the empty question %j', (question) => {
    expect(() => buildChatApiRequest({ ...baseInput, question })).toThrow(ChatApiRequestValidationError)
  })

  it('rejects an empty session ID', () => {
    expect(() => buildChatApiRequest({ ...baseInput, sessionId: '  ' })).toThrow(ChatApiRequestValidationError)
  })

  it('maps retirement amount and expected pre-reduction tax in won', () => {
    expect(buildChatApiRequest({
      ...baseInput,
      profile: { retirementAmountWon: 300_000_000, expectedTaxWon: 24_000_000 },
    }).profile).toEqual({ retirement_amount_won: 300_000_000, expected_tax_won: 24_000_000 })
  })

  it.each(['DB', 'DC', 'IRP'] as const)('maps the %s plan type', (planType) => {
    expect(buildChatApiRequest({ ...baseInput, profile: { planType } }).profile?.plan_type).toBe(planType)
  })

  it('omits null, undefined, and empty optional fields', () => {
    const result = buildChatApiRequest({
      ...baseInput,
      profile: { age: null, retirementAmountWon: undefined, expectedTaxWon: null, planType: null, extra: {} },
    })
    expect(result).not.toHaveProperty('profile')
    expect(JSON.stringify(result)).not.toContain('undefined')
  })

  it('preserves safe integer won without unit conversion', () => {
    const result = buildChatApiRequest({ ...baseInput, profile: { retirementAmountWon: 123_456_789 } })
    expect(result.profile?.retirement_amount_won).toBe(123_456_789)
  })

  it.each([-1, 1.5, Number.MAX_SAFE_INTEGER + 1])('rejects invalid won amount %s', (amount) => {
    expect(() => buildChatApiRequest({ ...baseInput, profile: { retirementAmountWon: amount } }))
      .toThrow(ChatApiRequestValidationError)
  })

  it.each([0, 1.5, 121])('rejects unrealistic age %s', (age) => {
    expect(() => buildChatApiRequest({ ...baseInput, profile: { age } })).toThrow(ChatApiRequestValidationError)
  })

  it('maps supported extra primitives and rejects unsupported values', () => {
    expect(buildChatApiRequest({ ...baseInput, profile: { extra: { text: 'yes', count: 2, flag: true } } }).profile?.extra)
      .toEqual({ text: 'yes', count: 2, flag: true })
    expect(() => buildChatApiRequest({ ...baseInput, profile: { extra: { nested: {} } } }))
      .toThrow(ChatApiRequestValidationError)
  })

  it('does not emit mode or the B deferred_retirement_tax field', () => {
    const result = buildChatApiRequest({ ...baseInput, profile: { expectedTaxWon: 24_000_000 } })
    expect(result).not.toHaveProperty('mode')
    expect(result.profile).not.toHaveProperty('deferred_retirement_tax')
  })

  it.each([
    ['http://localhost:8000', 'http://localhost:8000/v1/chat'],
    ['http://localhost:8000/', 'http://localhost:8000/v1/chat'],
    ['/api///', '/api/v1/chat'],
  ])('joins base URL %s without duplicate slashes', (baseUrl, expected) => {
    expect(getChatApiUrl(baseUrl)).toBe(expected)
  })
})
