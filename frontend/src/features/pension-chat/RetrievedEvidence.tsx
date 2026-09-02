import { useState } from 'react'
import type { RetrievedContextView, RetrievedEvidenceItem } from '../../types/api'

const EXCERPT_PREVIEW_CHARS = 180

function EvidenceExcerpt({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return null
  const needsToggle = text.length > EXCERPT_PREVIEW_CHARS
  const shown = !needsToggle || expanded ? text : `${text.slice(0, EXCERPT_PREVIEW_CHARS)}…`
  return <>
    <p className="retrieved-evidence-excerpt">{shown}</p>
    {needsToggle && <button type="button" className="evidence-more" onClick={() => setExpanded((open) => !open)}>{expanded ? '접기' : '더보기'}</button>}
  </>
}

function EvidenceCard({ item, index }: { item: RetrievedEvidenceItem; index: number }) {
  return <article className="evidence-item retrieved-evidence-card">
    <span className="retrieved-evidence-index">{index}.</span>
    <strong>{item.document}</strong>
    {item.page !== null && <small>p.{item.page}</small>}
    <EvidenceExcerpt text={item.excerpt} />
  </article>
}

export function RetrievedEvidenceSection({ view }: { view?: RetrievedContextView }) {
  if (!view || view.kind === 'none') return null
  if (view.kind === 'unparseable') {
    return <section className="pension-answer-section pension-evidence retrieved-evidence-panel" aria-labelledby="retrieved-evidence-title">
      <h2 id="retrieved-evidence-title">근거 문서</h2>
      <p>근거 정보를 표시하지 못했습니다.</p>
    </section>
  }
  return <section className="pension-answer-section pension-evidence retrieved-evidence-panel" aria-labelledby="retrieved-evidence-title">
    <details>
      <summary>
        <h2 id="retrieved-evidence-title">근거 문서 {view.items.length}건</h2>
        <span className="evidence-toggle evidence-toggle--closed">펼쳐보기</span>
        <span className="evidence-toggle evidence-toggle--open">접기</span>
      </summary>
      <ol className="evidence-list retrieved-evidence-list">
        {view.items.map((item, index) => (
          <li key={item.evidenceId ?? `${item.document}-${index}`}>
            <EvidenceCard item={item} index={index + 1} />
          </li>
        ))}
      </ol>
    </details>
  </section>
}
