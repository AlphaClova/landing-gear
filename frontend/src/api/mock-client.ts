import type { PensionApiClient } from './client'
import type { AnswerRequest, ChatResponse } from '../types/api'

const wait = (signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Request aborted', 'AbortError'))
      return
    }
    const timer = window.setTimeout(resolve, 900)
    signal?.addEventListener('abort', () => {
      window.clearTimeout(timer)
      reject(new DOMException('Request aborted', 'AbortError'))
    }, { once: true })
  })

export class MockPensionApiClient implements PensionApiClient {
  async answer(request: AnswerRequest, options?: { signal?: AbortSignal }): Promise<ChatResponse> {
    await wait(options?.signal)

    if (request.mode === 'withdrawal-decision') {
      return {
        type: 'clarification',
        requestId: crypto.randomUUID(),
        requiredSlots: [
          { key: 'retirementBenefit', label: '예상 퇴직급여', inputType: 'number', unit: '원', options: null },
          { key: 'expectedTax', label: '예상 퇴직소득세', inputType: 'number', unit: '원', options: null },
        ],
      }
    }

    const message = request.message.trim()
    const requestId = crypto.randomUUID()

    if (message.includes('[error]')) return { type: 'error', requestId, code: 'MOCK_ERROR', message: '답변을 불러오지 못했습니다.', retryable: true }
    if (message.includes('[clarification]')) return {
      type: 'clarification', requestId, requiredSlots: [
        { key: 'pensionType', label: '현재 가입한 퇴직연금 유형', inputType: 'text', unit: null, options: null },
        { key: 'companyPlan', label: '회사에서 제공하는 퇴직연금 제도', inputType: 'text', unit: null, options: null },
      ],
    }
    if (message === '원리금보장형과 실적배당형은 어떻게 비교해야 하나요?') return {
      type: 'result', requestId, mode: 'pension-chat',
      conclusion: '상품 유형별 차이를 비교할 수 있습니다.',
      explanation: '실제 상품 데이터 연결 전에는 유형별 확인 항목만 안내합니다.',
      comparison: null, citations: [],
    }
    if (message.includes('[limitation]') || message !== 'DB형과 DC형의 차이는 무엇인가요?') return {
      type: 'limitation', requestId,
      availableAnswer: 'DB형과 DC형의 일반적인 차이는 안내할 수 있습니다.',
      message: '개인에게 더 유리한 유형은 회사 규약과 개인 조건 없이 단정할 수 없습니다.',
      requiredConditions: ['회사 퇴직연금 안내서 또는 가입 확인서를 확인해 주세요.'],
    }

    const citations = [
      { id: 'moel-retirement-pension', documentTitle: '고용노동부 · 퇴직연금이란?', page: null, excerpt: 'DB형과 DC형의 급여·부담금 확정 및 운용 주체를 설명합니다.' },
      { id: 'law-retirement-benefit', documentTitle: '국가법령정보센터 · 근로자퇴직급여 보장법', page: null, excerpt: 'DC형 회사 부담금의 법정 최소 기준을 설명합니다.' },
    ]
    return {
      type: 'result', requestId, mode: 'pension-chat',
      conclusion: 'DB형은 근로자가 받을 퇴직급여 수준이 사전에 정해지고 회사가 적립금을 운용하는 방식입니다.\n\nDC형은 회사가 납입할 부담금 수준이 정해지고 근로자가 적립금을 직접 운용하는 방식입니다. 따라서 DC형의 최종 퇴직급여는 운용 결과에 따라 달라질 수 있습니다.',
      explanation: 'DB형과 DC형은 사전에 정해지는 항목과 적립금 운용 주체가 다릅니다.',
      comparison: {
        title: 'DB형·DC형 비교',
        rows: [
          { id: 'fixed-item', label: '사전에 정해지는 것', optionA: '퇴직 시 받을 급여 수준', optionB: '회사가 납입할 부담금 수준', unit: null, valueSource: 'rule' },
          { id: 'manager', label: '적립금 운용 주체', optionA: '회사', optionB: '근로자', unit: null, valueSource: 'rule' },
          { id: 'result-impact', label: '운용 결과의 영향', optionA: '근로자의 퇴직급여와 직접 연동되지 않음', optionB: '최종 퇴직급여에 반영될 수 있음', unit: null, valueSource: 'rule' },
          { id: 'contribution', label: '회사 부담금', optionA: '급여 지급 능력을 확보하도록 적립·운용', optionB: '연간 임금총액의 12분의 1 이상', unit: null, valueSource: 'rule' },
        ],
        reasons: [], checks: [], formula: null, citations,
      },
      citations,
    }
  }
}
