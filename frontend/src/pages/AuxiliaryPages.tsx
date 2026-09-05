import BookOpen from 'lucide-react/dist/esm/icons/book-open.mjs'
import CircleHelp from 'lucide-react/dist/esm/icons/circle-help.mjs'
import Clock3 from 'lucide-react/dist/esm/icons/clock-3.mjs'
import FileText from 'lucide-react/dist/esm/icons/file-text.mjs'
import Settings from 'lucide-react/dist/esm/icons/settings.mjs'
import { Card, PageHeader, StatusBadge } from '../components/ui'
import type { AppPage } from '../components/ui'

const content = {
  settings: { icon: Settings, eyebrow: '설정', title: '서비스 이용 환경을 관리합니다.', description: '알림과 표시 방식을 설정할 수 있는 기본 화면입니다.' },
  help: { icon: CircleHelp, eyebrow: '도움말', title: 'Landing Gear 이용 안내', description: '질문 작성 방법과 답변을 확인하는 순서를 안내합니다.' },
} as const

export function AuxiliaryPage({ page }: { page: Exclude<AppPage, 'home' | 'pension-chat' | 'withdrawal-decision'> }) {
  if (page === 'history') return <section className="standard-page"><PageHeader label="내 기록" title="지난 상담을 다시 확인하세요." description="저장된 상담과 비교 기록이 이곳에 표시됩니다." /><Card className="history-empty"><Clock3 aria-hidden="true" /><h2>아직 저장된 기록이 없습니다.</h2><p>상담을 완료한 뒤 저장 기능이 연결되면 기록을 확인할 수 있습니다.</p></Card></section>
  const item = content[page]; const Icon = item.icon
  return <section className="standard-page"><PageHeader label={item.eyebrow} title={item.title} description={item.description} /><div className="support-grid"><Card><Icon aria-hidden="true" /><h2>{page === 'settings' ? '기본 설정' : '질문 작성 방법'}</h2><p>{page === 'settings' ? '사용자 정보 없이 서비스의 표시 및 알림 환경만 다룹니다.' : '상황과 궁금한 점을 자연스럽게 입력하면 필요한 조건을 먼저 확인합니다.'}</p></Card><Card><BookOpen aria-hidden="true" /><h2>{page === 'help' ? '답변 확인 순서' : '준비 상태'}</h2><p>{page === 'help' ? '핵심 결론, 확정 정보, 조건부 정보, 근거와 주의사항 순서로 확인하세요.' : '백엔드 계약이 연결되기 전에는 값을 임의로 생성하지 않습니다.'}</p><StatusBadge tone="gold">연결 준비 중</StatusBadge></Card></div>{page === 'help' && <Card className="help-note"><FileText aria-hidden="true" /><div><h2>답변의 근거</h2><p>출처가 제공된 답변은 별도의 근거 영역에서 문서와 해당 위치를 확인할 수 있습니다.</p></div></Card>}</section>
}
