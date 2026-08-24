import { describe, expect, it } from 'vitest'
import { adaptWithdrawalTransportResponse, buildWithdrawalDecisionChatRequest, createWithdrawalDecisionProvider } from './withdrawal-decision-adapter'
import { createCompleteWithdrawalFixture, exampleWithdrawalInput } from './withdrawal-decision-mock'
import { WithdrawalTransportValidationError } from './withdrawal-decision-transport'
import { validateWithdrawalDecisionViewModel } from './withdrawal-decision-validator'

describe('withdrawal decision adapter boundary', () => {
  it('returns the existing mock fixture as a WithdrawalDecisionViewModel', async () => {
    const provider = createWithdrawalDecisionProvider(true)
    const result = await provider.compare(exampleWithdrawalInput, new AbortController().signal)

    expect(result.status).toBe('complete')
    expect(result.options.map((option) => option.id)).toEqual(['lump_sum', 'pension_10y', 'pension_21y_plus'])
    expect(result.highlightedOptionId).toBeNull()
    expect(result.highlightReason).toBeNull()
  })

  const scenario = (
    scenarioId: 'lump_sum' | 'annuity_10_years' | 'annuity_21_plus_years',
    evidenceIds = ['evidence-1'],
  ) => ({
    scenario: scenarioId,
    tax_value: 14_000_000,
    applicable_rate: 0.7,
    difference_vs_lump_sum: 6_000_000,
    formula: '20000000 * 0.70',
    rule_id: 'RETIRE_TAX_RATE_BY_YEAR',
    rule_version: '1.0.0',
    evidence_ids: evidenceIds,
    assumptions: [] as unknown[],
    warnings: [] as unknown[],
  })

  const comparisonPayload = () => ({
    inputs: { retirement_amount: 200_000_000, deferred_retirement_tax: 20_000_000 },
    comparison: {
      result_type: 'exact',
      unit: 'KRW',
      scenarios: [
        scenario('lump_sum'),
        scenario('annuity_10_years'),
        scenario('annuity_21_plus_years'),
      ],
    },
    evidence: [{
      evidence_id: 'evidence-1',
      chunk_id: 'chunk-1',
      document_id: 'document-1',
      page: 2 as number | null,
      section: '연금수령시 퇴직소득세 절세혜택',
      quote: '오래 나누어 받을수록 세금이 줄어드는 구조다.',
      source_priority: 0,
      score: 1,
    }],
    applied_rules: [{ rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0' }],
    claim_validation: {
      validations: [{ claim_id: 'claim-1', supported: true, reasons: [] }],
      unsupported_claim_count: 0,
      validated_claim_count: 1,
      unsupported_claim_rate: 0,
    },
  })

  it('maps all B scenario IDs to the existing option IDs', () => {
    const result = adaptWithdrawalTransportResponse(comparisonPayload(), exampleWithdrawalInput)
    expect(result.options.map((option) => option.id)).toEqual(['lump_sum', 'pension_10y', 'pension_21y_plus'])
  })

  it('preserves integer won, decimal rate, and tax-saving semantics', () => {
    const payload = comparisonPayload()
    const result = adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput)
    expect(result.options[0].retirementIncomeTax.amount).toBe(14_000_000)
    expect(result.options[0].applicableRate).toBe(0.7)
    expect(result.options[0].taxSavingFromLumpSum?.amount).toBe(6_000_000)
    expect(result.options[0].differenceFromBaseline).toBeNull()
  })

  it('maps exact results while leaving absent calculated values unavailable', () => {
    const result = adaptWithdrawalTransportResponse(comparisonPayload(), exampleWithdrawalInput)
    expect(result.options[0].retirementIncomeTax.basis).toBe('exact')
    expect(result.options[0].confirmedAfterTaxAmount).toMatchObject({ amount: null, basis: 'unavailable' })
    expect(result.options[0].estimatedTotalCashflow).toMatchObject({ amount: null, basis: 'unavailable' })
    expect(result.options[0].healthInsuranceImpact).toMatchObject({ amount: null, basis: 'unavailable' })
  })

  it('links and deduplicates evidence by evidence ID', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[1].evidence_ids = ['evidence-1', 'evidence-1']
    const result = adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput)
    expect(result.evidence).toHaveLength(1)
    expect(result.options[1].evidenceIds).toEqual(['evidence-1', 'evidence-1'])
  })

  it('maps numeric evidence pages without inventing organization or URL fields', () => {
    const evidence = adaptWithdrawalTransportResponse(comparisonPayload(), exampleWithdrawalInput).evidence[0]
    expect(evidence).toMatchObject({
      id: 'evidence-1', documentId: 'document-1', chunkId: 'chunk-1', page: 2,
      title: '연금수령시 퇴직소득세 절세혜택', location: 'document-1 · 2페이지',
      summary: '오래 나누어 받을수록 세금이 줄어드는 구조다.', claimIds: [],
    })
    expect(evidence).not.toHaveProperty('organization')
    expect(evidence).not.toHaveProperty('url')
  })

  it('preserves a null evidence page', () => {
    const payload = comparisonPayload()
    payload.evidence[0].page = null
    const evidence = adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput).evidence[0]
    expect(evidence.page).toBeNull()
    expect(evidence.location).toBe('document-1')
  })

  it('preserves formula, rule ID, and rule version', () => {
    const option = adaptWithdrawalTransportResponse(comparisonPayload(), exampleWithdrawalInput).options[0]
    expect(option).toMatchObject({
      formula: '20000000 * 0.70',
      ruleId: 'RETIRE_TAX_RATE_BY_YEAR',
      ruleVersion: '1.0.0',
    })
  })

  it('accepts empty assumptions and warnings', () => {
    const option = adaptWithdrawalTransportResponse(comparisonPayload(), exampleWithdrawalInput).options[0]
    expect(option.reasons).toEqual([])
    expect(option.cautions).toEqual([])
  })

  it('maps string assumptions and warnings', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0].assumptions = ['10년간 수령']
    payload.comparison.scenarios[0].warnings = ['세법 변경 가능']
    const result = adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput)
    expect(result.options[0].reasons).toEqual(['10년간 수령'])
    expect(result.options[0].cautions).toEqual(['세법 변경 가능'])
    expect(result.assumptions[0].value).toBe('10년간 수령')
  })

  it.each(['assumptions', 'warnings'] as const)('rejects unsupported object %s safely', (field) => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0][field] = [{ text: 'not supported' }]
    expect(() => adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput))
      .toThrow(WithdrawalTransportValidationError)
  })

  it('rejects an unknown evidence reference', () => {
    const payload = comparisonPayload()
    payload.comparison.scenarios[0].evidence_ids = ['missing-evidence']
    expect(() => adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput))
      .toThrow('unknown evidence')
  })

  it('rejects a scenario rule absent from applied_rules', () => {
    const payload = comparisonPayload()
    payload.applied_rules = [{ rule_id: 'OTHER_RULE', rule_version: '1.0.0' }]
    expect(() => adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput))
      .toThrow('absent from applied_rules')
  })

  it('maps MISSING_INPUT to needs_input without exposing the raw message', () => {
    const payload = { errors: [{
      case: 'missing_retirement_amount', inputs: { retirement_amount: null },
      error_type: 'MissingInputError', message: 'sensitive raw engine message', api_error_family: 'MISSING_INPUT',
    }] }
    const result = adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput)
    expect(result).toMatchObject({ status: 'needs_input', missingFields: ['retirementBenefitAmount'], canRetry: false })
    expect(result.summary).not.toContain('sensitive raw engine message')
  })

  it('does not infer a C field for missing deferred_retirement_tax', () => {
    const payload = { errors: [{
      case: 'missing_tax', inputs: { deferred_retirement_tax: null },
      error_type: 'MissingInputError', message: 'raw', api_error_family: 'MISSING_INPUT',
    }] }
    expect(adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput).missingFields).toEqual([])
  })

  it('maps RULE_ERROR to a non-retryable error without exposing the raw message', () => {
    const payload = { errors: [{
      case: 'unknown_rule', inputs: { rule_version: 'unknown' },
      error_type: 'UnknownRuleVersionError', message: 'unknown-version raw detail', api_error_family: 'RULE_ERROR',
    }] }
    const result = adaptWithdrawalTransportResponse(payload, exampleWithdrawalInput)
    expect(result).toMatchObject({ status: 'error', canRetry: false, options: [] })
    expect(result.summary).not.toContain('unknown-version raw detail')
  })

  it('rejects a missing amount instead of coercing it to zero', () => {
    const invalid = structuredClone(createCompleteWithdrawalFixture(exampleWithdrawalInput)) as unknown as {
      options: Array<{ confirmedAfterTaxAmount: Record<string, unknown> }>
    }
    delete invalid.options[0].confirmedAfterTaxAmount.amount

    expect(() => validateWithdrawalDecisionViewModel(invalid)).toThrow('required view model')
    expect(invalid.options[0].confirmedAfterTaxAmount.amount).toBeUndefined()
  })

  it('maps the withdrawal input to the A chat request profile without a B field name', () => {
    const result = buildWithdrawalDecisionChatRequest('  수령 방식 비교  ', 'session-1', exampleWithdrawalInput)
    expect(result).toEqual({
      session_id: 'session-1',
      question: '수령 방식 비교',
      profile: { age: 55, retirement_amount_won: 300_000_000, expected_tax_won: 24_000_000 },
    })
    expect(result.profile).not.toHaveProperty('deferred_retirement_tax')
  })
})
