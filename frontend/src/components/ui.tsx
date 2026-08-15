import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'
import Bell from 'lucide-react/dist/esm/icons/bell.mjs'
import Calculator from 'lucide-react/dist/esm/icons/calculator.mjs'
import CircleHelp from 'lucide-react/dist/esm/icons/circle-help.mjs'
import History from 'lucide-react/dist/esm/icons/history.mjs'
import Home from 'lucide-react/dist/esm/icons/home.mjs'
import Menu from 'lucide-react/dist/esm/icons/menu.mjs'
import MessageCircle from 'lucide-react/dist/esm/icons/message-circle.mjs'
import Scale from 'lucide-react/dist/esm/icons/scale.mjs'
import Settings from 'lucide-react/dist/esm/icons/settings.mjs'
import UserRound from 'lucide-react/dist/esm/icons/user-round.mjs'
import type { ResponseMode } from '../types/api'

export type AppPage = 'home' | ResponseMode | 'calculator' | 'history' | 'settings' | 'help'

export function LandingGearLogo({ compact = false }: { compact?: boolean }) {
  return <img className={compact ? 'logo logo--compact' : 'logo'} src={compact ? '/assets/brand/landing-gear-mark.svg' : '/assets/brand/landing-gear-logo.svg'} alt="Landing Gear" />
}

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} {...props} />
}

export function Card({ className = '', children }: { className?: string; children: ReactNode }) {
  return <section className={`card ${className}`}>{children}</section>
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />
}

export function StatusBadge({ children, tone = 'gold' }: { children: ReactNode; tone?: 'gold' | 'navy' | 'amber' }) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>
}

export function EvidenceCard({ title = '근거와 출처', children }: { title?: string; children: ReactNode }) {
  return <details className="evidence-card"><summary>{title}</summary><div>{children}</div></details>
}

export function EmptyState() {
  return <div className="empty-state"><span aria-hidden="true">✦</span><p>질문을 입력하면 답변이 이곳에 표시됩니다.</p></div>
}

export function LoadingState({ onCancel }: { onCancel: () => void }) {
  return <div className="state-panel loading-state" aria-live="polite" aria-busy="true"><div className="skeleton-stack" aria-hidden="true"><i /><i /><i /></div><div><strong>질문을 살펴보고 있습니다.</strong><p>필요한 조건과 근거를 확인하고 있어요.</p><button className="text-button" onClick={onCancel}>요청 취소</button></div></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state-panel state-panel--amber" role="alert"><span className="state-symbol" aria-hidden="true">!</span><div><strong>요청을 완료하지 못했습니다.</strong><p>{message}</p>{onRetry && <button className="secondary-button" onClick={onRetry}>다시 시도</button>}</div></div>
}

const menu = [
  { id: 'home', label: '홈', icon: Home },
  { id: 'pension-chat', label: '연금 상담', icon: MessageCircle },
  { id: 'withdrawal-decision', label: '인출 의사결정', icon: Scale },
  { id: 'calculator', label: '계산·시뮬레이션', icon: Calculator },
  { id: 'history', label: '내 기록', icon: History },
] as const

export function Sidebar({ current, onNavigate, open, onClose }: { current: AppPage; onNavigate: (page: AppPage) => void; open: boolean; onClose: () => void }) {
  return <>
    <button className={`sidebar-scrim ${open ? 'is-open' : ''}`} onClick={onClose} aria-label="메뉴 닫기" tabIndex={open ? 0 : -1} />
    <aside className={`sidebar ${open ? 'is-open' : ''}`} aria-label="주 메뉴">
      <button className="sidebar-brand" onClick={() => onNavigate('home')}><LandingGearLogo /></button>
      <nav aria-label="주 메뉴">
        {menu.map((item) => {
          const active = current === item.id; const Icon = item.icon
          return <button key={item.id} className={active ? 'active' : ''} onClick={() => { onNavigate(item.id); onClose() }} aria-current={active ? 'page' : undefined}><Icon aria-hidden="true" />{item.label}</button>
        })}
      </nav>
      <nav className="sidebar-bottom" aria-label="지원 메뉴"><button className={current === 'settings' ? 'active' : ''} onClick={() => onNavigate('settings')}><Settings aria-hidden="true" />설정</button><button className={current === 'help' ? 'active' : ''} onClick={() => onNavigate('help')}><CircleHelp aria-hidden="true" />도움말</button></nav>
    </aside>
  </>
}

export function Header({ onMenu }: { onMenu: () => void }) {
  return <header className="top-header"><button className="menu-button" onClick={onMenu} aria-label="메뉴 열기"><Menu /></button><span>안녕하세요</span><div className="header-actions"><button aria-label="알림"><Bell /></button><span className="header-divider" /><button aria-label="프로필" className="profile-icon"><UserRound /></button></div></header>
}

export function AppShell({ current, onNavigate, menuOpen, onMenuOpen, onMenuClose, children }: { current: AppPage; onNavigate: (page: AppPage) => void; menuOpen: boolean; onMenuOpen: () => void; onMenuClose: () => void; children: ReactNode }) {
  return <div className="app-shell"><Sidebar current={current} onNavigate={onNavigate} open={menuOpen} onClose={onMenuClose} /><div className="app-frame"><Header onMenu={onMenuOpen} />{children}</div></div>
}
