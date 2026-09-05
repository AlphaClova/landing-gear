import { apiClientConfig } from './config'
import {
  ChatApiClientError,
  CHAT_CLIENT_USER_MESSAGES,
  parseChatTimeoutMs,
} from './chat-client'
import type { ChatResponse } from '../types/api'
import { presentRetrievedContext } from './retrieved-context'

export interface PublicAnswerResponse {
  question_id: string
  question: string
  retrieved_context: string
  think_trace: string
  answer: string
}

export interface PublicAnswerClientOptions {
  signal?: AbortSignal
}

export interface PublicAnswerClient {
  answer(questionId: string, question: string, options?: PublicAnswerClientOptions): Promise<PublicAnswerResponse>
}

const PUBLIC_ANSWER_FIELDS = [
  'question_id',
  'question',
  'retrieved_context',
  'think_trace',
  'answer',
] as const

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

export function getPublicAnswerUrl(
  baseUrl: string,
  questionId: string,
  question: string,
): string {
  const origin = baseUrl.replace(/\/+$/, '')
  const params = new URLSearchParams({
    question_id: questionId,
    question,
  })
  return `${origin}/answer?${params.toString()}`
}

export function parsePublicAnswerResponse(value: unknown): PublicAnswerResponse {
  if (!isRecord(value)) {
    throw new ChatApiClientError({
      kind: 'protocol',
      status: null,
      code: null,
      requestId: null,
      retryable: false,
      debugMessage: 'Public /answer payload is not an object',
      userMessage: CHAT_CLIENT_USER_MESSAGES.protocol,
    })
  }
  for (const field of PUBLIC_ANSWER_FIELDS) {
    if (typeof value[field] !== 'string') {
      throw new ChatApiClientError({
        kind: 'protocol',
        status: null,
        code: null,
        requestId: typeof value.question_id === 'string' ? value.question_id : null,
        retryable: false,
        debugMessage: `Public /answer field '${field}' is not a string`,
        userMessage: CHAT_CLIENT_USER_MESSAGES.protocol,
      })
    }
  }
  return {
    question_id: value.question_id as string,
    question: value.question as string,
    retrieved_context: value.retrieved_context as string,
    think_trace: value.think_trace as string,
    answer: value.answer as string,
  }
}

export function adaptPublicAnswerToChatResponse(payload: PublicAnswerResponse): ChatResponse {
  return {
    type: 'result',
    requestId: payload.question_id,
    mode: 'pension-chat',
    conclusion: payload.answer,
    explanation: '',
    comparison: null,
    citations: [],
    retrievedContextView: presentRetrievedContext(payload.retrieved_context),
  }
}

const isJsonContentType = (response: Response) => {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
  return contentType.includes('application/json') || contentType.includes('+json')
}

const browserFetch: typeof fetch = (input, init) => globalThis.fetch(input, init)

export class HttpPublicAnswerClient implements PublicAnswerClient {
  private readonly fetcher: typeof fetch

  constructor(
    private readonly baseUrl: string = apiClientConfig.baseUrl,
    private readonly timeoutMs: number = parseChatTimeoutMs(import.meta.env.VITE_CHAT_TIMEOUT_MS),
    fetcher?: typeof fetch,
  ) {
    this.fetcher = fetcher ?? browserFetch
  }

  async answer(
    questionId: string,
    question: string,
    options: PublicAnswerClientOptions = {},
  ): Promise<PublicAnswerResponse> {
    const timeoutController = new AbortController()
    const requestController = new AbortController()
    const onCallerAbort = () => requestController.abort(options.signal?.reason)
    options.signal?.addEventListener('abort', onCallerAbort, { once: true })
    if (options.signal?.aborted) onCallerAbort()
    const timer = globalThis.setTimeout(() => {
      timeoutController.abort()
      requestController.abort()
    }, this.timeoutMs)
    const url = getPublicAnswerUrl(this.baseUrl, questionId, question)

    try {
      const response = await this.fetcher(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: requestController.signal,
      })
      const contentTypeOk = isJsonContentType(response)
      const text = await response.text()
      if (!contentTypeOk) {
        throw new ChatApiClientError({
          kind: 'protocol',
          status: response.status,
          code: null,
          requestId: questionId,
          retryable: false,
          debugMessage: 'Public /answer Content-Type is not JSON',
          userMessage: CHAT_CLIENT_USER_MESSAGES.protocol,
        })
      }
      if (!text.trim()) {
        throw new ChatApiClientError({
          kind: 'protocol',
          status: response.status,
          code: null,
          requestId: questionId,
          retryable: false,
          debugMessage: 'Public /answer body is empty',
          userMessage: CHAT_CLIENT_USER_MESSAGES.protocol,
        })
      }
      let payload: unknown
      try {
        payload = JSON.parse(text) as unknown
      } catch (cause) {
        throw new ChatApiClientError({
          kind: 'protocol',
          status: response.status,
          code: null,
          requestId: questionId,
          retryable: false,
          debugMessage: 'Public /answer body contains invalid JSON',
          userMessage: CHAT_CLIENT_USER_MESSAGES.protocol,
          cause,
        })
      }
      if (!response.ok) {
        throw new ChatApiClientError({
          kind: 'http',
          status: response.status,
          code: null,
          requestId: questionId,
          retryable: response.status >= 500,
          debugMessage: `Public /answer HTTP ${response.status}`,
          userMessage: response.status === 504
            ? CHAT_CLIENT_USER_MESSAGES.timeout
            : CHAT_CLIENT_USER_MESSAGES.server,
        })
      }
      const parsed = parsePublicAnswerResponse(payload)
      if (import.meta.env.DEV) {
        console.debug('[public-answer]', {
          question,
          url,
          answer: parsed.answer,
        })
      }
      return parsed
    } catch (error) {
      if (error instanceof ChatApiClientError) throw error
      if (options.signal?.aborted) {
        throw new ChatApiClientError({
          kind: 'cancelled',
          status: null,
          code: null,
          requestId: questionId,
          retryable: false,
          debugMessage: 'Request was cancelled by the caller',
          userMessage: CHAT_CLIENT_USER_MESSAGES.cancelled,
          cause: error,
        })
      }
      if (timeoutController.signal.aborted) {
        throw new ChatApiClientError({
          kind: 'timeout',
          status: null,
          code: null,
          requestId: questionId,
          retryable: true,
          debugMessage: `Client timeout after ${this.timeoutMs}ms`,
          userMessage: CHAT_CLIENT_USER_MESSAGES.timeout,
          cause: error,
        })
      }
      throw new ChatApiClientError({
        kind: 'network',
        status: null,
        code: null,
        requestId: questionId,
        retryable: true,
        debugMessage: error instanceof Error ? error.message : 'Unknown network failure',
        userMessage: CHAT_CLIENT_USER_MESSAGES.server,
        cause: error,
      })
    } finally {
      globalThis.clearTimeout(timer)
      options.signal?.removeEventListener('abort', onCallerAbort)
    }
  }
}

export const publicAnswerClient: PublicAnswerClient = new HttpPublicAnswerClient()
