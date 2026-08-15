import type { ChatResponse } from '../../types/api'

export const productComparisonQuestion = '원리금보장형과 실적배당형은 어떻게 비교해야 하나요?'

export type ProductValueStatus = 'available' | 'conditional' | 'unavailable'

export interface ProductComparisonValue {
  value: string | null
  status: ProductValueStatus
  description?: string
}

export interface ProductComparisonItem {
  id: string
  name: string
  category: string
  principalProtection: ProductComparisonValue
  expectedReturn: ProductComparisonValue
  fee: ProductComparisonValue
  riskLevel: ProductComparisonValue
  liquidity: ProductComparisonValue
  investmentPeriod: ProductComparisonValue
  characteristics: string[]
  cautions: string[]
  evidenceIds: string[]
}

export interface ProductComparisonViewModel {
  type: 'product_compare'
  title: string
  summary: string
  items: ProductComparisonItem[]
  comparisonCriteria: string[]
  limitations: string[]
  evidence: Array<{ id: string; organization: string; title: string; location: string; url?: string; summary: string }>
  followUpQuestions: string[]
  isMock: boolean
}

const unavailable = { value: null, status: 'unavailable', description: '실제 상품 데이터 연결 필요' } as const

// 이 데이터는 상품 비교 UI 검증용 유형 비교 예시다. 실제 상품명, 수익률, 수수료, 위험등급은 담당 B의 상품 데이터 응답으로 교체한다.
export const productComparisonFixture: ProductComparisonViewModel = {
  type: 'product_compare',
  title: '상품 유형별 차이를 확인하세요',
  summary: '상품을 선택하기 전에 원금 보호 구조, 수익 변동 가능성, 수수료, 위험등급과 투자기간을 함께 확인해야 합니다.',
  items: [
    {
      id: 'principal-protected-type', name: '원리금보장형', category: '상품 유형',
      principalProtection: { value: '상품 조건에 따라 원금과 이자 지급 구조 확인', status: 'conditional' },
      expectedReturn: unavailable, fee: unavailable, riskLevel: unavailable,
      liquidity: { value: '중도해지 및 이전 조건 확인 필요', status: 'conditional' },
      investmentPeriod: { value: '상품별 만기 조건 확인 필요', status: 'conditional' },
      characteristics: ['정해진 금리 및 만기 구조를 확인하는 유형', '상품별 적용 금리와 중도해지 조건 확인 필요'],
      cautions: ['실제 보장 범위와 조건은 상품 설명서 확인 필요'], evidenceIds: [],
    },
    {
      id: 'performance-linked-type', name: '실적배당형', category: '상품 유형',
      principalProtection: { value: '운용 결과에 따라 원금 손실 가능', status: 'conditional' },
      expectedReturn: unavailable, fee: unavailable, riskLevel: unavailable,
      liquidity: { value: '상품별 환매 및 이전 조건 확인 필요', status: 'conditional' },
      investmentPeriod: { value: '투자 대상과 전략에 따라 확인 필요', status: 'conditional' },
      characteristics: ['운용 성과에 따라 결과가 달라지는 유형', '투자 대상과 위험 수준 확인 필요'],
      cautions: ['과거 수익률이 미래 성과를 보장하지 않음', '실제 상품의 위험등급과 설명서 확인 필요'], evidenceIds: [],
    },
  ],
  comparisonCriteria: ['원금 보호 구조', '기대수익', '수수료', '위험등급', '유동성', '투자기간'],
  limitations: ['현재는 상품 유형의 비교 구조만 확인할 수 있습니다. 실제 상품명, 수익률, 수수료와 위험등급은 상품 데이터 연결 후 제공됩니다.'],
  evidence: [],
  followUpQuestions: ['실제 상품을 비교할 때 어떤 정보를 확인해야 하나요?', '수수료와 위험등급은 어디서 확인하나요?', '투자기간에 따라 어떤 조건을 확인해야 하나요?'],
  isMock: true,
}

export function getProductComparisonViewModel(question: string, response: ChatResponse): ProductComparisonViewModel | null {
  const isMockMode = import.meta.env.VITE_USE_MOCK_API !== 'false'
  return isMockMode && response.type === 'result' && question.trim() === productComparisonQuestion ? productComparisonFixture : null
}
