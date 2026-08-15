import { describe, expect, it } from 'vitest'
import { createWithdrawalDecisionProvider } from './withdrawal-decision-adapter'
import { createCompleteWithdrawalFixture, exampleWithdrawalInput } from './withdrawal-decision-mock'
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

  it('rejects a missing amount instead of coercing it to zero', () => {
    const invalid = structuredClone(createCompleteWithdrawalFixture(exampleWithdrawalInput)) as unknown as {
      options: Array<{ confirmedAfterTaxAmount: Record<string, unknown> }>
    }
    delete invalid.options[0].confirmedAfterTaxAmount.amount

    expect(() => validateWithdrawalDecisionViewModel(invalid)).toThrow('required view model')
    expect(invalid.options[0].confirmedAfterTaxAmount.amount).toBeUndefined()
  })
})
