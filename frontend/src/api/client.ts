import type { AnswerRequest, ChatResponse } from '../types/api'

export interface PensionApiClient {
  answer(request: AnswerRequest, options?: { signal?: AbortSignal }): Promise<ChatResponse>
}

