import { describe, expect, it, vi } from 'vitest'
import { ChatApiClientError } from '../../api/chat-client'
import type { PublicAnswerClient } from '../../api/public-answer-client'
import type { ChatApiResponseTransport } from '../../api/chat-response'
import {
  adaptPensionChatResponse,
  createPensionChatProvider,
  HttpPensionChatProvider,
  MockPensionChatProvider,
  parsePensionChatApiMode,
} from './pension-chat-provider'

const transport = (
  type: ChatApiResponseTransport['type'] = 'result',
  overrides: Partial<ChatApiResponseTransport> = {},
): ChatApiResponseTransport => ({
  type,
  message: type === 'result' ? '실제 질문에 대한 답변입니다.' : '추가 안내입니다.',
  required_slots: [],
  comparison: null,
  withdrawal_result: null,
  citations: [],
  request_id: 'request-1',
  ...overrides,
})

const publicPayload = (question: string, answer: string, questionId = 'Q-1') => ({
  question_id: questionId,
  question,
  retrieved_context: '',
  think_trace: '',
  answer,
})

describe('pension chat HTTP provider', () => {
  it('sends the exact entered question to GET /answer with a unique question_id', async () => {
    const answer = vi.fn<PublicAnswerClient['answer']>()
      .mockResolvedValueOnce(publicPayload('DB형과 DC형은 어떻게 다른가요?', '첫 번째 실제 답변', 'Q-1'))
      .mockResolvedValueOnce(publicPayload('오늘 비트코인 가격이 오를까요?', '두 번째 범위 밖 안내', 'Q-2'))
    const ids = ['Q-1', 'Q-2']
    const provider = new HttpPensionChatProvider({ answer }, () => ids.shift() ?? 'Q-fallback')

    const first = await provider.answer('DB형과 DC형은 어떻게 다른가요?')
    const second = await provider.answer('오늘 비트코인 가격이 오를까요?')

    expect(answer.mock.calls[0][0]).toBe('Q-1')
    expect(answer.mock.calls[0][1]).toBe('DB형과 DC형은 어떻게 다른가요?')
    expect(answer.mock.calls[1][0]).toBe('Q-2')
    expect(answer.mock.calls[1][1]).toBe('오늘 비트코인 가격이 오를까요?')
    expect(first).toMatchObject({ type: 'result', conclusion: '첫 번째 실제 답변' })
    expect(second).toMatchObject({ type: 'result', conclusion: '두 번째 범위 밖 안내' })
    expect(first.type === 'result' && first.conclusion).not.toBe(second.type === 'result' && second.conclusion)
  })

  it('maps result and snake_case comparison fields without a mock fixture', () => {
    const response = adaptPensionChatResponse(transport('result', {
      message: '서버가 만든 연금 답변',
      comparison: {
        title: '비교', options: ['DB', 'DC'], note: '참고',
        rows: [{ label: '운용 주체', values: { DB: '회사', DC: '가입자' } }],
      },
    }))
    expect(response).toMatchObject({
      type: 'result', conclusion: '서버가 만든 연금 답변',
      comparison: { rows: [{ optionA: '회사', optionB: '가입자' }] },
    })
  })

  it('maps clarification prompts and reasons', () => {
    const response = adaptPensionChatResponse(transport('clarification', {
      message: '가입 유형을 알려 주세요.',
      required_slots: [{ name: 'plan_type', prompt: '가입 유형', reason: '맞춤 답변에 필요합니다.' }],
    }))
    expect(response).toMatchObject({
      type: 'clarification', message: '가입 유형을 알려 주세요.',
      requiredSlots: [{ key: 'plan_type', label: '가입 유형', reason: '맞춤 답변에 필요합니다.' }],
    })
  })

  it('maps limitation using the server answer instead of DB/DC mock text', () => {
    expect(adaptPensionChatResponse(transport('limitation', { message: '가상자산 가격 전망은 답변 범위 밖입니다.' })))
      .toEqual({
        type: 'limitation', requestId: 'request-1', availableAnswer: null,
        message: '가상자산 가격 전망은 답변 범위 밖입니다.', requiredConditions: [],
      })
  })

  it('never exposes a server error message', () => {
    const response = adaptPensionChatResponse(transport('error', { message: 'internal stack and provider secret' }))
    expect(response).toMatchObject({ type: 'error', message: '답변을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.' })
    expect(response).not.toHaveProperty('message', 'internal stack and provider secret')
  })

  it.each([12, null])('preserves citation page %s and source metadata', (page) => {
    const response = adaptPensionChatResponse(transport('result', {
      citations: [{
        id: 'evidence-1', document_id: 'doc-1', page, section: '제1장', source: '기관',
        excerpt: '근거 문장', url: 'https://example.test/source',
      }],
    }))
    expect(response.type === 'result' && response.citations[0]).toMatchObject({
      documentId: 'doc-1', page, section: '제1장', source: '기관', excerpt: '근거 문장',
      url: 'https://example.test/source',
    })
  })

  it('forwards cancellation and keeps timeout/network errors retryable', async () => {
    const controller = new AbortController()
    const cancelled = new ChatApiClientError({
      kind: 'cancelled', status: null, code: null, requestId: null, retryable: false,
      debugMessage: 'debug', userMessage: '요청이 취소되었습니다.',
    })
    const answer = vi.fn<PublicAnswerClient['answer']>().mockRejectedValue(cancelled)
    const provider = new HttpPensionChatProvider({ answer }, () => 'Q-1')
    controller.abort()
    await expect(provider.answer('질문', controller.signal)).rejects.toBe(cancelled)
    expect(answer.mock.calls[0][2]?.signal).toBe(controller.signal)
  })
})

describe('pension chat mode regression', () => {
  it.each([[undefined, 'mock'], ['mock', 'mock'], ['http', 'http'], ['invalid', 'mock']] as const)(
    'parses %s as %s', (value, expected) => expect(parsePensionChatApiMode(value)).toBe(expected),
  )

  it('uses separate HTTP and mock providers', () => {
    expect(createPensionChatProvider('http', { answer: vi.fn() })).toBeInstanceOf(HttpPensionChatProvider)
    expect(createPensionChatProvider('mock')).toBeInstanceOf(MockPensionChatProvider)
  })

  it('keeps the existing DB/DC demonstration in mock mode', async () => {
    const provider = new MockPensionChatProvider()
    const response = await provider.answer('DB형과 DC형의 차이는 무엇인가요?')
    expect(response).toMatchObject({ type: 'result', mode: 'pension-chat' })
    expect(response.type === 'result' && response.conclusion).toContain('DB형')
  })
})
