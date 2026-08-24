import { describe, expect, it } from 'vitest'
import {
  isWithdrawalComparisonResponse,
  isWithdrawalErrorResponse,
  parseWithdrawalTransportResponse,
  WithdrawalTransportValidationError,
} from './withdrawal-decision-transport'

const scenario = (scenarioId: string = 'lump_sum') => ({
  scenario: scenarioId,
  tax_value: 24_000_000,
  applicable_rate: 0.7,
  difference_vs_lump_sum: 0,
  formula: '24000000 * 0.70',
  rule_id: 'RETIRE_TAX_RATE_BY_YEAR',
  rule_version: '1.0.0',
  evidence_ids: ['evidence-1'],
  assumptions: [],
  warnings: [],
})

const comparisonPayload = () => ({
  inputs: { retirement_amount: 300_000_000, deferred_retirement_tax: 24_000_000 },
  comparison: { result_type: 'exact', unit: 'KRW', scenarios: [scenario()] },
  evidence: [{
    evidence_id: 'evidence-1', chunk_id: 'chunk-1', document_id: 'document-1', page: 1 as number | null,
    section: 'section', quote: 'quote', source_priority: 0, score: 1,
  }],
  applied_rules: [{ rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0' }],
  claim_validation: {
    validations: [{ claim_id: 'claim-1', supported: true, reasons: [] }],
    unsupported_claim_count: 0, validated_claim_count: 1, unsupported_claim_rate: 0,
  },
})

const errorPayload = (family: string) => ({
  errors: [{
    case: 'error-case', inputs: { deferred_retirement_tax: null },
    error_type: 'ExampleError', message: 'raw engine detail', api_error_family: family,
  }],
})

describe('withdrawal decision transport contract', () => {
  it('accepts a minimal payload matching the comparison sample', () => {
    expect(isWithdrawalComparisonResponse(comparisonPayload())).toBe(true)
  })

  it.each(['lump_sum', 'annuity_10_years', 'annuity_21_plus_years'])(
    'accepts the %s scenario identifier',
    (scenarioId) => {
      const payload = comparisonPayload()
      payload.comparison.scenarios = [scenario(scenarioId)]
      expect(isWithdrawalComparisonResponse(payload)).toBe(true)
    },
  )

  it('accepts integer-won amounts', () => {
    expect(parseWithdrawalTransportResponse(comparisonPayload())).toEqual(comparisonPayload())
  })

  it('accepts decimal rates', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0].applicable_rate = 0.5
    expect(isWithdrawalComparisonResponse(payload)).toBe(true)
  })

  it('accepts empty assumptions and warnings', () => {
    const payload = comparisonPayload()
    expect(payload.comparison.scenarios[0].assumptions).toEqual([])
    expect(payload.comparison.scenarios[0].warnings).toEqual([])
    expect(isWithdrawalComparisonResponse(payload)).toBe(true)
  })

  it('accepts a numeric citation page', () => {
    expect(isWithdrawalComparisonResponse(comparisonPayload())).toBe(true)
  })

  it('accepts a null citation page', () => {
    const payload = comparisonPayload()
    payload.evidence[0].page = null
    expect(isWithdrawalComparisonResponse(payload)).toBe(true)
  })

  it.each(['MISSING_INPUT', 'RULE_ERROR'])('accepts the %s error family', (family) => {
    expect(isWithdrawalErrorResponse(errorPayload(family))).toBe(true)
  })

  it('rejects a missing required field', () => {
    const payload = comparisonPayload() as Record<string, unknown>
    delete payload.claim_validation
    expect(() => parseWithdrawalTransportResponse(payload)).toThrow(WithdrawalTransportValidationError)
  })

  it('rejects an unknown scenario', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios = [scenario('annuity_unknown')]
    expect(isWithdrawalComparisonResponse(payload)).toBe(false)
  })

  it('rejects fractional-won amounts', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0].tax_value = 1.5
    expect(isWithdrawalComparisonResponse(payload)).toBe(false)
  })

  it.each([-0.1, 1.1])('rejects the out-of-range rate %s', (rate) => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0].applicable_rate = rate
    expect(isWithdrawalComparisonResponse(payload)).toBe(false)
  })

  it('rejects a non-string evidence ID array', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0].evidence_ids = [1] as unknown as string[]
    expect(isWithdrawalComparisonResponse(payload)).toBe(false)
  })

  it('rejects an invalid citation page type', () => {
    const payload = comparisonPayload()
    payload.evidence[0].page = '1' as unknown as number
    expect(isWithdrawalComparisonResponse(payload)).toBe(false)
  })

  it('rejects a payload mixing comparison and error responses', () => {
    const payload = { ...comparisonPayload(), ...errorPayload('RULE_ERROR') }
    expect(() => parseWithdrawalTransportResponse(payload)).toThrow(WithdrawalTransportValidationError)
  })
})
