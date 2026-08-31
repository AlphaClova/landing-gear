import { useRef, useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MockPensionApiClient } from '../../api/mock-client'
import type { ChatResponse } from '../../types/api'
import { PensionChat } from './PensionChat'

const client = new MockPensionApiClient()

function PensionHarness() {
  const [value, setValue] = useState('')
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [answeredQuestion, setAnsweredQuestion] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cancelled, setCancelled] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const submit = async () => {
    const question = value.trim()
    if (!question || loading) return
    controller.current = new AbortController()
    setLoading(true); setPendingQuestion(question); setError(null); setCancelled(false)
    try { setResponse(await client.answer({ mode: 'pension-chat', message: question }, { signal: controller.current.signal })); setAnsweredQuestion(question) }
    catch { setError('답변을 불러오지 못했습니다.') }
    finally { setLoading(false); setPendingQuestion('') }
  }
  const cancel = () => { controller.current?.abort(); setLoading(false); setCancelled(true) }
  return <PensionChat value={value} onChange={setValue} onSubmit={submit} onCancel={cancel} onRetry={submit} response={response} answeredQuestion={answeredQuestion} pendingQuestion={pendingQuestion} loading={loading} error={error} cancelled={cancelled} />
}

describe('연금 상담 회귀', () => {
  it('화면명과 행동 제목을 반복하지 않고 하나의 h1을 사용한다', () => {
    render(<PensionHarness />)
    expect(screen.getByText('연금 상담')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: '연금이 궁금하신가요?' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: '연금 상담' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('추천 질문을 키보드로 선택할 수 있다', async () => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    const suggestion = screen.getByRole('button', { name: 'DB형과 DC형의 차이는 무엇인가요?' })
    suggestion.focus()
    await user.keyboard('{Enter}')
    expect(screen.getByLabelText('질문 입력')).toHaveValue('DB형과 DC형의 차이는 무엇인가요?')
  })

  it('추천 질문은 입력창에만 반영하고 빈 질문은 제출하지 않는다', async () => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    const submit = screen.getByRole('button', { name: '질문하기' })
    expect(submit).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'DB형과 DC형의 차이는 무엇인가요?' }))
    expect(screen.getByLabelText('질문 입력')).toHaveValue('DB형과 DC형의 차이는 무엇인가요?')
    expect(screen.queryByText('답변을 준비하고 있습니다')).not.toBeInTheDocument()
    expect(screen.queryByText('DB형과 DC형의 핵심 차이')).not.toBeInTheDocument()
  })

  it('DB형·DC형 질문 제출 시 핵심 결론과 비교 결과를 표시한다', async () => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    await user.click(screen.getByRole('button', { name: 'DB형과 DC형의 차이는 무엇인가요?' }))
    await user.click(screen.getByRole('button', { name: '질문하기' }))
    expect(screen.getByText('답변을 준비하고 있습니다')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'DB형과 DC형의 핵심 차이' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('답변 결과')).toHaveFocus())
    expect(screen.getByRole('table', { name: 'DB형과 DC형 비교' })).toBeInTheDocument()
    expect(screen.getByText('연간 임금총액의 12분의 1 이상')).toBeInTheDocument()
  })

  it('상품 유형 비교는 두 유형을 동등하게 표시하고 없는 숫자를 만들지 않는다', async () => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    await user.click(screen.getByRole('button', { name: '원리금보장형과 실적배당형은 어떻게 비교해야 하나요?' }))
    await user.click(screen.getByRole('button', { name: '질문하기' }))
    expect(await screen.findByRole('heading', { name: '상품 유형별 차이를 확인하세요' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: '원리금보장형' })).toHaveLength(1)
    expect(screen.getAllByRole('heading', { name: '실적배당형' })).toHaveLength(1)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getAllByText('데이터 연결 필요').length).toBeGreaterThan(0)
    expect(screen.queryByText(/\d+(\.\d+)?%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/\d[,.]?\d*원/)).not.toBeInTheDocument()
  })

  it.each([
    ['[clarification]', '추가 정보 필요'],
    ['[limitation]', '답변 범위 안내'],
    ['[error]', '답변을 불러오지 못했습니다.'],
  ])('%s 상태를 표시한다', async (question, expected) => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    fireEvent.change(screen.getByLabelText('질문 입력'), { target: { value: question } })
    await user.click(screen.getByRole('button', { name: '질문하기' }))
    expect(await screen.findByText(expected)).toBeInTheDocument()
  })

  it('후속 질문은 새 입력에 포커스되고 기존 답변은 유지된다', async () => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    await user.click(screen.getByRole('button', { name: 'DB형과 DC형의 차이는 무엇인가요?' }))
    await user.click(screen.getByRole('button', { name: '질문하기' }))
    await screen.findByRole('heading', { name: 'DB형과 DC형의 핵심 차이' })
    const followUp = screen.getByRole('button', { name: '현재 가입한 퇴직연금 유형은 어디서 확인하나요?' })
    await user.click(followUp)
    const input = screen.getByLabelText('질문 입력')
    await waitFor(() => expect(input).toHaveFocus())
    expect(input).toHaveValue('현재 가입한 퇴직연금 유형은 어디서 확인하나요?')
    expect(screen.getByRole('heading', { name: 'DB형과 DC형의 핵심 차이' })).toBeInTheDocument()
  })

  it('로딩을 status로 알리고 중복 제출을 막으며 취소 후 질문을 유지한다', async () => {
    const user = userEvent.setup()
    render(<PensionHarness />)
    await user.click(screen.getByRole('button', { name: 'DB형과 DC형의 차이는 무엇인가요?' }))
    await user.click(screen.getByRole('button', { name: '질문하기' }))
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: '질문하기' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '요청 취소' }))
    expect(screen.getByRole('status')).toHaveTextContent('요청이 취소되었습니다.')
    expect(screen.getByLabelText('질문 입력')).toHaveValue('DB형과 DC형의 차이는 무엇인가요?')
  })
})
