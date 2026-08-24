import { apiClientConfig } from './config'
import { getChatApiUrl } from './chat-request'
import type { ChatApiRequest } from './chat-request'
import { parseChatApiHttpError, parseChatApiResponse } from './chat-response'
import type {
  ChatApiErrorCode,
  ChatApiHttpError,
  ChatApiResponseTransport,
} from './chat-response'

export const DEFAULT_CHAT_TIMEOUT_MS = 30_000

export const CHAT_CLIENT_USER_MESSAGES = {
  input: '입력한 내용을 다시 확인해 주세요.',
  server: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
  tool: '계산에 필요한 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.',
  timeout: '응답 시간이 길어지고 있습니다. 잠시 후 다시 시도해 주세요.',
  protocol: '응답을 확인하는 중 문제가 발생했습니다.',
  cancelled: '요청이 취소되었습니다.',
} as const

export type ChatApiClientErrorKind = 'http' | 'network' | 'timeout' | 'cancelled' | 'protocol'

export interface ChatApiClientErrorDetails {
  kind: ChatApiClientErrorKind
  status: number | null
  code: ChatApiErrorCode | null
  requestId: string | null
  retryable: boolean
  debugMessage: string
  userMessage: string
  cause?: unknown
}

export class ChatApiClientError extends Error {
  readonly kind: ChatApiClientErrorKind
  readonly status: number | null
  readonly code: ChatApiErrorCode | null
  readonly requestId: string | null
  readonly retryable: boolean
  readonly debugMessage: string
  readonly userMessage: string

  constructor(details: ChatApiClientErrorDetails) {
    super(details.userMessage, details.cause === undefined ? undefined : { cause: details.cause })
    this.name = 'ChatApiClientError'
    this.kind = details.kind
    this.status = details.status
    this.code = details.code
    this.requestId = details.requestId
    this.retryable = details.retryable
    this.debugMessage = details.debugMessage
    this.userMessage = details.userMessage
  }
}

export interface ChatApiClientOptions {
  signal?: AbortSignal
}

export interface ChatApiClient {
  chat(request: ChatApiRequest, options?: ChatApiClientOptions): Promise<ChatApiResponseTransport>
}

export function parseChatTimeoutMs(value: string | undefined): number {
  if (!value) return DEFAULT_CHAT_TIMEOUT_MS
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : DEFAULT_CHAT_TIMEOUT_MS
}

const chatTimeoutMs = parseChatTimeoutMs(import.meta.env.VITE_CHAT_TIMEOUT_MS)

const isJsonContentType = (response: Response) => {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
  return contentType.includes('application/json') || contentType.includes('+json')
}

const requestIdFromHeader = (response: Response) => response.headers.get('x-request-id')?.trim() || null

const protocolError = (
  debugMessage: string,
  status: number | null,
  requestId: string | null,
  cause?: unknown,
) => new ChatApiClientError({
  kind: 'protocol',
  status,
  code: null,
  requestId,
  retryable: false,
  debugMessage,
  userMessage: CHAT_CLIENT_USER_MESSAGES.protocol,
  cause,
})

const assertMatchingRequestIds = (
  bodyRequestId: string | null,
  headerRequestId: string | null,
  status: number,
) => {
  if (bodyRequestId && headerRequestId && bodyRequestId !== headerRequestId) {
    throw protocolError('Response body and X-Request-Id header do not match', status, headerRequestId)
  }
}

const readJson = async (response: Response, requestId: string | null): Promise<unknown> => {
  if (!isJsonContentType(response)) {
    throw protocolError('Response Content-Type is not JSON', response.status, requestId)
  }
  const text = await response.text()
  if (!text.trim()) throw protocolError('Response body is empty', response.status, requestId)
  try {
    return JSON.parse(text) as unknown
  } catch (cause) {
    throw protocolError('Response body contains invalid JSON', response.status, requestId, cause)
  }
}

