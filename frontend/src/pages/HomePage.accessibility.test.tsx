import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { HomePage } from './HomePage'

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
    const pensionHeading = screen.getByRole('heading', { level: 1, name: '연금 상담' })
    await waitFor(() => expect(pensionHeading).toHaveFocus())
  })
})
