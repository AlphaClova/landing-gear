import type { PensionApiClient } from './client'
import type { AnswerRequest, ChatResponse } from '../types/api'

export class HttpPensionApiClient implements PensionApiClient {
  constructor(private readonly baseUrl: string) {}

  async answer(request: AnswerRequest, options?: { signal?: AbortSignal }): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: options?.signal,
    })

    if (!response.ok) {
      throw new Error(`API request failed (${response.status})`)
    }

    return (await response.json()) as ChatResponse
  }
}

