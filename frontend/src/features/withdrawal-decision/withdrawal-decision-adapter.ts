import { isMockApiEnabled, pensionApi } from '../../api'
import type { PensionApiClient } from '../../api'
import type { ChatResponse } from '../../types/api'
import type { WithdrawalDecisionInput, WithdrawalDecisionViewModel } from './withdrawal-decision-view-model'
import { createCompleteWithdrawalFixture, createErrorFixture, createLimitedFixture, createNeedsInputFixture } from './withdrawal-decision-mock'
import { validateWithdrawalDecisionViewModel } from './withdrawal-decision-validator'

export const isMockWithdrawalMode = isMockApiEnabled

const requiredFields: Array<keyof WithdrawalDecisionInput> = ['retirementBenefitAmount', 'currentAge', 'pensionStartAge']

const wait = (signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal.aborted) return reject(new DOMException('Request aborted', 'AbortError'))
  const timer = window.setTimeout(resolve, 900)
  signal.addEventListener('abort', () => { window.clearTimeout(timer); reject(new DOMException('Request aborted', 'AbortError')) }, { once: true })
})

export interface WithdrawalDecisionProvider {
  compare(input: WithdrawalDecisionInput, signal: AbortSignal): Promise<WithdrawalDecisionViewModel>
}

class MockWithdrawalDecisionProvider implements WithdrawalDecisionProvider {
  async compare(input: WithdrawalDecisionInput, signal: AbortSignal): Promise<WithdrawalDecisionViewModel> {
    await wait(signal)
    const missingFields = requiredFields.filter((field) => input[field] === null)
    const result = missingFields.length
      ? createNeedsInputFixture(input, missingFields)
      : input.retirementBenefitAmount === 999
        ? createErrorFixture(input)
        : input.expectedReturnRate === -1
          ? createLimitedFixture(input)
          : createCompleteWithdrawalFixture(input)
    return validateWithdrawalDecisionViewModel(result)
  }
}

export function adaptWithdrawalChatResponse(response: ChatResponse, input: WithdrawalDecisionInput): WithdrawalDecisionViewModel {
  const apiBoundary: WithdrawalDecisionViewModel = {
    status: 'limited', scenarioTitle: '퇴직급여 수령 방식 비교', input, missingFields: [],
    summary: '', limitations: [], options: [], assumptions: [], evidence: [],
    baselineOptionId: null, highlightedOptionId: null, highlightReason: null,
    canCompare: false, canRetry: false,
  }
  if (response.type === 'error') return { ...apiBoundary, status: 'error', summary: response.message, canRetry: response.retryable }
  if (response.type === 'clarification') return {
    ...apiBoundary, status: 'needs_input',
    summary: '금액 비교를 위해 추가 조건이 필요합니다.',
    missingFields: requiredFields.filter((field) => input[field] === null),
  }
  return {
    ...apiBoundary,
    summary: response.type === 'limitation' ? response.availableAnswer ?? response.message : response.conclusion,
    limitations: [response.type === 'limitation' ? response.message : '실제 Rule Engine 결과를 화면 계약으로 변환하는 서버 응답 합의가 필요합니다.'],
  }
}

class HttpWithdrawalDecisionProvider implements WithdrawalDecisionProvider {
  constructor(private readonly client: PensionApiClient) {}

  async compare(input: WithdrawalDecisionInput, signal: AbortSignal) {
    const response = await this.client.answer(
      { mode: 'withdrawal-decision', message: JSON.stringify({ input }) },
      { signal },
    )
    // TODO(A/B): Replace this explicit limitation boundary only after the
    // canonical withdrawal payload and calculation/evidence IDs are finalized.
    return validateWithdrawalDecisionViewModel(adaptWithdrawalChatResponse(response, input))
  }
}

export function createWithdrawalDecisionProvider(
  useMockApi: boolean,
  client: PensionApiClient = pensionApi,
): WithdrawalDecisionProvider {
  return useMockApi ? new MockWithdrawalDecisionProvider() : new HttpWithdrawalDecisionProvider(client)
}

const withdrawalDecisionProvider = createWithdrawalDecisionProvider(isMockWithdrawalMode)

export function requestWithdrawalDecision(input: WithdrawalDecisionInput, signal: AbortSignal) {
  return withdrawalDecisionProvider.compare(input, signal)
}
