import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CHAT_CLIENT_USER_MESSAGES, ChatApiClientError } from '../../api/chat-client'
import type { ChatApiClient } from '../../api/chat-client'
import type { ChatApiResponseTransport, ChatApiWithdrawalResult } from '../../api/chat-response'
import {
  HttpChatWithdrawalDecisionProvider,
  WITHDRAWAL_COMPARISON_QUESTION,
  parseWithdrawalChatApiMode,
} from './withdrawal-decision-adapter'
import { adaptChatApiWithdrawalResponse, WithdrawalChatAdapterError } from './withdrawal-decision-chat-adapter'
import { exampleWithdrawalInput } from './withdrawal-decision-mock'

const scenario = (
  id: 'lump_sum' | 'annuity_10_years' | 'annuity_21_plus_years',
  tax: number,
  rate: number,
  saving: number,
  evidenceIds = ['evidence-1'],
) => ({
  scenario: id, tax_value: tax, applicable_rate: rate, difference_vs_lump_sum: saving,
  formula: `${24_000_000} * ${rate}`, rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0',
  evidence_ids: evidenceIds, assumptions: [], warnings: [],
})

const withdrawalResult = (): ChatApiWithdrawalResult => ({
  comparison: {
    scenarios: [
      scenario('lump_sum', 24_000_000, 1, 0),
      scenario('annuity_10_years', 16_800_000, 0.7, 7_200_000),
      scenario('annuity_21_plus_years', 12_000_000, 0.5, 12_000_000),
    ],
    result_type: 'exact', unit: 'KRW',
  },
  evidence: [{
    evidence_id: 'evidence-1', chunk_id: 'chunk-1', document_id: 'doc-1', page: 2,
    section: '절세혜택', quote: '기간별 적용 비율', source_priority: 0, score: 1,
  }],
  applied_rules: [{ rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0' }],
  claim_validation: {
    validations: [{ claim_id: 'claim-1', supported: true, reasons: [] }],
    unsupported_claim_count: 0, validated_claim_count: 1, unsupported_claim_rate: 0,
  },
})

const response = (type: ChatApiResponseTransport['type'] = 'result'): ChatApiResponseTransport => ({
  type, message: 'internal server wording', required_slots: [], comparison: null,
  withdrawal_result: type === 'result' ? withdrawalResult() : null,
  citations: [], request_id: 'req-1',
})

const clientError = (kind: ChatApiClientError['kind'], retryable: boolean) => new ChatApiClientError({
  kind, status: kind === 'http' ? 503 : null, code: kind === 'http' ? 'tool_unavailable' : null,
  requestId: 'req-1', retryable, debugMessage: 'sensitive server message',
  userMessage: retryable ? CHAT_CLIENT_USER_MESSAGES.server : CHAT_CLIENT_USER_MESSAGES.input,
})

describe('A chat withdrawal adapter', () => {
  it('maps the normal result to complete with all three option IDs and exact values', () => {
    const result = adaptChatApiWithdrawalResponse(response(), exampleWithdrawalInput)
    expect(result.status).toBe('complete')
    expect(result.options.map((option) => option.id)).toEqual(['lump_sum', 'pension_10y', 'pension_21y_plus'])
    expect(result.options.map((option) => option.retirementIncomeTax.amount)).toEqual([24_000_000, 16_800_000, 12_000_000])
    expect(result.options.map((option) => option.applicableRate)).toEqual([1, 0.7, 0.5])
    expect(result.options.map((option) => option.taxSavingFromLumpSum?.amount)).toEqual([0, 7_200_000, 12_000_000])
  })

  it('preserves formula and rule data from the actual response', () => {
    const option = adaptChatApiWithdrawalResponse(response(), exampleWithdrawalInput).options[0]
    expect(option).toMatchObject({ formula: '24000000 * 1', ruleId: 'RETIRE_TAX_RATE_BY_YEAR', ruleVersion: '1.0.0' })
  })

  it('preserves numeric and null evidence pages and deduplicates scenario references', () => {
    const payload = response()
    payload.withdrawal_result!.comparison.scenarios[0].evidence_ids = ['evidence-1', 'evidence-1']
    payload.withdrawal_result!.evidence.push({
      ...payload.withdrawal_result!.evidence[0], evidence_id: 'evidence-2', chunk_id: 'chunk-2', page: null,
    })
    payload.withdrawal_result!.evidence.push({ ...payload.withdrawal_result!.evidence[0] })
    const result = adaptChatApiWithdrawalResponse(payload, exampleWithdrawalInput)
    expect(result.evidence.map((item) => item.page)).toEqual([2, null])
    expect(result.evidence[0]).not.toHaveProperty('url')
    expect(result.options[0].evidenceIds).toEqual(['evidence-1'])
  })

  it('maps unsupported claims to limited without exposing issue text', () => {
    const payload = response()
    payload.withdrawal_result!.claim_validation = {
      validations: [{ claim_id: 'claim-1', supported: false, reasons: ['internal verifier issue'] }],
      unsupported_claim_count: 1, validated_claim_count: 1, unsupported_claim_rate: 1,
    }
    const result = adaptChatApiWithdrawalResponse(payload, exampleWithdrawalInput)
    expect(result.status).toBe('limited')
    expect(JSON.stringify(result)).not.toContain('internal verifier issue')
  })

  it('maps known clarification slots and handles unknown slots generically', () => {
    const payload = response('clarification')
    payload.required_slots = [
      { name: 'retirement_amount_won', prompt: 'raw retirement prompt', reason: null },
      { name: 'expected_tax_won', prompt: 'raw tax prompt', reason: null },
      { name: 'unknown_slot', prompt: 'internal prompt', reason: null },
    ]
    const result = adaptChatApiWithdrawalResponse(payload, exampleWithdrawalInput)
    expect(result).toMatchObject({
      status: 'needs_input', missingFields: ['retirementBenefitAmount', 'expectedTaxWon'], canRetry: false,
    })
    expect(JSON.stringify(result)).not.toContain('internal prompt')
  })

  it('maps limitation and normal error to safe states', () => {
    expect(adaptChatApiWithdrawalResponse(response('limitation'), exampleWithdrawalInput).status).toBe('limited')
    const error = adaptChatApiWithdrawalResponse(response('error'), exampleWithdrawalInput)
    expect(error).toMatchObject({ status: 'error', canRetry: false })
    expect(error.summary).not.toContain('internal server wording')
  })

  it('rejects a result without withdrawal_result', () => {
    const payload = response(); payload.withdrawal_result = null
    expect(() => adaptChatApiWithdrawalResponse(payload, exampleWithdrawalInput)).toThrow(WithdrawalChatAdapterError)
  })

  it('rejects missing, duplicate, or unknown scenarios', () => {
    const missing = response(); missing.withdrawal_result!.comparison.scenarios.pop()
    expect(() => adaptChatApiWithdrawalResponse(missing, exampleWithdrawalInput)).toThrow('each supported scenario')
    const duplicate = response(); duplicate.withdrawal_result!.comparison.scenarios[2] = duplicate.withdrawal_result!.comparison.scenarios[1]
    expect(() => adaptChatApiWithdrawalResponse(duplicate, exampleWithdrawalInput)).toThrow('each supported scenario')
  })

  it('rejects unknown evidence and inconsistent claim counters', () => {
    const evidence = response(); evidence.withdrawal_result!.comparison.scenarios[0].evidence_ids = ['unknown']
    expect(() => adaptChatApiWithdrawalResponse(evidence, exampleWithdrawalInput)).toThrow('unknown evidence')
    const claims = response(); claims.withdrawal_result!.claim_validation.unsupported_claim_count = 1
    expect(() => adaptChatApiWithdrawalResponse(claims, exampleWithdrawalInput)).toThrow('counters')
  })
})

describe('HTTP chat withdrawal provider', () => {
  beforeEach(() => sessionStorage.clear())

  it('sends the fixed question, session ID, profile amounts, and AbortSignal then adapts the response', async () => {
    sessionStorage.setItem('landing-gear.chat-session-id', '123e4567-e89b-42d3-a456-426614174000')
    const chat = vi.fn<ChatApiClient['chat']>().mockResolvedValue(response())
    const signal = new AbortController().signal
    const result = await new HttpChatWithdrawalDecisionProvider({ chat }).compare(exampleWithdrawalInput, signal)
    expect(result.status).toBe('complete')
    expect(chat).toHaveBeenCalledWith({
      session_id: '123e4567-e89b-42d3-a456-426614174000',
      question: WITHDRAWAL_COMPARISON_QUESTION,
      profile: {
        age: 55,
        retirement_amount_won: 300_000_000,
        expected_tax_won: 24_000_000,
        extra: { pension_start_age: 60 },
      },
    }, { signal })
    expect(chat.mock.calls[0][0]).not.toHaveProperty('mode')
    expect(chat.mock.calls[0][0].profile).not.toHaveProperty('deferred_retirement_tax')
  })

  it('preserves the existing cancelled flow', async () => {
    const chat = vi.fn<ChatApiClient['chat']>().mockRejectedValue(clientError('cancelled', false))
    await expect(new HttpChatWithdrawalDecisionProvider({ chat }).compare(exampleWithdrawalInput, new AbortController().signal))
      .rejects.toMatchObject({ name: 'AbortError' })
  })

  it.each([
    ['timeout', true], ['network', true], ['http', true], ['http', false], ['protocol', false],
  ] as const)('maps %s retryable=%s without exposing debug messages', async (kind, retryable) => {
    const chat = vi.fn<ChatApiClient['chat']>().mockRejectedValue(clientError(kind, retryable))
    vi.useFakeTimers()
    try {
      const resultPromise = new HttpChatWithdrawalDecisionProvider({ chat }).compare(exampleWithdrawalInput, new AbortController().signal)
      await vi.runAllTimersAsync()
      const result = await resultPromise
      expect(result).toMatchObject({ status: 'error', canRetry: retryable })
      expect(JSON.stringify(result)).not.toContain('sensitive server message')
      // Retryable transport failures (network/timeout/5xx) get one silent
      // automatic retry before surfacing an error; non-retryable failures fail fast.
      expect(chat).toHaveBeenCalledTimes(retryable ? 2 : 1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('recovers transparently on a single automatic retry after a retryable failure', async () => {
    const chat = vi.fn<ChatApiClient['chat']>()
      .mockRejectedValueOnce(clientError('network', true))
      .mockResolvedValueOnce(response())
    vi.useFakeTimers()
    try {
      const resultPromise = new HttpChatWithdrawalDecisionProvider({ chat }).compare(exampleWithdrawalInput, new AbortController().signal)
      await vi.runAllTimersAsync()
      const result = await resultPromise
      expect(result.status).toBe('complete')
      expect(chat).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('maps an Adapter protocol failure to a non-retryable error', async () => {
    const invalid = response(); invalid.withdrawal_result = null
    const chat = vi.fn<ChatApiClient['chat']>().mockResolvedValue(invalid)
    const result = await new HttpChatWithdrawalDecisionProvider({ chat }).compare(exampleWithdrawalInput, new AbortController().signal)
    expect(result).toMatchObject({ status: 'error', canRetry: false })
  })

  it.each([
    [undefined, 'mock'], ['mock', 'mock'], ['http', 'http'], ['invalid', 'mock'],
  ] as const)('selects %s as %s mode', (value, expected) => {
    expect(parseWithdrawalChatApiMode(value)).toBe(expected)
  })
})
