/**
 * Frontend contract boundary. Replace these provisional shapes with imports from
 * the shared schema package once owners A/B publish the canonical contract.
 */
export type ResponseMode = 'pension-chat' | 'withdrawal-decision'

export interface Citation {
  id: string
  documentId?: string
  documentTitle: string
  page: number | string | null
  section?: string | null
  source?: string
  excerpt: string | null
  url?: string | null
}

export interface RequiredSlot {
  key: string
  label: string
  inputType: 'text' | 'number' | 'select'
  unit: string | null
  options: string[] | null
  reason?: string | null
}

export interface ComparisonRow {
  id: string
  label: string
  optionA: string | null
  optionB: string | null
  unit: string | null
  valueSource: 'rule' | 'user-input' | 'assumption' | 'needs-confirmation'
}

export interface ComparisonResult {
  title: string
  rows: ComparisonRow[]
  reasons: string[]
  checks: string[]
  formula: string | null
  citations: Citation[]
}

export interface RetrievedEvidenceItem {
  document: string
  page: string | null
  evidenceId: string | null
  excerpt: string
}

export type RetrievedContextView =
  | { kind: 'none' }
  | { kind: 'items'; items: RetrievedEvidenceItem[] }
  | { kind: 'unparseable' }

export type ChatResponse =
  | { type: 'clarification'; requestId: string; message?: string; requiredSlots: RequiredSlot[] }
  | { type: 'result'; requestId: string; mode: ResponseMode; conclusion: string; explanation: string; comparison: ComparisonResult | null; citations: Citation[]; retrievedContextView?: RetrievedContextView }
  | { type: 'limitation'; requestId: string; availableAnswer: string | null; message: string; requiredConditions: string[] }
  | { type: 'error'; requestId: string | null; code: string; message: string; retryable: boolean }

export interface AnswerRequest {
  message: string
  mode: ResponseMode
  sessionId?: string
  slots?: Record<string, string>
}

