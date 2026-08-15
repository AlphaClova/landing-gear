import { useRef } from 'react'
import type { RefObject } from 'react'
import type { ChatResponse } from '../../types/api'
import { ErrorState, StatusBadge } from '../../components/ui'
import { getPensionResultViewModel, pensionSuggestions } from './pension-chat-view-model'
import { getProductComparisonViewModel } from './product-comparison-view-model'
import { ProductComparison } from './ProductComparison'

interface PensionChatProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onCancel: () => void
  onRetry: () => void
  response: ChatResponse | null
  answeredQuestion: string
  pendingQuestion: string
  loading: boolean
  error: string | null
  cancelled: boolean
}

function QuestionForm({ value, onChange, onSubmit, disabled, inputRef }: Pick<PensionChatProps, 'value' | 'onChange' | 'onSubmit'> & { disabled: boolean; inputRef: RefObject<HTMLTextAreaElement | null> }) {
  return <div className="pension-prompt">
    <label htmlFor="pension-question">질문 입력</label>
    <textarea ref={inputRef} id="pension-question" value={value} onChange={(event) => onChange(event.target.value)} placeholder="궁금한 연금 제도나 수령 방식을 질문해 보세요." rows={3} disabled={disabled} />
    <button type="button" onClick={onSubmit} disabled={disabled || !value.trim()}>질문하기</button>
  </div>
}

