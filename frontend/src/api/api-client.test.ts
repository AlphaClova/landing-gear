import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPensionApiClient } from '.'
import { ApiHttpError, ApiNetworkError, ApiResponseError } from './errors'
import { HttpPensionApiClient } from './http-client'
import { MockPensionApiClient } from './mock-client'

const request = { mode: 'pension-chat', message: 'test question' } as const
const validResponse = {
  type: 'result',
  requestId: 'request-1',
  mode: 'pension-chat',
  conclusion: 'conclusion',
  explanation: 'explanation',
  comparison: null,
  citations: [],
} as const

const jsonResponse = (body: unknown, init: ResponseInit = {}) => new Response(JSON.stringify(body), {
  status: 200,
  headers: { 'content-type': 'application/json' },
  ...init,
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('API client boundary', () => {
  it('selects the mock client only in mock mode', () => {
    expect(createPensionApiClient({ useMockApi: true, baseUrl: '/api', timeoutMs: 1000 }))
      .toBeInstanceOf(MockPensionApiClient)
  })

  it('selects the HTTP client in real mode', () => {
    expect(createPensionApiClient({ useMockApi: false, baseUrl: '/api', timeoutMs: 1000 }))
      .toBeInstanceOf(HttpPensionApiClient)
  })

  it('joins the base URL, passes an AbortSignal, and returns valid JSON', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(validResponse))
    vi.stubGlobal('fetch', fetchMock)
    const externalController = new AbortController()
    const client = new HttpPensionApiClient('https://api.example.test/v1/', 1000)

    await expect(client.answer(request, { signal: externalController.signal })).resolves.toEqual(validResponse)
    expect(fetchMock).toHaveBeenCalledWith('https://api.example.test/v1/answer', expect.objectContaining({
      method: 'POST',
      signal: expect.any(AbortSignal),
    }))
    const passedSignal = fetchMock.mock.calls[0][1]?.signal as AbortSignal
    externalController.abort()
    expect(passedSignal.aborted).toBe(true)
  })

  it('distinguishes an HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}, { status: 503 })))
    await expect(new HttpPensionApiClient('/api').answer(request)).rejects.toBeInstanceOf(ApiHttpError)
  })

  it('distinguishes a network error', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    await expect(new HttpPensionApiClient('/api').answer(request)).rejects.toBeInstanceOf(ApiNetworkError)
  })

  it('rejects a non-JSON response', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response('not json', {
      headers: { 'content-type': 'text/plain' },
    })))
    await expect(new HttpPensionApiClient('/api').answer(request)).rejects.toBeInstanceOf(ApiResponseError)
  })

  it('rejects malformed JSON without treating it as a network error', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response('{', {
      headers: { 'content-type': 'application/json' },
    })))
    await expect(new HttpPensionApiClient('/api').answer(request)).rejects.toBeInstanceOf(ApiResponseError)
  })

  it('rejects a response without the required discriminator', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ requestId: 'request-1' })))
    await expect(new HttpPensionApiClient('/api').answer(request)).rejects.toThrow('discriminator')
  })
})
