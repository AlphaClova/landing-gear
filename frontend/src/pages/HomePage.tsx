import { useEffect, useRef, useState } from 'react'
import ArrowRight from 'lucide-react/dist/esm/icons/arrow-right.mjs'
import { pensionApi } from '../api'
import { AppShell, Button, Card } from '../components/ui'
import type { AppPage } from '../components/ui'
import { StatusPanel } from '../components/StatusPanel'
import { PensionChat } from '../features/pension-chat/PensionChat'
import { WithdrawalDecision } from '../features/withdrawal-decision/WithdrawalDecision'
import { AuxiliaryPage } from './AuxiliaryPages'
import type { ChatResponse, ResponseMode } from '../types/api'

type Page = 'start' | AppPage
const examples = ['DB형과 DC형의 차이는 무엇인가요?', '퇴직금은 어떤 방식으로 받을 수 있나요?', '연금저축과 IRP는 어떻게 다른가요?']

export function HomePage() {
  const [page, setPage] = useState<Page>(() => {
    const hash = window.location.hash.slice(1) as AppPage
    return ['home', 'pension-chat', 'withdrawal-decision', 'calculator', 'history', 'settings', 'help'].includes(hash) ? hash : 'start'
  })
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [answeredQuestion, setAnsweredQuestion] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [cancelled, setCancelled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const requestRef = useRef<AbortController | null>(null)

  useEffect(() => () => requestRef.current?.abort(), [])
  const navigate = (next: Page) => { requestRef.current?.abort(); setPage(next); setResponse(null); setError(null); setAnsweredQuestion(''); setPendingQuestion(''); setCancelled(false); window.location.hash = next === 'start' ? '' : next }
  const selectMode = (mode: ResponseMode) => navigate(mode)
  const askFromHome = () => { if (message.trim()) navigate('pension-chat') }
  const cancel = () => { requestRef.current?.abort(); requestRef.current = null; setLoading(false); setPendingQuestion(''); setError(null); setCancelled(true) }
  const submit = async () => {
    if (page !== 'pension-chat' && page !== 'withdrawal-decision') return
    const question = message.trim()
    if (!question || loading) return
    requestRef.current?.abort(); const controller = new AbortController(); requestRef.current = controller
    setLoading(true); setError(null); setCancelled(false); setPendingQuestion(question)
    if (page === 'withdrawal-decision') setResponse(null)
    let timedOut = false
    const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, 20_000)
    try { const nextResponse = await pensionApi.answer({ message: question, mode: page }, { signal: controller.signal }); setResponse(nextResponse); setAnsweredQuestion(question); setPendingQuestion('') }
    catch (caught) { if (caught instanceof DOMException && caught.name === 'AbortError') { if (timedOut) setError('응답 시간이 초과되었습니다. 입력한 질문을 유지한 채 다시 시도할 수 있습니다.'); return }; setError(caught instanceof Error ? caught.message : '알 수 없는 오류가 발생했습니다.') }
    finally { window.clearTimeout(timeout); if (requestRef.current === controller) setLoading(false) }
  }

  if (page === 'start') return <main className="start-page">
    <header className="start-header"><button className="login-link">로그인</button></header>
    <section className="start-hero hero-content" aria-labelledby="start-heading">
      <div className="brand-stage"><div className="brand-aura" aria-hidden="true" /><h1 id="start-heading" className="hero-wordmark">Landing Gear<span className="wordmark-star" aria-hidden="true">✦</span><span className="wordmark-curve" aria-hidden="true" /></h1></div>
      <p>연금의 선택을 더 선명하게.</p>
      <div className="start-actions"><Button onClick={() => navigate('home')}>시작하기 <ArrowRight aria-hidden="true" /></Button><button className="guide-link">서비스 안내</button></div>
    </section>
  </main>

  return <AppShell current={page} onNavigate={navigate} menuOpen={menuOpen} onMenuOpen={() => setMenuOpen(true)} onMenuClose={() => setMenuOpen(false)}>
    <main className="workspace">
      {page === 'home' ? <>
        <section className="home-hero"><div><h1>무엇을 도와드릴까요?</h1><p>궁금한 내용을 묻거나 필요한 계산을 시작해 보세요.</p></div><div className="home-prompt"><label className="sr-only" htmlFor="home-question">연금 질문</label><input id="home-question" value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && askFromHome()} placeholder="연금에 대해 궁금한 점을 입력해 주세요." /><Button onClick={askFromHome} disabled={!message.trim()}><span aria-hidden="true">✦</span> 질문하기</Button></div></section>
        <div className="home-grid"><div><div className="feature-cards"><button className="card feature-card" onClick={() => selectMode('pension-chat')}><img src="/assets/icons/pension-chat.svg" alt="" /><div><h2>연금 상담</h2><p>연금 제도와 수령 방식을 간단히 확인해 보세요.</p></div><span aria-hidden="true">→</span></button><button className="card feature-card" onClick={() => selectMode('withdrawal-decision')}><img src="/assets/icons/withdrawal-decision.svg" alt="" /><div><h2>인출 의사결정</h2><p>일시금과 연금 수령 방식의 차이를 비교해 보세요.</p></div><span aria-hidden="true">→</span></button></div><Card className="examples"><h2>이런 질문으로 시작해 보세요</h2><div>{examples.map((example) => <button key={example} onClick={() => { setMessage(example); navigate('pension-chat') }}><span aria-hidden="true">?</span>{example}<b aria-hidden="true">›</b></button>)}</div></Card></div><Card className="principles"><h2>답변 원칙</h2><ul><li><img src="/assets/icons/exact-estimate.svg" alt="" />확정값과 예상값 구분</li><li><img src="/assets/icons/evidence.svg" alt="" />근거와 출처 제공</li><li><img src="/assets/icons/condition.svg" alt="" />필요한 조건만 확인</li></ul></Card></div>
      </> : page === 'pension-chat' ? <PensionChat value={message} onChange={setMessage} onSubmit={submit} onCancel={cancel} onRetry={submit} response={response} answeredQuestion={answeredQuestion} pendingQuestion={pendingQuestion} loading={loading} error={error} cancelled={cancelled} /> : page === 'withdrawal-decision' ? <div className="feature-layout"><div><WithdrawalDecision value={message} onChange={setMessage} onSubmit={submit} disabled={loading} /></div><StatusPanel response={response} loading={loading} error={error} onCancel={cancel} onRetry={submit} /></div> : <AuxiliaryPage page={page} />}
    </main>
  </AppShell>
}
