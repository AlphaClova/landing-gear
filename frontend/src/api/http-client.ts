import type { PensionApiClient } from './client'
import type { AnswerRequest, ChatResponse } from '../types/api'
import { ApiHttpError, ApiNetworkError, ApiResponseError, ApiTimeoutError } from './errors'
import { parseChatResponse } from './response-validator'

export class HttpPensionApiClient implements PensionApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly timeoutMs = 10_000,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  async answer(request: AnswerRequest, options?: { signal?: AbortSignal }): Promise<ChatResponse> {
    const timeoutController = new AbortController()
    const timer = window.setTimeout(() => timeoutController.abort(), this.timeoutMs)
    const signal = options?.signal
      ? AbortSignal.any([options.signal, timeoutController.signal])
      : timeoutController.signal

    try {
      const response = await this.fetcher(`${this.baseUrl.replace(/\/+$/, '')}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(request),
        signal,
      })

      if (!response.ok) throw new ApiHttpError(response.status)

      const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
      if (!contentType.includes('application/json')) throw new ApiResponseError('API response is not JSON')

      let payload: unknown
      try {
        payload = await response.json()
      } catch (error) {
        throw new ApiResponseError(`API response contains invalid JSON: ${error instanceof Error ? error.name : 'parse error'}`)
      }
      return parseChatResponse(payload)
    } catch (error) {
      if (error instanceof ApiHttpError || error instanceof ApiResponseError) throw error
      if (options?.signal?.aborted) throw error
      if (timeoutController.signal.aborted) throw new ApiTimeoutError()
      throw new ApiNetworkError({ cause: error })
    } finally {
      window.clearTimeout(timer)
    }
  }
}