const isStructuredError = (value: ChatApiHttpError): value is Extract<ChatApiHttpError, { type: 'error' }> =>
  'type' in value

const retryableStatus = (status: number) => status >= 500

const userMessageForHttpError = (status: number, code: ChatApiErrorCode | null) => {
  if (code === 'upstream_timeout' || status === 504) return CHAT_CLIENT_USER_MESSAGES.timeout
  if (code === 'tool_unavailable' || status === 503) return CHAT_CLIENT_USER_MESSAGES.tool
  if (code === 'validation_error' || code === 'tool_argument_error' || status === 400 || status === 422) {
    return CHAT_CLIENT_USER_MESSAGES.input
  }
  return CHAT_CLIENT_USER_MESSAGES.server
}

const mapHttpError = (
  status: number,
  payload: ChatApiHttpError,
  headerRequestId: string | null,
): ChatApiClientError => {
  const structured = isStructuredError(payload)
  const code = structured ? payload.code : null
  const bodyRequestId = structured ? payload.request_id : null
  assertMatchingRequestIds(bodyRequestId, headerRequestId, status)
  return new ChatApiClientError({
    kind: 'http',
    status,
    code,
    requestId: bodyRequestId ?? headerRequestId,
    retryable: retryableStatus(status),
    debugMessage: structured
      ? payload.message
      : payload.detail.map((item) => `${item.loc.join('.')}: ${item.msg}`).join('; '),
    userMessage: userMessageForHttpError(status, code),
  })
}

export class HttpChatApiClient implements ChatApiClient {
  constructor(
    private readonly baseUrl: string = apiClientConfig.baseUrl,
    private readonly timeoutMs: number = chatTimeoutMs,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  async chat(request: ChatApiRequest, options: ChatApiClientOptions = {}): Promise<ChatApiResponseTransport> {
    const timeoutController = new AbortController()
    const requestController = new AbortController()
    const onCallerAbort = () => requestController.abort(options.signal?.reason)
    options.signal?.addEventListener('abort', onCallerAbort, { once: true })
    if (options.signal?.aborted) onCallerAbort()
    const timer = globalThis.setTimeout(() => {
      timeoutController.abort()
      requestController.abort()
    }, this.timeoutMs)

    try {
      const response = await this.fetcher(getChatApiUrl(this.baseUrl), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: requestController.signal,
      })
      const headerRequestId = requestIdFromHeader(response)
      const payload = await readJson(response, headerRequestId)

      if (!response.ok) {
        try {
          throw mapHttpError(response.status, parseChatApiHttpError(payload), headerRequestId)
        } catch (error) {
          if (error instanceof ChatApiClientError) throw error
          throw protocolError('HTTP error body does not match a supported contract', response.status, headerRequestId, error)
        }
      }

      try {
        const result = parseChatApiResponse(payload)
        assertMatchingRequestIds(result.request_id, headerRequestId, response.status)
        return result
      } catch (error) {
        if (error instanceof ChatApiClientError) throw error
        throw protocolError('Successful response does not match the /v1/chat contract', response.status, headerRequestId, error)
      }
    } catch (error) {
      if (error instanceof ChatApiClientError) throw error
      if (options.signal?.aborted) {
        throw new ChatApiClientError({
          kind: 'cancelled', status: null, code: null, requestId: null, retryable: false,
          debugMessage: 'Request was cancelled by the caller', userMessage: CHAT_CLIENT_USER_MESSAGES.cancelled, cause: error,
        })
      }
      if (timeoutController.signal.aborted) {
        throw new ChatApiClientError({
          kind: 'timeout', status: null, code: null, requestId: null, retryable: true,
          debugMessage: `Client timeout after ${this.timeoutMs}ms`, userMessage: CHAT_CLIENT_USER_MESSAGES.timeout, cause: error,
        })
      }
      throw new ChatApiClientError({
        kind: 'network', status: null, code: null, requestId: null, retryable: true,
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

export const chatApiClient: ChatApiClient = new HttpChatApiClient()
