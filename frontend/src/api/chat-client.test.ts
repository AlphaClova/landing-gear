import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  CHAT_CLIENT_USER_MESSAGES,
  ChatApiClientError,
  DEFAULT_CHAT_TIMEOUT_MS,
  HttpChatApiClient,
  parseChatTimeoutMs,
} from './chat-client'
import type { ChatApiRequest } from './chat-request'

const request: ChatApiRequest = {
  session_id: '123e4567-e89b-42d3-a456-426614174000',
  question: '일시금과 연금을 비교해 주세요.',
  profile: { retirement_amount_won: 300_000_000, expected_tax_won: 24_000_000 },
}

const responseBody = (type: 'clarification' | 'result' | 'limitation' | 'error' = 'result') => ({
  type,
  message: '응답입니다.',
  required_slots: type === 'clarification'
    ? [{ name: 'expected_tax_won', prompt: '기준 세액을 입력해 주세요.', reason: null }]
    : [],
  comparison: null,
  withdrawal_result: null,
  citations: [],
  request_id: 'req-1',
})

const withdrawalResult = () => ({
  comparison: {
    scenarios: [{
      scenario: 'lump_sum', tax_value: 24_000_000, applicable_rate: 1,
      difference_vs_lump_sum: 0, formula: '24000000 * 1.00',
      rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0',
      evidence_ids: [], assumptions: [], warnings: [],
    }],
    result_type: 'exact', unit: 'KRW',
  },
  evidence: [],
  applied_rules: [{ rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0' }],
  claim_validation: {
    validations: [], unsupported_claim_count: 0, validated_claim_count: 0, unsupported_claim_rate: 0,
  },
})

const jsonResponse = (body: unknown, status = 200, requestId = 'req-1') => new Response(JSON.stringify(body), {
  status,
  headers: {
    'Content-Type': 'application/json',
    ...(requestId ? { 'X-Request-Id': requestId } : {}),
  },
})

const errorEnvelope = (code = 'internal_error', message = 'internal diagnostic') => ({
  type: 'error', code, message, request_id: 'req-1',
})

const expectClientError = async (promise: Promise<unknown>) => {
  try {
    await promise
    throw new Error('expected request to fail')
  } catch (error) {
    expect(error).toBeInstanceOf(ChatApiClientError)
    return error as ChatApiClientError
  }
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('/v1/chat HTTP client', () => {
  it('binds the default fetcher to a valid receiver (regression: real browsers reject a detached fetch call)', async () => {
    // Node/jsdom's fetch does not enforce the receiver checks a real browser's
    // native `window.fetch` does, so this codepath looked fine under every
    // Node-based test and even most manual browser checks (any script that
    // happens to rebind fetch first — e.g. wrapping it for logging — hides the
    // bug). A real, unmodified Chromium throws
    // `TypeError: Failed to execute 'fetch' on 'Window': Illegal invocation`
    // the moment `this.fetcher(...)` (a member-expression call whose `this` is
    // the client instance, not `window`) invokes an unbound `fetch` reference.
    // This fake reproduces that exact browser contract so the regression is
    // caught by a fast, deterministic unit test instead of only in a browser.
    const strictBrowserFetch = function (this: unknown) {
      if (this !== globalThis) {
        throw new TypeError("Failed to execute 'fetch' on 'Window': Illegal invocation")
      }
      return Promise.resolve(jsonResponse(responseBody()))
    } as typeof fetch
    const originalFetch = globalThis.fetch
    globalThis.fetch = strictBrowserFetch
    try {
      // No explicit fetcher argument: exercises the class's own default capture.
      const client = new HttpChatApiClient('/api', 1000)
      await expect(client.chat(request)).resolves.toMatchObject({ type: 'result' })
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('posts the exact request as JSON to the normalized URL', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(responseBody()))
    const client = new HttpChatApiClient('http://localhost:8000/', 1000, fetcher)
    await client.chat(request)
    expect(fetcher).toHaveBeenCalledWith('http://localhost:8000/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: expect.any(AbortSignal),
    })
  })

  it.each(['result', 'clarification', 'limitation'] as const)('returns a validated %s response', async (type) => {
    const client = new HttpChatApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(responseBody(type))))
    await expect(client.chat(request)).resolves.toMatchObject({ type, request_id: 'req-1' })
  })

  it('returns a validated withdrawal_result', async () => {
    const body = { ...responseBody(), withdrawal_result: withdrawalResult() }
    const client = new HttpChatApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body)))
    await expect(client.chat(request)).resolves.toMatchObject({ withdrawal_result: { claim_validation: { unsupported_claim_count: 0 } } })
  })

  it('accepts matching body and X-Request-Id values', async () => {
    const client = new HttpChatApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(responseBody())))
    await expect(client.chat(request)).resolves.toMatchObject({ request_id: 'req-1' })
  })

  it('rejects mismatched body and X-Request-Id values as a protocol error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(responseBody(), 200, 'req-other'))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'protocol', retryable: false, userMessage: CHAT_CLIENT_USER_MESSAGES.protocol })
  })

  it.each([
    [400, 'tool_argument_error', false, CHAT_CLIENT_USER_MESSAGES.input],
    [422, 'validation_error', false, CHAT_CLIENT_USER_MESSAGES.input],
    [500, 'internal_error', true, CHAT_CLIENT_USER_MESSAGES.server],
    [502, 'upstream_error', true, CHAT_CLIENT_USER_MESSAGES.server],
    [503, 'tool_unavailable', true, CHAT_CLIENT_USER_MESSAGES.tool],
    [504, 'upstream_timeout', true, CHAT_CLIENT_USER_MESSAGES.timeout],
  ] as const)('maps HTTP %i with retryable=%s', async (status, code, retryable, userMessage) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(errorEnvelope(code), status))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'http', status, code, retryable, userMessage, requestId: 'req-1' })
  })

  it('maps FastAPI default 422 separately without inventing an A code', async () => {
    const body = { detail: [{ type: 'missing', loc: ['body', 'question'], msg: 'Field required', input: {} }] }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body, 422, 'req-validation'))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'http', status: 422, code: null, retryable: false, requestId: 'req-validation' })
  })

  it('preserves the server message only as debug information', async () => {
    const serverMessage = 'B tool internal stack details'
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(errorEnvelope('tool_unavailable', serverMessage), 503))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error.debugMessage).toBe(serverMessage)
    expect(error.userMessage).toBe(CHAT_CLIENT_USER_MESSAGES.tool)
    expect(error.userMessage).not.toContain(serverMessage)
  })

  it('maps a fetch failure to a retryable network error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'network', retryable: true, status: null })
  })

  describe('diagnosticCode classification (chat-diagnostics.ts)', () => {
    it('confirms WD-CORS when the request fails but a no-cors probe to the same host succeeds', async () => {
      const fetcher = vi.fn<typeof fetch>((url) => (
        typeof url === 'string' && url.endsWith('/health')
          ? Promise.resolve(new Response(null, { status: 200 }))
          : Promise.reject(new TypeError('Failed to fetch'))
      ))
      const error = await expectClientError(new HttpChatApiClient('https://api.example.com', 1000, fetcher).chat(request))
      expect(error).toMatchObject({ kind: 'network', diagnosticCode: 'WD-CORS' })
      expect(fetcher).toHaveBeenCalledWith('https://api.example.com/health', expect.objectContaining({ mode: 'no-cors' }))
    })

    it('confirms WD-NETWORK when both the request and the reachability probe fail', async () => {
      const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'))
      const error = await expectClientError(new HttpChatApiClient('https://api.example.com', 1000, fetcher).chat(request))
      expect(error).toMatchObject({ kind: 'network', diagnosticCode: 'WD-NETWORK' })
    })

    it('assigns WD-TIMEOUT to a client-side timeout', async () => {
      vi.useFakeTimers()
      const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
      }))
      const pending = new HttpChatApiClient('/api', 25, fetcher).chat(request)
      const errorPromise = expectClientError(pending)
      await vi.advanceTimersByTimeAsync(25)
      expect(await errorPromise).toMatchObject({ kind: 'timeout', diagnosticCode: 'WD-TIMEOUT' })
    })

    it('assigns WD-ABORTED to a caller-cancelled request', async () => {
      const controller = new AbortController()
      const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
      }))
      const pending = new HttpChatApiClient('/api', 1000, fetcher).chat(request, { signal: controller.signal })
      controller.abort()
      expect(await expectClientError(pending)).toMatchObject({ kind: 'cancelled', diagnosticCode: 'WD-ABORTED' })
    })

    it('assigns WD-HTTP-5XX and WD-HTTP-4XX by status class', async () => {
      const serverError = await expectClientError(new HttpChatApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(errorEnvelope('internal_error'), 500))).chat(request))
      expect(serverError).toMatchObject({ diagnosticCode: 'WD-HTTP-5XX' })
      const clientError = await expectClientError(new HttpChatApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(errorEnvelope('validation_error'), 422))).chat(request))
      expect(clientError).toMatchObject({ diagnosticCode: 'WD-HTTP-4XX' })
    })

    it('assigns WD-PROTOCOL to a contract-violating 200 response', async () => {
      const error = await expectClientError(new HttpChatApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ type: 'result' }))).chat(request))
      expect(error).toMatchObject({ kind: 'protocol', diagnosticCode: 'WD-PROTOCOL' })
    })
  })

  it('distinguishes the client timeout as retryable', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
    }))
    const pending = new HttpChatApiClient('/api', 25, fetcher).chat(request)
    const errorPromise = expectClientError(pending)
    await vi.advanceTimersByTimeAsync(25)
    const error = await errorPromise
    expect(error).toMatchObject({ kind: 'timeout', retryable: true, userMessage: CHAT_CLIENT_USER_MESSAGES.timeout })
  })

  it('distinguishes caller cancellation and does not mark it retryable', async () => {
    const controller = new AbortController()
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
    }))
    const pending = new HttpChatApiClient('/api', 1000, fetcher).chat(request, { signal: controller.signal })
    controller.abort()
    const error = await expectClientError(pending)
    expect(error).toMatchObject({ kind: 'cancelled', retryable: false })
  })

  it.each([
    ['an empty body', new Response('', { status: 200, headers: { 'Content-Type': 'application/json' } })],
    ['a non-JSON body', new Response('plain text', { status: 200, headers: { 'Content-Type': 'text/plain' } })],
    ['malformed JSON', new Response('{', { status: 200, headers: { 'Content-Type': 'application/json' } })],
  ])('maps %s to a protocol error', async (_label, response) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response)
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'protocol', retryable: false })
  })

  it('rejects an invalid HTTP 200 payload as a protocol error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ type: 'result' }))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'protocol', retryable: false })
  })

  it('rejects an invalid HTTP error body as a protocol error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ message: 'raw error' }, 500))
    const error = await expectClientError(new HttpChatApiClient('/api', 1000, fetcher).chat(request))
    expect(error).toMatchObject({ kind: 'protocol', status: 500, retryable: false })
  })

  it.each([undefined, '', 'not-a-number', '0', '-1', '1.5'])('uses the safe timeout fallback for %j', (value) => {
    expect(parseChatTimeoutMs(value)).toBe(DEFAULT_CHAT_TIMEOUT_MS)
  })

  it('accepts a positive integer timeout', () => {
    expect(parseChatTimeoutMs('45000')).toBe(45_000)
  })

  it('cleans up its timeout and caller abort listener after completion', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const removeListener = vi.spyOn(controller.signal, 'removeEventListener')
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(responseBody()))
    await new HttpChatApiClient('/api', 1000, fetcher).chat(request, { signal: controller.signal })
    expect(vi.getTimerCount()).toBe(0)
    expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function))
  })
})
