import { pensionApi } from '../../api'
import type { WithdrawalDecisionInput, WithdrawalDecisionViewModel } from './withdrawal-decision-view-model'
import { createCompleteWithdrawalFixture, createErrorFixture, createLimitedFixture, createNeedsInputFixture } from './withdrawal-decision-mock'

export const isMockWithdrawalMode = import.meta.env.VITE_USE_MOCK_API !== 'false'

const requiredFields: Array<keyof WithdrawalDecisionInput> = ['retirementBenefitAmount', 'currentAge', 'pensionStartAge']

const wait = (signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  if (signal.aborted) return reject(new DOMException('Request aborted', 'AbortError'))
  const timer = window.setTimeout(resolve, 900)
  signal.addEventListener('abort', () => { window.clearTimeout(timer); reject(new DOMException('Request aborted', 'AbortError')) }, { once: true })
})

export async function requestWithdrawalDecision(input: WithdrawalDecisionInput, signal: AbortSignal): Promise<WithdrawalDecisionViewModel> {
  if (isMockWithdrawalMode) {
    await wait(signal)
    const missingFields = requiredFields.filter((field) => input[field] === null)
    if (missingFields.length) return createNeedsInputFixture(input, missingFields)
    if (input.retirementBenefitAmount === 999) return createErrorFixture(input)
    if (input.expectedReturnRate === -1) return createLimitedFixture(input)
    return createCompleteWithdrawalFixture(input)
  }

  const response = await pensionApi.answer({ mode: 'withdrawal-decision', message: JSON.stringify({ input }) }, { signal })
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
