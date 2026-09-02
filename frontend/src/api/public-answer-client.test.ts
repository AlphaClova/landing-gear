import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  adaptPublicAnswerToChatResponse,
  getPublicAnswerUrl,
  HttpPublicAnswerClient,
  parsePublicAnswerResponse,
} from './public-answer-client'
import { ChatApiClientError } from './chat-client'

const payload = {
  question_id: 'Q-1',
  question: 'DB형과 DC형은 어떻게 다른가요?',
  retrieved_context: '[DOC x]\nexcerpt',
  think_trace: 'internal',
  answer: 'DB형은 급여가 사전확정되고 회사가 운용합니다. DC형은 근로자가 운용합니다.',
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('public GET /answer client', () => {
  it('builds GET /answer with question_id and question query params', () => {
    expect(getPublicAnswerUrl('http://127.0.0.1:8000/', 'Q-1', '연금저축과 IRP'))
      .toBe('http://127.0.0.1:8000/answer?question_id=Q-1&question=%EC%97%B0%EA%B8%88%EC%A0%80%EC%B6%95%EA%B3%BC+IRP')
  })

  it('parses the 5-string public contract and maps answer as the UI source of truth', () => {
    expect(parsePublicAnswerResponse(payload)).toEqual(payload)
    expect(adaptPublicAnswerToChatResponse(payload)).toMatchObject({
      type: 'result',
      requestId: 'Q-1',
      conclusion: payload.answer,
      explanation: '',
      comparison: null,
      citations: [],
    })
  })

  it('does not treat think_trace as the displayed answer', () => {
    const mapped = adaptPublicAnswerToChatResponse(payload)
    expect(mapped.type === 'result' && mapped.conclusion).not.toContain('internal')
    expect(JSON.stringify(mapped)).not.toContain('think_trace')
  })

  it('rejects a legacy ChatResponse-shaped payload', () => {
    expect(() => parsePublicAnswerResponse({
      type: 'limitation',
      requestId: 'request-1',
      availableAnswer: 'DB형과 DC형의 일반적인 차이는 안내할 수 있습니다.',
      message: '개인에게 더 유리한 유형은 단정할 수 없습니다.',
      requiredConditions: ['회사 퇴직연금 안내서'],
    })).toThrow(ChatApiClientError)
  })

  it('sends GET /answer and returns the parsed public payload', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(payload), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }))
    const client = new HttpPublicAnswerClient('http://127.0.0.1:8000', 1000, fetcher)
    await expect(client.answer('Q-1', payload.question)).resolves.toEqual(payload)
    const [url, init] = fetcher.mock.calls[0]
    expect(url).toBe(getPublicAnswerUrl('http://127.0.0.1:8000', 'Q-1', payload.question))
    expect(init).toEqual(expect.objectContaining({ method: 'GET' }))
    const parsedUrl = new URL(String(url))
    expect(parsedUrl.searchParams.get('question_id')).toBe('Q-1')
    expect(parsedUrl.searchParams.get('question')).toBe(payload.question)
  })

  it('does not call the default native fetch as a method (Illegal invocation)', async () => {
    const brandedFetch = vi.fn(function (this: unknown) {
      if (this != null && this !== globalThis && this !== window) {
        throw new TypeError("Failed to execute 'fetch' on 'Window': Illegal invocation")
      }
      return Promise.resolve(new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }))
    }) as typeof fetch
    vi.stubGlobal('fetch', brandedFetch)
    const client = new HttpPublicAnswerClient('http://127.0.0.1:8000', 1000)
    await expect(client.answer('Q-1', payload.question)).resolves.toEqual({
      question_id: payload.question_id,
      question: payload.question,
      retrieved_context: payload.retrieved_context,
      think_trace: payload.think_trace,
      answer: payload.answer,
    })
    expect(brandedFetch).toHaveBeenCalled()
  })
})
