import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WithdrawalDecision } from './WithdrawalDecision'

async function loadExample(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: '예시 조건 불러오기' }))
  expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveValue(300000000)
  expect(screen.getByLabelText(/감면 전 기준 퇴직소득세/)).toHaveValue(24000000)
  expect(screen.getByLabelText(/현재 나이/)).toHaveValue(55)
  expect(screen.getByLabelText(/연금 수령 시작 나이/)).toHaveValue(60)
  expect(screen.getByLabelText(/예상수익률/)).toHaveValue(2)
}

describe('인출 의사결정 회귀', () => {
  it('감면 전 기준 퇴직소득세를 접근 가능한 필수 입력으로 표시한다', () => {
    render(<WithdrawalDecision />)
    const input = screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' })
    expect(input).toBeRequired()
    expect(input).toHaveAttribute('aria-required', 'true')
    expect(input).toHaveAccessibleDescription('일시금 수령 시 기준이 되는 퇴직소득세를 입력해 주세요.')
  })

  it('짧은 행동 제목과 하나의 h1을 사용한다', () => {
    render(<WithdrawalDecision />)
    expect(screen.getByText('인출 의사결정')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: '수령 방식을 비교해 보세요' })).toBeInTheDocument()
    expect(screen.queryByText('수령 방식의 차이를 같은 기준으로 비교해 보세요.')).not.toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('필수 입력 누락 시 needs_input 요약과 누락 필드를 표시한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    expect(await screen.findByText('수령 방식의 일반적인 차이는 안내할 수 있지만 금액 비교를 위해 추가 조건이 필요합니다.')).toBeInTheDocument()
    expect(screen.getByText(/퇴직급여 예상액, 감면 전 기준 퇴직소득세, 현재 나이, 연금 수령 시작 나이/)).toBeInTheDocument()
    expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveAttribute('aria-describedby', 'retirement-benefit-help')
    expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveAccessibleDescription(/필수 입력입니다.*원 단위/)
    await waitFor(() => expect(screen.getByLabelText(/퇴직급여 예상액/)).toHaveFocus())
  })

  it.each(['-1', '1.5', String(Number.MAX_SAFE_INTEGER + 1)])('기준세액 %s원을 거부한다', async (value) => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const tax = screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' })
    await user.clear(tax); await user.type(tax, value)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    await waitFor(() => expect(tax).toHaveAttribute('aria-invalid', 'true'))
    expect(tax).toHaveAccessibleDescription('0원 이상의 정수 금액을 원 단위로 입력해 주세요.')
  })

  it('숫자가 아닌 기준세액 입력을 미입력으로 처리한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const tax = screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' })
    fireEvent.change(tax, { target: { value: 'not-a-number' } })
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    await waitFor(() => expect(tax).toHaveAttribute('aria-invalid', 'true'))
    expect(tax).toHaveValue(null)
  })

  it.each(['0', '24000000'])('정수 기준세액 %s원을 허용한다', async (value) => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const tax = screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' })
    await user.clear(tax); await user.type(tax, value)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    await waitFor(() => expect(tax).toHaveAttribute('aria-invalid', 'false'))
    expect(tax).toHaveValue(Number(value))
  })

  it('요청 취소 후에도 기준세액 입력을 유지한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const tax = screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' })
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    await user.click(screen.getByRole('button', { name: '요청 취소' }))
    expect(await screen.findByText('요청을 취소했습니다. 입력한 조건은 유지됩니다.')).toBeInTheDocument()
    expect(tax).toHaveValue(24000000)
  })

  it('예시 조건에서 중복 unavailable 값과 조건부 영향을 정리한다', async () => {
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
    expect(screen.queryByText('확정 세후금액')).not.toBeInTheDocument()
    expect(screen.queryByText('예상 총 현금흐름')).not.toBeInTheDocument()
    expect(screen.queryByText('예상 월 현금흐름')).not.toBeInTheDocument()
    expect(screen.queryByText('계산할 수 없음')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '가정 기반 예상 현금흐름' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '추가 확인 사항' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '건강보험료' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '금융소득 과세' })).toBeInTheDocument()
    expect(screen.getAllByText('현재 계산에는 건강보험료 영향이 포함되지 않았습니다.')).toHaveLength(1)
    expect(screen.getAllByText('현재 계산에는 금융소득 과세 영향이 포함되지 않았습니다.')).toHaveLength(1)
    expect(screen.queryByRole('heading', { name: '확인할 조건' })).not.toBeInTheDocument()
    expect(screen.queryByText(/추천|우위|가장 유리/)).not.toBeInTheDocument()
  })

  it('B transport fixture의 계산값과 근거를 Adapter를 거쳐 표시한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    await screen.findByRole('heading', { name: '수령 방식별 차이를 확인하세요' })

    const exactTable = screen.getByRole('region', { name: '확정 계산 비교표, 좌우로 스크롤 가능' })
    expect(within(exactTable).getByText('24,000,000원')).toBeInTheDocument()
    expect(within(exactTable).getByText('16,800,000원')).toBeInTheDocument()
    expect(within(exactTable).getByText('12,000,000원')).toBeInTheDocument()
    expect(within(exactTable).getByText('100%')).toBeInTheDocument()
    expect(within(exactTable).getByText('70%')).toBeInTheDocument()
    expect(within(exactTable).getByText('50%')).toBeInTheDocument()
    expect(within(exactTable).getByText('기준 (0원)')).toBeInTheDocument()
    expect(within(exactTable).getByText('7,200,000원 절감')).toBeInTheDocument()
    expect(within(exactTable).getByText('12,000,000원 절감')).toBeInTheDocument()
    expect(within(exactTable).getAllByText('확정 계산')).toHaveLength(3)

    expect(screen.getByText('24,000,000원 × 100% = 24,000,000원')).toBeInTheDocument()
    expect(screen.getByText('24,000,000원 × 70% = 16,800,000원')).toBeInTheDocument()
    expect(screen.getByText('24,000,000원 × 50% = 12,000,000원')).toBeInTheDocument()
    expect(screen.getAllByText('RETIRE_TAX_RATE_BY_YEAR · v1.0.0')).toHaveLength(3)
    expect(screen.getByText('일시금으로 받으면 퇴직소득세를 100% 즉시 납부한다.')).toBeInTheDocument()
    expect(screen.getByText('수령 기간에 따라 퇴직소득세의 일부만 납부한다.')).toBeInTheDocument()
    expect(screen.getByText(/p\.1/)).toBeInTheDocument()
    expect(screen.queryByText(/p\.null|null/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '원문 보기' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '적용된 가정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '주의사항' })).not.toBeInTheDocument()
    expect(screen.queryByText('계산할 수 없음')).not.toBeInTheDocument()
  })

  it('예상수익률 -1은 limited 상태로 확정값만 유지한다', async () => {
    const user = userEvent.setup()
    render(<WithdrawalDecision />)
    await loadExample(user)
    const rate = screen.getByLabelText(/예상수익률/)
    await user.clear(rate); await user.type(rate, '-1')
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
    expect(await screen.findByText('확정 조건의 비교는 가능하지만 예상 현금흐름은 현재 가정으로 계산할 수 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '가정 기반 예상 현금흐름' })).not.toBeInTheDocument()
    expect(screen.queryByText('계산할 수 없음')).not.toBeInTheDocument()
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
    expect(screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' })).toHaveValue(24000000)
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
    await screen.findByRole('button', { name: '조건을 바꿔 다시 비교' })
    expect(age).toHaveValue(56)
    expect(screen.getByRole('region', { name: '확정 계산 비교표, 좌우로 스크롤 가능' })).toBeInTheDocument()
  })
})

describe('인출 의사결정 HTTP 모드 (실제 클릭 흐름)', () => {
  const originalFetch = globalThis.fetch

  const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'x-request-id': 'req-http-1' },
  })

  const withdrawalChatResponse = () => ({
    type: 'result', message: 'ok', request_id: 'req-http-1', required_slots: [], comparison: null,
    citations: [],
    withdrawal_result: {
      comparison: {
        result_type: 'exact', unit: 'KRW',
        scenarios: [
          { scenario: 'lump_sum', tax_value: 5_000_000, applicable_rate: 1, difference_vs_lump_sum: 0, formula: '5000000 * 1.00', rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0', evidence_ids: ['e1'], assumptions: [], warnings: [] },
          { scenario: 'annuity_10_years', tax_value: 3_500_000, applicable_rate: 0.7, difference_vs_lump_sum: 1_500_000, formula: '5000000 * 0.70', rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0', evidence_ids: ['e1'], assumptions: [], warnings: [] },
          { scenario: 'annuity_21_plus_years', tax_value: 2_500_000, applicable_rate: 0.5, difference_vs_lump_sum: 2_500_000, formula: '5000000 * 0.50', rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0', evidence_ids: ['e1'], assumptions: [], warnings: [] },
        ],
      },
      evidence: [{ evidence_id: 'e1', chunk_id: 'c1', document_id: 'doc-1', page: 1, section: '근거', quote: '설명', source_priority: 0, score: 1 }],
      applied_rules: [{ rule_id: 'RETIRE_TAX_RATE_BY_YEAR', rule_version: '1.0.0' }],
      claim_validation: { validations: [{ claim_id: 'c1', supported: true, reasons: [] }], unsupported_claim_count: 0, validated_claim_count: 1, unsupported_claim_rate: 0 },
    },
  })

  async function fillReportedInputAndSubmit(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText(/퇴직급여 예상액/), '100000000')
    await user.type(screen.getByRole('spinbutton', { name: '감면 전 기준 퇴직소득세' }), '5000000')
    await user.type(screen.getByLabelText(/현재 나이/), '55')
    await user.type(screen.getByLabelText(/연금 수령 시작 나이/), '65')
    await user.selectOptions(screen.getByLabelText(/건강보험 자격/), '잘 모르겠어요')
    await user.click(screen.getByRole('button', { name: '수령 방식 비교하기' }))
  }

  beforeEach(() => {
    vi.stubEnv('VITE_CHAT_API_MODE', 'http')
    vi.stubEnv('VITE_API_BASE_URL', 'https://landing-gear.onrender.com')
    vi.resetModules()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.unstubAllEnvs()
    sessionStorage.clear()
  })

  it('실제 DOM 입력과 클릭만으로 POST /v1/chat 1회 후 withdrawal_result를 렌더링한다', async () => {
    const fetchMock = vi.fn<typeof fetch>(() => Promise.resolve(jsonResponse(withdrawalChatResponse())))
    globalThis.fetch = fetchMock

    const { WithdrawalDecision: HttpWithdrawalDecision } = await import('./WithdrawalDecision')
    const user = userEvent.setup()
    render(<HttpWithdrawalDecision />)

    await fillReportedInputAndSubmit(user)

    expect(await screen.findByRole('heading', { name: '수령 방식별 차이를 확인하세요' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://landing-gear.onrender.com/v1/chat')
    expect(JSON.parse((init as RequestInit).body as string).profile.extra).toEqual({ pension_start_age: 65 })
  })

  // A 'network'-classified failure now also triggers a GET .../health reachability
  // probe (see chat-diagnostics.ts) to disambiguate CORS from a genuine outage.
  // These tests discriminate the mock by URL so the probe never consumes a
  // queued POST /v1/chat response, and count/index only the POST calls.
  const isHealthProbe = (url: unknown) => typeof url === 'string' && url.endsWith('/health')
  const postCalls = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls.filter(([url]) => !isHealthProbe(url))

  it('일시적인 네트워크 실패는 자동 재시도 1회로 사용자 개입 없이 복구된다', async () => {
    let postAttempts = 0
    const fetchMock = vi.fn<typeof fetch>((url) => {
      if (isHealthProbe(url)) return Promise.resolve(new Response(null, { status: 200 }))
      postAttempts += 1
      return postAttempts === 1
        ? Promise.reject(new TypeError('Failed to fetch'))
        : Promise.resolve(jsonResponse(withdrawalChatResponse()))
    })
    globalThis.fetch = fetchMock

    const { WithdrawalDecision: HttpWithdrawalDecision } = await import('./WithdrawalDecision')
    const user = userEvent.setup()
    render(<HttpWithdrawalDecision />)

    await fillReportedInputAndSubmit(user)

    expect(await screen.findByRole('heading', { name: '수령 방식별 차이를 확인하세요' }, { timeout: 5000 })).toBeInTheDocument()
    expect(postCalls(fetchMock)).toHaveLength(2)
  })

  it('두 번 연속 실패해도 오류 화면이 새 비교와 다시 시도를 막지 않고, 다시 시도는 동일 입력으로 재요청한다', async () => {
    let postAttempts = 0
    const fetchMock = vi.fn<typeof fetch>((url) => {
      if (isHealthProbe(url)) return Promise.resolve(new Response(null, { status: 200 }))
      postAttempts += 1
      return postAttempts <= 2
        ? Promise.reject(new TypeError('Failed to fetch'))
        : Promise.resolve(jsonResponse(withdrawalChatResponse()))
    })
    globalThis.fetch = fetchMock

    const { WithdrawalDecision: HttpWithdrawalDecision } = await import('./WithdrawalDecision')
    const user = userEvent.setup()
    render(<HttpWithdrawalDecision />)

    await fillReportedInputAndSubmit(user)

    const alert = await screen.findByRole('alert', {}, { timeout: 5000 })
    expect(alert).toBeInTheDocument()
    expect(postCalls(fetchMock)).toHaveLength(2) // original attempt + one automatic retry, both failed
    expect(screen.getByText(/오류 코드: WD-/)).toBeInTheDocument()

    // The input form must still be open and the primary submit button must still work.
    expect(screen.getByRole('button', { name: '수령 방식 비교하기' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    expect(await screen.findByRole('heading', { name: '수령 방식별 차이를 확인하세요' }, { timeout: 5000 })).toBeInTheDocument()
    const posts = postCalls(fetchMock)
    expect(posts).toHaveLength(3)
    const thirdCallBody = JSON.parse((posts[2][1] as RequestInit).body as string)
    expect(thirdCallBody.profile).toEqual({
      age: 55, retirement_amount_won: 100000000, expected_tax_won: 5000000, extra: { pension_start_age: 65 },
    })
  })
})
