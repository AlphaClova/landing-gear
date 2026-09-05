import type { RetrievedContextView, RetrievedEvidenceItem } from '../types/api'

const CONTEXT_BLOCK = /\[DOC\s+([^\]]+)\](?:\[PAGE\s+([^\]]+)\])?(?:\[EVIDENCE\s+([^\]]+)\])?\n([\s\S]*?)(?=\n\[DOC\s+|$)/g

const optionalCapture = (value: string | undefined): string | null => {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

export function parseRetrievedContext(raw: string): RetrievedEvidenceItem[] {
  const items: RetrievedEvidenceItem[] = []
  const matcher = new RegExp(CONTEXT_BLOCK.source, CONTEXT_BLOCK.flags)
  let match: RegExpExecArray | null
  while ((match = matcher.exec(raw)) !== null) {
    items.push({
      document: match[1].trim(),
      page: optionalCapture(match[2]),
      evidenceId: optionalCapture(match[3]),
      excerpt: match[4].replace(/\n+$/, ''),
    })
  }
  return items
}

export function presentRetrievedContext(raw: string): RetrievedContextView {
  if (typeof raw !== 'string' || raw.trim() === '') {
    return { kind: 'none' }
  }
  try {
    const items = parseRetrievedContext(raw)
    if (items.length === 0) return { kind: 'unparseable' }
    return { kind: 'items', items }
  } catch {
    return { kind: 'unparseable' }
  }
}
