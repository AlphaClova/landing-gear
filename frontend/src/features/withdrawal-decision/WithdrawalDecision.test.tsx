import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { WithdrawalDecision } from './WithdrawalDecision'

async function loadExample(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: '예시 조건 불러오기' }))
  expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveValue(200000000)
  expect(screen.getByLabelText(/현재 나이/)).toHaveValue(55)
  expect(screen.getByLabelText(/연금 수령 시작 나이/)).toHaveValue(60)
  expect(screen.getByLabelText(/예상수익률/)).toHaveValue(2)
}

describe('인출 의사결정 회귀', () => {
  it('필수 입력 누락 시 needs_input 요약과 누락 필드를 표시한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    expect(await screen.findByText('수령 방식의 일반적인 차이는 안내할 수 있지만 금액 비교를 위해 추가 조건이 필요합니다.')).toBeInTheDocument()
    expect(screen.getByText(/퇴직급여 예상액, 현재 나이, 연금 수령 시작 나이/)).toBeInTheDocument()
    expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveAttribute('aria-describedby', 'retirement-benefit-help')
    expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveAccessibleDescription(/필수 입력입니다.*원 단위/)
    await waitFor(() => expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveFocus())
  })

  it('예시 조건으로 세 방식과 확정·예상·조건부 상태를 구분한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    expect(screen.getByText('비교 결과를 준비하고 있습니다')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '수령 방식별 차이를 확인하세요' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: '일시금' }).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByRole('heading', { name: '10년 연금' }).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByRole('heading', { name: '21년 이상 연금' }).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('확정 계산').length).toBeGreaterThan(0)
    expect(screen.getAllByText('가정 기반 예상').length).toBeGreaterThan(0)
    expect(screen.getAllByText('추가 확인 필요')).toHaveLength(3)
    expect(screen.getAllByText('조건에 따라 달라짐')).toHaveLength(3)
    expect(screen.getAllByText('계산할 수 없음').length).toBeGreaterThan(0)
    expect(screen.queryByText(/추천|우위|가장 유리/)).not.toBeInTheDocument()
  })

  it('예상수익률 -1은 limited 상태로 확정값만 유지한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const rate = screen.getByLabelText(/예상수익률/)
    await user.clear(rate); await user.type(rate, '-1')
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    expect(await screen.findByText('확정 조건의 비교는 가능하지만 예상 현금흐름은 현재 가정으로 계산할 수 없습니다.')).toBeInTheDocument()
    expect(screen.getAllByText('계산할 수 없음').length).toBeGreaterThan(0)
    expect(screen.getAllByText('확정 계산').length).toBeGreaterThan(0)
  })

  it('퇴직급여 999는 error와 다시 시도를 표시하고 입력을 유지한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const benefit = screen.getByLabelText(/퇴직급여 예상액/)
    await user.clear(benefit); await user.type(benefit, '999')
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('비교 결과를 불러오지 못했습니다.')
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument()
    expect(benefit).toHaveValue(999)
  })

  it('결과 이후 조건을 수정해 다시 비교할 수 있다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    await screen.findByRole('heading', { name: '수령 방식별 차이를 확인하세요' })
    const inputPanel = screen.getByText('입력 조건 확인·수정')
    if (!inputPanel.closest('details')?.hasAttribute('open')) await user.click(inputPanel)
    const age = screen.getByLabelText(/현재 나이/)
    await user.clear(age); await user.type(age, '56')
    await user.click(screen.getByRole('button', { name: '조건을 바꿔 다시 비교' }))
    const assumptions = await screen.findByRole('heading', { name: '적용된 가정' })
    await waitFor(() => expect(within(assumptions.parentElement!).getByText('56세')).toBeInTheDocument())
  })
})
