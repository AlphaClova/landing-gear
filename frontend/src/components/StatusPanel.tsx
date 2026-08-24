import type { ChatResponse } from '../types/api'
import { EmptyState, ErrorState, EvidenceCard, LoadingState, StatusBadge } from './ui'

interface StatusPanelProps { response: ChatResponse | null; loading: boolean; error: string | null; onCancel: () => void; onRetry: () => void }

export function StatusPanel({ response, loading, error, onCancel, onRetry }: StatusPanelProps) {
  if (loading) return <LoadingState onCancel={onCancel} />
  if (error) return <ErrorState message={error} onRetry={onRetry} />
  if (!response) return <EmptyState />

  if (response.type === 'clarification') return <section className="result-panel"><StatusBadge tone="amber">추가 정보 필요</StatusBadge><h2>필요한 조건만 확인할게요.</h2><p className="result-intro">정확한 비교를 위해 아래 정보를 알려주세요.</p><ul className="condition-list">{response.requiredSlots.map((slot) => <li key={slot.key}><span>{slot.label}</span>{slot.unit && <small>{slot.unit}</small>}</li>)}</ul></section>
  if (response.type === 'limitation') return <section className="result-panel result-panel--amber"><StatusBadge tone="amber">답변 범위 안내</StatusBadge><h2>{response.message}</h2>{response.availableAnswer && <p>{response.availableAnswer}</p>}<ul className="condition-list">{response.requiredConditions.map((condition) => <li key={condition}>{condition}</li>)}</ul></section>
  if (response.type === 'error') return <ErrorState message={response.message} onRetry={response.retryable ? onRetry : undefined} />

  const citations = response.comparison?.citations.length ? response.comparison.citations : response.citations
  return <section className="result-panel"><div className="result-heading"><StatusBadge tone="navy">확인된 결과</StatusBadge><h2>{response.conclusion}</h2></div><p>{response.explanation}</p>{response.comparison && <div className="comparison"><h3>{response.comparison.title}</h3><div className="comparison-table" role="table">{response.comparison.rows.map((row) => <div className="comparison-row" role="row" key={row.id}><strong role="cell">{row.label}</strong><span role="cell">{row.optionA ?? '확인 필요'}</span><span role="cell">{row.optionB ?? '확인 필요'}</span><StatusBadge tone={row.valueSource === 'rule' || row.valueSource === 'user-input' ? 'navy' : 'gold'}>{row.valueSource === 'assumption' ? '예상값' : row.valueSource === 'needs-confirmation' ? '확인 필요' : '확정값'}</StatusBadge></div>)}</div></div>}{citations.length > 0 && <EvidenceCard>{citations.map((citation) => <article key={citation.id}><strong>{citation.documentTitle}</strong>{citation.page && <span>{citation.page}</span>}{citation.excerpt && <p>{citation.excerpt}</p>}</article>)}</EvidenceCard>}</section>
}
