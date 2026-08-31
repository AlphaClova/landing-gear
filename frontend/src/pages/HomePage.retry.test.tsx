import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatResponse } from '../types/api'

const mocks = vi.hoisted(() => ({ answer: vi.fn() }))

vi.mock('../features/pension-chat/pension-chat-provider', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../features/pension-chat/pension-chat-provider')>()),
  pensionChatProvider: { answer: mocks.answer },
}))

import { HomePage } from './HomePage'

const result = (message: string): ChatResponse => ({
  type: 'result', requestId: 'request-success', mode: 'pension-chat', conclusion: message,
  explanation: '', comparison: null, citations: [],
})

const responseError: ChatResponse = {
  type: 'error', requestId: 'request-error', code: 'CHAT_RESPONSE_ERROR',
  message: '답변을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.', retryable: true,
}

beforeEach(() => {
  mocks.answer.mockReset()
  window.history.replaceState(null, '', '#pension-chat')
})

afterEach(() => {
  window.history.replaceState(null, '', window.location.pathname)
})

describe('일반 연금 상담 HTTP 재시도', () => {
  it('실패 후 상태를 해제하고 이전 질문으로 재호출한 뒤 성공 결과로 교체한다', async () => {
    const user = userEvent.setup()
    let resolveRetry!: (response: ChatResponse) => void
    const retryResponse = new Promise<ChatResponse>((resolve) => { resolveRetry = resolve })
    mocks.answer
      .mockResolvedValueOnce(responseError)
      .mockReturnValueOnce(retryResponse)
      .mockRejectedValueOnce(new Error('new question failed'))
      .mockRejectedValueOnce(new Error('retry failed again'))

    render(<HomePage />)
    const input = screen.getByLabelText('질문 입력')
    await user.type(input, '실패한 원래 질문')
    await user.click(screen.getByRole('button', { name: '질문하기' }))

    expect(await screen.findByText('요청을 완료하지 못했습니다.')).toBeInTheDocument()
    expect(screen.queryByText('답변을 준비하고 있습니다')).not.toBeInTheDocument()
    const retryButton = screen.getByRole('button', { name: '다시 시도' })
    expect(retryButton).toBeEnabled()

    const newQuestionInput = screen.getByLabelText('질문 입력')
    await user.clear(newQuestionInput)
    await user.type(newQuestionInput, '새로 입력한 질문')
    await user.click(retryButton)

    expect(mocks.answer).toHaveBeenNthCalledWith(2, '실패한 원래 질문', expect.any(AbortSignal))
    expect(screen.getByText('답변을 준비하고 있습니다')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '질문하기' })).toBeDisabled()

    resolveRetry(result('재시도 성공 실제 답변'))
    expect(await screen.findByText('재시도 성공 실제 답변')).toBeInTheDocument()
    expect(screen.queryByText('요청을 완료하지 못했습니다.')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '질문하기' }))
    await waitFor(() => expect(mocks.answer).toHaveBeenNthCalledWith(3, '새로 입력한 질문', expect.any(AbortSignal)))
    expect(await screen.findByText('요청을 완료하지 못했습니다.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '다시 시도' }))
    await waitFor(() => expect(mocks.answer).toHaveBeenCalledTimes(4))
    expect(mocks.answer).toHaveBeenLastCalledWith('새로 입력한 질문', expect.any(AbortSignal))
    expect(await screen.findByText('요청을 완료하지 못했습니다.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeEnabled()
  })
})
