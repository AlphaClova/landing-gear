import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { HomePage } from './HomePage'
import { Header } from '../components/ui'
import { AuxiliaryPage } from './AuxiliaryPages'

describe('주요 화면 접근성 구조', () => {
  beforeEach(() => {
    window.location.hash = ''
  })

  it('장식 효과를 숨기고 시작 후 main, nav, h1에 접근할 수 있다', async () => {
    const user = userEvent.setup()
    render(<HomePage />)

    expect(document.querySelector('.brand-aura')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Landing Gear' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /시작하기/ }))

    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '주 메뉴' })).toBeInTheDocument()
    const heading = screen.getByRole('heading', { level: 1, name: '무엇을 도와드릴까요?' })
    await waitFor(() => expect(heading).toHaveFocus())

    const pensionMenu = screen.getByRole('button', { name: '연금 상담' })
    pensionMenu.focus()
    await user.keyboard(' ')
    const pensionHeading = screen.getByRole('heading', { level: 1, name: '연금이 궁금하신가요?' })
    await waitFor(() => expect(pensionHeading).toHaveFocus())
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('사용자 이름 유무에 따라 인사말 경계를 유지하고 헤더 버튼 이름을 제공한다', () => {
    const { rerender } = render(<Header onMenu={() => undefined} />)
    expect(screen.getByText('안녕하세요, 고객님')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '알림' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '계정' })).toBeInTheDocument()

    rerender(<Header onMenu={() => undefined} displayName="지윤" />)
    expect(screen.getByText('안녕하세요, 지윤님')).toBeInTheDocument()
  })

  it('사이드바 로고를 클릭하거나 키보드로 실행해 시작 화면으로 이동하고 다시 홈에 진입한다', async () => {
    const user = userEvent.setup()
    render(<HomePage />)
    await user.click(screen.getByRole('button', { name: /시작하기/ }))

    let brand = screen.getByRole('button', { name: 'Landing Gear 시작 화면으로 이동' })
    await user.click(brand)
    expect(screen.getByRole('heading', { level: 1, name: 'Landing Gear' })).toBeInTheDocument()
    expect(window.location.hash).toBe('')

    await user.click(screen.getByRole('button', { name: /시작하기/ }))
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: '무엇을 도와드릴까요?' })).toHaveFocus())
    brand = screen.getByRole('button', { name: 'Landing Gear 시작 화면으로 이동' })
    brand.focus()
    expect(brand).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('heading', { level: 1, name: 'Landing Gear' })).toBeInTheDocument()
    expect(window.location.hash).toBe('')

    await user.click(screen.getByRole('button', { name: /시작하기/ }))
    expect(screen.getByRole('heading', { level: 1, name: '무엇을 도와드릴까요?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '홈' })).toHaveAttribute('aria-current', 'page')
  })

  it.each([
    ['history', '내 기록', '지난 상담을 다시 확인하세요.'],
    ['settings', '설정', '서비스 이용 환경을 관리합니다.'],
    ['help', '도움말', 'Landing Gear 이용 안내'],
  ] as const)('%s 화면은 공통 라벨과 하나의 제목을 사용한다', (page, label, title) => {
    render(<AuxiliaryPage page={page} />)
    expect(screen.getByText(label)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })
})