export function PensionChat(props: PensionChatProps) {
  const { value, onChange, onSubmit, onCancel, onRetry, response, answeredQuestion, pendingQuestion, loading, error, cancelled } = props
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const resultModel = response ? getPensionResultViewModel(answeredQuestion, response) : null
  const productModel = response ? getProductComparisonViewModel(answeredQuestion, response) : null
  const chooseQuestion = (question: string) => {
    onChange(question)
    window.requestAnimationFrame(() => inputRef.current?.focus())
  }

  const form = <QuestionForm value={value} onChange={onChange} onSubmit={onSubmit} disabled={loading} inputRef={inputRef} />

  return <section className="pension-slice" aria-labelledby="pension-title">
    <header className="pension-intro"><span className="eyebrow">연금 상담</span><h1 id="pension-title">연금 상담</h1><p>연금 제도와 수령 방식이 궁금하다면 질문해 보세요.</p></header>

    {!response && !loading && !error && !cancelled && <>
      {form}
      <section className="pension-suggestions" aria-labelledby="pension-suggestions-title"><h2 id="pension-suggestions-title">추천 질문</h2><div>{pensionSuggestions.map((question) => <button type="button" key={question} onClick={() => chooseQuestion(question)}>{question}</button>)}</div></section>
    </>}

    {response && <div className="pension-conversation">
      {answeredQuestion && <section className="asked-question"><span>내 질문</span><p>{answeredQuestion}</p></section>}

      {response.type === 'result' && productModel && <ProductComparison model={productModel} onQuestion={chooseQuestion} />}
      {response.type === 'result' && resultModel && <>
        <section className="pension-answer-section pension-conclusion"><StatusBadge tone="navy">핵심 결론</StatusBadge><h2>DB형과 DC형의 핵심 차이</h2>{response.conclusion.split('\n\n').map((paragraph) => <p key={paragraph}>{paragraph}</p>)}</section>
        {response.comparison && <section className="pension-answer-section pension-comparison"><h2>{response.comparison.title}</h2><div className="pension-comparison-table" role="table" aria-label="DB형과 DC형 비교"><div className="pension-comparison-head" role="row"><strong role="columnheader">비교 항목</strong><strong role="columnheader">DB형</strong><strong role="columnheader">DC형</strong></div>{response.comparison.rows.map((row) => <div className="pension-comparison-row" role="row" key={row.id}><strong role="rowheader">{row.label}</strong><span role="cell">{row.optionA}</span><span role="cell">{row.optionB}</span></div>)}</div></section>}
        {resultModel && <>
          <section className="pension-answer-section pension-details"><h2>상세 설명</h2><div>{resultModel.sections.map((section) => <article key={section.title}><h3>{section.title}</h3><p>{section.content}</p></article>)}</div></section>
          <section className="pension-caution"><StatusBadge tone="amber">확인할 사항</StatusBadge><p>{resultModel.caution}</p></section>
          <section className="pension-answer-section pension-evidence" aria-labelledby="evidence-title"><h2 id="evidence-title">근거와 출처</h2><div className="evidence-list">{resultModel.evidence.map((evidence) => <details className="evidence-item" key={evidence.id}><summary><span className="evidence-summary"><b>{evidence.organization}</b><strong>{evidence.title}</strong><small>{evidence.location}</small><em>{evidence.supportedContent}</em></span><span className="evidence-toggle" aria-hidden="true">근거 보기</span></summary><div className="evidence-detail"><p>{evidence.excerpt}</p><a href={evidence.url} target="_blank" rel="noreferrer">공식 페이지에서 확인하기</a><div className="evidence-claims"><b>연결된 답변 항목</b><ul>{evidence.claimLabels.map((label) => <li key={label}>{label}</li>)}</ul></div></div></details>)}</div></section>
          <section className="pension-followups" aria-labelledby="followups-title"><h2 id="followups-title">이어진 질문</h2><div>{resultModel.followUpQuestions.map((question) => <button type="button" key={question} onClick={() => chooseQuestion(question)}>{question}</button>)}</div></section>
        </>}
      </>}
      {response.type === 'result' && !productModel && !resultModel && <section className="pension-answer-section"><StatusBadge tone="navy">확인된 결과</StatusBadge><h2>{response.conclusion}</h2><p>{response.explanation}</p></section>}

      {response.type === 'clarification' && <section className="pension-answer-section pension-state"><StatusBadge tone="amber">추가 정보 필요</StatusBadge><h2>현재 안내할 수 있는 내용</h2><p>DB형과 DC형의 일반적인 제도 차이는 설명할 수 있습니다.</p><h3>정확한 답변을 위해 부족한 정보</h3><p>현재 가입 유형이나 회사의 제도는 제공된 정보만으로 확인할 수 없습니다.</p><h3>필요한 조건</h3><ul>{response.requiredSlots.map((slot) => <li key={slot.key}>{slot.label}</li>)}</ul></section>}
      {response.type === 'limitation' && <section className="pension-answer-section pension-state pension-state--amber"><StatusBadge tone="amber">답변 범위 안내</StatusBadge><h2>현재 안내할 수 있는 내용</h2>{response.availableAnswer && <p>{response.availableAnswer}</p>}<h3>확인할 수 없는 내용</h3><p>{response.message}</p><h3>다음 확인 방법</h3><ul>{response.requiredConditions.map((condition) => <li key={condition}>{condition}</li>)}</ul></section>}
      {response.type === 'error' && <ErrorState message={response.message} onRetry={response.retryable ? onRetry : undefined} />}
    </div>}

    {loading && <section className="pension-loading" aria-live="polite" aria-busy="true"><div className="asked-question"><span>내 질문</span><p>{pendingQuestion}</p></div><div className="pension-skeleton" aria-hidden="true"><i /><i /><i /></div><strong>답변을 준비하고 있습니다</strong><button type="button" onClick={onCancel}>요청 취소</button></section>}
    {error && <ErrorState message={error} onRetry={onRetry} />}
    {cancelled && !loading && <section className="pension-cancelled" role="status"><strong>요청이 취소되었습니다.</strong><p>입력한 질문은 그대로 유지됩니다.</p></section>}

    {(response || loading || error || cancelled) && <section className="pension-new-question" aria-labelledby="new-question-title"><h2 id="new-question-title">새 질문</h2>{form}</section>}
  </section>
}
