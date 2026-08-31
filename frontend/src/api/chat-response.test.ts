import { describe, expect, it } from 'vitest'
import {
  ChatApiResponseValidationError,
  parseChatApiHttpError,
  parseChatApiResponse,
} from './chat-response'
import type {
  ChatApiCitation,
  ChatApiComparisonResult,
  ChatApiResponseTransport,
  ChatApiWithdrawalResult,
} from './chat-response'

const citation = (page: number | null = 12): ChatApiCitation => ({
  id: 'evidence-1',
  document_id: 'doc-retirement-tax-guide',
  page,
  section: null,
  source: '퇴직소득세 감면율 안내',
  excerpt: '연금 수령 기간별 감면율 근거',
  url: null,
})

const comparison = (): ChatApiComparisonResult => ({
  title: '일시금 vs 연금수령 비교',
  options: ['lump_sum', 'pension_1_10y'],
  rows: [{
    label: '적용 세율',
    values: { lump_sum: '100%', pension_1_10y: '70%' },
  }],
  note: null,
})

const baseResponse = (): ChatApiResponseTransport => ({
  type: 'result',
  message: '비교 결과입니다.',
  required_slots: [],
  comparison: null,
  withdrawal_result: null,
  citations: [],
  request_id: 'req_a1b2c3d4e5f6',
})

