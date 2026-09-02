import { describe, expect, it } from 'vitest'
import { parseRetrievedContext, presentRetrievedContext } from './retrieved-context'

const twoEvidence = [
  '[DOC doc41][PAGE 1][EVIDENCE doc41-p01-c02]',
  '연금저축 세액공제 한도는 연 600만원입니다.',
  '',
  '[DOC doc55][PAGE 10][EVIDENCE doc55-p10-c01]',
  'IRP를 포함한 합산 한도는 연 900만원입니다.',
].join('\n')

describe('retrieved context presentation parser', () => {
  it('parses two evidence blocks with DOC, PAGE, and excerpt', () => {
    expect(parseRetrievedContext(twoEvidence)).toEqual([
      {
        document: 'doc41',
        page: '1',
        evidenceId: 'doc41-p01-c02',
        excerpt: '연금저축 세액공제 한도는 연 600만원입니다.',
      },
      {
        document: 'doc55',
        page: '10',
        evidenceId: 'doc55-p10-c01',
        excerpt: 'IRP를 포함한 합산 한도는 연 900만원입니다.',
      },
    ])
    expect(presentRetrievedContext(twoEvidence)).toEqual({
      kind: 'items',
      items: parseRetrievedContext(twoEvidence),
    })
  })

  it('omits PAGE when the backend header has no PAGE tag', () => {
    expect(parseRetrievedContext('[DOC doc-no-page][EVIDENCE e-1]\n페이지 없는 근거')).toEqual([
      {
        document: 'doc-no-page',
        page: null,
        evidenceId: 'e-1',
        excerpt: '페이지 없는 근거',
      },
    ])
  })

  it('treats empty or whitespace-only context as none', () => {
    expect(presentRetrievedContext('')).toEqual({ kind: 'none' })
    expect(presentRetrievedContext('   \n')).toEqual({ kind: 'none' })
    expect(parseRetrievedContext('')).toEqual([])
  })

  it('does not dump raw context when parsing fails', () => {
    const raw = 'THIS_SHOULD_NOT_BE_TREATED_AS_AN_EXCERPT'
    expect(presentRetrievedContext(raw)).toEqual({ kind: 'unparseable' })
    expect(parseRetrievedContext(raw)).toEqual([])
  })
})
