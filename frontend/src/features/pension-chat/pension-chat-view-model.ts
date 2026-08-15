import type { ChatResponse } from '../../types/api'

export const dbDcQuestion = 'DB형과 DC형의 차이는 무엇인가요?'

export const pensionSuggestions = [
  dbDcQuestion,
  '원리금보장형과 실적배당형은 어떻게 비교해야 하나요?',
  '연금저축과 IRP는 어떻게 다른가요?',
  '연금은 언제부터 받을 수 있나요?',
]

export interface PensionEvidence {
  id: string
  organization: string
  title: string
  url: string
  location: string
  excerpt: string
  supportedContent: string
  claimLabels: string[]
}

export interface PensionResultViewModel {
  sections: { title: string; content: string }[]
  caution: string
  evidence: PensionEvidence[]
  followUpQuestions: string[]
}

const dbDcResult: PensionResultViewModel = {
  sections: [
    {
      title: 'DB형',
      content: 'DB형은 퇴직 시 받을 급여 수준이 사전에 정해지는 구조입니다. 회사가 부담금을 적립하고 운용 책임을 집니다. 근로자가 받을 급여는 회사의 적립금 운용성과와 직접 연동되지 않습니다.',
    },
    {
      title: 'DC형',
      content: 'DC형은 회사가 납입해야 할 부담금 수준이 사전에 정해지는 구조입니다. 근로자가 자신의 적립금을 직접 운용하며, 적립금과 운용수익을 퇴직급여로 받습니다.',
    },
  ],
  caution: '어떤 유형이 적합한지는 회사의 제도, 임금 변화, 운용 가능 여부와 위험 감수 성향 등에 따라 달라질 수 있습니다.',
  evidence: [
    {
      id: 'moel-retirement-pension',
      organization: '고용노동부',
      title: '퇴직연금이란?',
      url: 'https://www.moel.go.kr/retirementpay.do',
      location: '확정급여형 퇴직연금제도 및 확정기여형 퇴직연금제도 안내',
      excerpt: 'DB형은 받을 퇴직급여가 사전에 확정되고, DC형은 회사가 납입할 부담금이 사전에 확정됩니다.',
      supportedContent: 'DB형의 급여 확정 및 회사 운용, DC형의 부담금 확정 및 근로자 운용 구조',
      claimLabels: ['DB형 급여 수준', 'DB형 운용 주체', 'DC형 부담금 수준', 'DC형 운용 주체', 'DC형 운용 결과'],
    },
    {
      id: 'law-retirement-benefit',
      organization: '국가법령정보센터',
      title: '근로자퇴직급여 보장법',
      url: 'https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=0&lsId=009883',
      location: '제2조 정의, 제20조 제1항',
      excerpt: '확정기여형 사용자는 가입자의 연간 임금총액의 12분의 1 이상을 부담금으로 납입해야 합니다.',
      supportedContent: 'DB형·DC형의 법적 정의와 DC형 회사 부담금의 최소 기준',
      claimLabels: ['DB형 급여 수준', 'DC형 부담금 수준', 'DC형 최소 부담금'],
    },
  ],
  followUpQuestions: [
    '현재 가입한 퇴직연금 유형은 어디서 확인하나요?',
    '임금이 계속 오르면 DB형과 DC형에 어떤 차이가 생기나요?',
    'DC형에서는 운용 상품을 어떻게 선택하나요?',
  ],
}

export function getPensionResultViewModel(question: string, response: ChatResponse): PensionResultViewModel | null {
  return response.type === 'result' && question.trim() === dbDcQuestion ? dbDcResult : null
}