const withdrawalResult = (): ChatApiWithdrawalResult => ({
  comparison: {
    scenarios: [{
      scenario: 'lump_sum', tax_value: 24_000_000, applicable_rate: 1,
      difference_vs_lump_sum: 0, formula: '24000000 * 1.00',
      rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0',
      evidence_ids: ['evidence-1'], assumptions: [], warnings: [],
    }],
    result_type: 'exact',
    unit: 'KRW',
  },
  evidence: [{
    evidence_id: 'evidence-1', chunk_id: 'chunk-1', document_id: 'document-1', page: 1,
    section: null, quote: null, source_priority: null, score: 1,
  }],
  applied_rules: [{ rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0' }],
  claim_validation: {
    validations: [{ claim_id: 'claim-1', supported: true, reasons: [] }],
    unsupported_claim_count: 0, validated_claim_count: 1, unsupported_claim_rate: 0,
  },
})

describe('/v1/chat response transport', () => {
  it('accepts the minimal shape of A withdrawal result sample', () => {
    const payload = { ...baseResponse(), withdrawal_result: withdrawalResult(), citations: [citation()] }
    expect(parseChatApiResponse(payload)).toEqual(payload)
  })

  it('allows a general result with null withdrawal_result', () => {
    expect(parseChatApiResponse(baseResponse()).withdrawal_result).toBeNull()
  })

  it('accepts and preserves nullable latest citation ranking metadata', () => {
    const payload = {
      ...baseResponse(),
      citations: [{ ...citation(null), source_priority: null, score: null }],
    }
    expect(parseChatApiResponse(payload).citations[0]).toMatchObject({
      source_priority: null,
      score: null,
    })
  })

  it.each([
    ['source_priority', 1.5],
    ['score', 'high'],
  ])('rejects invalid citation %s when the latest field is present', (field, invalidValue) => {
    const payload = {
      ...baseResponse(),
      citations: [{ ...citation(), [field]: invalidValue }],
    }
    expect(() => parseChatApiResponse(payload)).toThrow(ChatApiResponseValidationError)
  })

  it('validates a withdrawal result comparison, evidence, rules, and claims', () => {
    const result = parseChatApiResponse({ ...baseResponse(), withdrawal_result: withdrawalResult() })
    expect(result.withdrawal_result?.claim_validation.unsupported_claim_count).toBe(0)
  })

  it('accepts clarification with required slots', () => {
    const payload = {
      ...baseResponse(),
      type: 'clarification',
      required_slots: [{ name: 'expected_tax_won', prompt: '기준 세액을 입력해 주세요.', reason: null }],
    }
    expect(parseChatApiResponse(payload).type).toBe('clarification')
  })

  it('accepts limitation', () => {
    expect(parseChatApiResponse({ ...baseResponse(), type: 'limitation' }).type).toBe('limitation')
  })

  it('accepts error as a normal ChatResponse type when it has the full response shape', () => {
    expect(parseChatApiResponse({ ...baseResponse(), type: 'error' }).type).toBe('error')
  })

  it('validates the generic comparison', () => {
    const payload = { ...baseResponse(), comparison: comparison() }
    expect(parseChatApiResponse(payload).comparison?.options).toEqual(['lump_sum', 'pension_1_10y'])
  })

  it('allows nullable Citation page, section, and url', () => {
    const payload = { ...baseResponse(), citations: [citation(null)] }
    expect(parseChatApiResponse(payload).citations[0].page).toBeNull()
  })

  it('allows nullable applied rule version', () => {
    const result = withdrawalResult()
    result.applied_rules[0].rule_version = null
    expect(parseChatApiResponse({ ...baseResponse(), withdrawal_result: result })
      .withdrawal_result?.applied_rules[0].rule_version).toBeNull()
  })

  it('validates unsupported claims', () => {
    const result = withdrawalResult()
    result.claim_validation = {
      validations: [{ claim_id: 'claim-1', supported: false, reasons: ['근거 확인 필요'] }],
      unsupported_claim_count: 1, validated_claim_count: 1, unsupported_claim_rate: 1,
    }
    expect(parseChatApiResponse({ ...baseResponse(), withdrawal_result: result })
      .withdrawal_result?.claim_validation.validations[0].reasons).toEqual(['근거 확인 필요'])
  })

  it('rejects an unknown type', () => {
    expect(() => parseChatApiResponse({ ...baseResponse(), type: 'complete' }))
      .toThrow(ChatApiResponseValidationError)
  })

  it('rejects a missing required top-level field', () => {
    const payload: Record<string, unknown> = { ...baseResponse() }
    delete payload.request_id
    expect(() => parseChatApiResponse(payload)).toThrow(ChatApiResponseValidationError)
  })

  it('rejects row values missing an option', () => {
    const invalidComparison = comparison()
    invalidComparison.rows[0].values = { lump_sum: '100%' }
    expect(() => parseChatApiResponse({ ...baseResponse(), comparison: invalidComparison }))
      .toThrow(ChatApiResponseValidationError)
  })

  it('rejects row values with an unknown option', () => {
    const invalidComparison = comparison()
    invalidComparison.rows[0].values = { lump_sum: '100%', unknown: '70%' }
    expect(() => parseChatApiResponse({ ...baseResponse(), comparison: invalidComparison }))
      .toThrow(ChatApiResponseValidationError)
  })

  it('rejects an invalid withdrawal Citation', () => {
    const result = withdrawalResult()
    result.evidence[0].page = '12' as unknown as number
    expect(() => parseChatApiResponse({ ...baseResponse(), withdrawal_result: result }))
      .toThrow(ChatApiResponseValidationError)
  })

  it('rejects an invalid request_id', () => {
    expect(() => parseChatApiResponse({ ...baseResponse(), request_id: ' ' }))
      .toThrow(ChatApiResponseValidationError)
  })
})

describe('/v1/chat HTTP error transport', () => {
  it('accepts A structured error envelope and preserves diagnostic fields', () => {
    const payload = {
      type: 'error',
      code: 'upstream_timeout',
      message: 'internal upstream details',
      request_id: 'req_a1b2c3d4e5f6',
    }
    expect(parseChatApiHttpError(payload)).toEqual(payload)
  })

  it('accepts the FastAPI default 422 detail response separately', () => {
    const payload = {
      detail: [{
        type: 'missing',
        loc: ['body', 'question'],
        msg: 'Field required',
        input: { session_id: 'session-1' },
      }],
    }
    expect(parseChatApiHttpError(payload)).toEqual(payload)
  })

  it('does not expose the server message through a validation failure', () => {
    const serverMessage = 'sensitive internal exception'
    try {
      parseChatApiHttpError({ type: 'error', code: 'typo', message: serverMessage, request_id: 'req-1' })
      throw new Error('expected parser to reject payload')
    } catch (error) {
      expect(error).toBeInstanceOf(ChatApiResponseValidationError)
      expect((error as Error).message).not.toContain(serverMessage)
    }
  })
})
