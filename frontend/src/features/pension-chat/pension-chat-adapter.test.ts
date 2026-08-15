import { describe, expect, it } from 'vitest'
import type { ChatResponse } from '../../types/api'
import { dbDcQuestion, getPensionResultViewModel } from './pension-chat-view-model'
import { getProductComparisonViewModel, productComparisonQuestion } from './product-comparison-view-model'

const result: ChatResponse = {
  type: 'result', requestId: 'request-1', mode: 'pension-chat',
  conclusion: 'result', explanation: 'explanation', comparison: null, citations: [],
}

describe('pension view-model adapter boundary', () => {
  it('uses the DB/DC fixture only at the mock boundary', () => {
    expect(getPensionResultViewModel(dbDcQuestion, result, true)).not.toBeNull()
    expect(getPensionResultViewModel(dbDcQuestion, result, false)).toBeNull()
  })

  it('uses the product comparison fixture only at the mock boundary', () => {
    expect(getProductComparisonViewModel(productComparisonQuestion, result, true)).not.toBeNull()
    expect(getProductComparisonViewModel(productComparisonQuestion, result, false)).toBeNull()
  })
})
