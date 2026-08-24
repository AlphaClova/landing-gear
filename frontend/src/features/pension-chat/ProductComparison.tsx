import { StatusBadge } from '../../components/ui'
import type { ProductComparisonItem, ProductComparisonValue, ProductComparisonViewModel, ProductValueStatus } from './product-comparison-view-model'

const statusLabel: Record<ProductValueStatus, string> = { available: '확인된 정보', conditional: '조건 확인 필요', unavailable: '데이터 연결 필요' }
const rows: Array<{ label: string; key: keyof Pick<ProductComparisonItem, 'principalProtection' | 'expectedReturn' | 'fee' | 'riskLevel' | 'liquidity' | 'investmentPeriod'> }> = [
  { label: '원금 보호 구조', key: 'principalProtection' }, { label: '기대수익', key: 'expectedReturn' }, { label: '수수료', key: 'fee' }, { label: '위험등급', key: 'riskLevel' }, { label: '유동성', key: 'liquidity' }, { label: '투자기간', key: 'investmentPeriod' },
]

function ProductStatus({ value }: { value: ProductComparisonValue }) {
  return <span className={`product-status product-status--${value.status}`}>{statusLabel[value.status]}</span>
}

export function ProductComparison({ model, onQuestion }: { model: ProductComparisonViewModel; onQuestion: (question: string) => void }) {
  return <>
    <section className="product-summary"><div>{model.isMock && <StatusBadge tone="gold">유형 비교 예시</StatusBadge>}<h2>{model.title}</h2><p>{model.summary}</p></div>{model.isMock && <small>실제 상품별 정보는 상품 데이터 연결 후 표시됩니다.</small>}</section>
    <section className="product-type-section"><h2>유형 비교</h2><div className="product-type-cards">{model.items.map((item) => <article key={item.id}><header><small>{item.category}</small><h3>{item.name}</h3></header><dl><div><dt>원금 보호 구조</dt><dd><ProductStatus value={item.principalProtection} />{item.principalProtection.value}</dd></div><div><dt>기대수익</dt><dd><ProductStatus value={item.expectedReturn} />{item.expectedReturn.value ?? item.expectedReturn.description}</dd></div><div><dt>위험등급</dt><dd><ProductStatus value={item.riskLevel} />{item.riskLevel.value ?? item.riskLevel.description}</dd></div></dl><h4>주요 특징</h4><ul>{item.characteristics.map((text) => <li key={text}>{text}</li>)}</ul><div className="product-caution"><strong>주의사항</strong>{item.cautions.map((text) => <p key={text}>{text}</p>)}</div></article>)}</div></section>
    <section className="product-table-section"><h2>상품 유형 비교표</h2><p className="table-scroll-hint">표를 좌우로 스크롤해 비교할 수 있습니다.</p><div tabIndex={0} role="region" aria-label="상품 유형 비교표, 좌우로 스크롤 가능"><table><thead><tr><th scope="col">비교 항목</th>{model.items.map((item) => <th scope="col" key={item.id}>{item.name}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.key}><th scope="row">{row.label}</th>{model.items.map((item) => { const value = item[row.key]; return <td key={item.id}><ProductStatus value={value} /><span>{value.value ?? value.description ?? '데이터 연결 필요'}</span></td> })}</tr>)}</tbody></table></div></section>
    <section className="product-checks"><h2>확인해야 할 조건</h2><ul>{model.comparisonCriteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul></section>
    {model.isMock && <section className="product-data-limitation"><StatusBadge tone="amber">상품별 데이터 연결 전</StatusBadge><h2>상품별 데이터 연결 전</h2><p>{model.limitations[0]}</p></section>}
    <section className="product-evidence-empty" aria-live="polite"><h2>근거와 출처</h2><p>{model.evidence.length === 0 ? '상품 데이터와 설명서 근거가 연결되면 이곳에서 확인할 수 있습니다.' : `${model.evidence.length}개의 근거가 연결되었습니다.`}</p></section>
    <section className="pension-followups" aria-labelledby="product-followups-title"><h2 id="product-followups-title">이어진 질문</h2><div>{model.followUpQuestions.map((question) => <button type="button" key={question} onClick={() => onQuestion(question)}>{question}</button>)}</div></section>
  </>
}
