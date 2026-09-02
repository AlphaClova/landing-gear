import { ChatApiClientError } from '../../api/chat-client'
import type { ChatApiCitation, ChatApiResponseTransport } from '../../api/chat-response'
import {
  adaptPublicAnswerToChatResponse,
  publicAnswerClient,
} from '../../api/public-answer-client'
import type { PublicAnswerClient } from '../../api/public-answer-client'
import { MockPensionApiClient } from '../../api/mock-client'
import type { PensionApiClient } from '../../api/client'
import type { ChatResponse, Citation, ComparisonResult, RequiredSlot } from '../../types/api'

export type PensionChatApiMode = 'mock' | 'http'

export const parsePensionChatApiMode = (value: string | undefined): PensionChatApiMode =>
  value === 'http' ? 'http' : 'mock'

const SAFE_RESPONSE_ERROR = '답변을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'

const mapCitation = (citation: ChatApiCitation): Citation => ({
  id: citation.id,
  documentId: citation.document_id,
  documentTitle: citation.section?.trim() || citation.document_id,
  page: citation.page,
  section: citation.section,
  source: citation.source,
  excerpt: citation.excerpt || null,
  url: citation.url,
})

const mapComparison = (
  response: ChatApiResponseTransport,
  citations: Citation[],
): ComparisonResult | null => {
  if (!response.comparison) return null
  const [optionA, optionB] = response.comparison.options
  return {
    title: response.comparison.title,
    rows: response.comparison.rows.map((row, index) => ({
      id: `comparison-${index + 1}`,
      label: row.label,
      optionA: optionA ? row.values[optionA] ?? null : null,
      optionB: optionB ? row.values[optionB] ?? null : null,
      unit: null,
      valueSource: 'rule',
    })),
    reasons: response.comparison.note ? [response.comparison.note] : [],
    checks: [],
    formula: null,
    citations,
  }
}

const mapRequiredSlot = (slot: ChatApiResponseTransport['required_slots'][number]): RequiredSlot => ({
  key: slot.name,
  label: slot.prompt,
  inputType: 'text',
  unit: null,
  options: null,
  reason: slot.reason,
})

export function adaptPensionChatResponse(response: ChatApiResponseTransport): ChatResponse {
  if (response.type === 'error') {
    return {
      type: 'error',
      requestId: response.request_id,
      code: 'CHAT_RESPONSE_ERROR',
      message: SAFE_RESPONSE_ERROR,
      retryable: true,
    }
  }

  if (response.type === 'clarification') {
    return {
      type: 'clarification',
      requestId: response.request_id,
      message: response.message,
      requiredSlots: response.required_slots.map(mapRequiredSlot),
    }
  }

  if (response.type === 'limitation') {
    return {
      type: 'limitation',
      requestId: response.request_id,
      availableAnswer: null,
      message: response.message,
      requiredConditions: response.required_slots.map((slot) => slot.prompt),
    }
  }

  const citations = response.citations.map(mapCitation)
  return {
    type: 'result',
    requestId: response.request_id,
    mode: 'pension-chat',
    conclusion: response.message,
    explanation: '',
    comparison: mapComparison(response, citations),
    citations,
  }
}

export interface PensionChatProvider {
  answer(question: string, signal?: AbortSignal): Promise<ChatResponse>
}

export class HttpPensionChatProvider implements PensionChatProvider {
  constructor(
    private readonly client: PublicAnswerClient = publicAnswerClient,
    private readonly questionId: () => string = () => crypto.randomUUID(),
  ) {}

  async answer(question: string, signal?: AbortSignal): Promise<ChatResponse> {
    const payload = await this.client.answer(this.questionId(), question, { signal })
    return adaptPublicAnswerToChatResponse(payload)
  }
}

export class MockPensionChatProvider implements PensionChatProvider {
  constructor(private readonly client: PensionApiClient = new MockPensionApiClient()) {}

  answer(question: string, signal?: AbortSignal): Promise<ChatResponse> {
    return this.client.answer({ message: question, mode: 'pension-chat' }, { signal })
  }
}

export function createPensionChatProvider(
  mode: PensionChatApiMode = parsePensionChatApiMode(import.meta.env.VITE_CHAT_API_MODE),
  client: PublicAnswerClient = publicAnswerClient,
): PensionChatProvider {
  return mode === 'http' ? new HttpPensionChatProvider(client) : new MockPensionChatProvider()
}

export const pensionChatProvider = createPensionChatProvider()

export { ChatApiClientError }
