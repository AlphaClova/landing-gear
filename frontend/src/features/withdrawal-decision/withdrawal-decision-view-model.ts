/**
 * Withdrawal decision screen contract.
 *
 * This view model is intentionally isolated from the public ChatResponse
 * transport contract. API adapters may map /v1/chat or Rule Engine output into
 * this shape, but the frontend must not calculate or infer financial values.
 */
export type WithdrawalDecisionStatus =
  | 'complete'
  | 'needs_input'
  | 'limited'
  | 'error'

export type CalculationBasis =
  | 'exact'
  | 'scenario'
  | 'conditional'
  | 'unavailable'

export interface MoneyValue {
  amount: number | null
  currency: 'KRW'
  basis: CalculationBasis
  label: string
  description?: string
}

export interface WithdrawalDecisionInput {
  retirementBenefitAmount: number | null
  expectedTaxWon: number | null
  currentAge: number | null
  pensionStartAge: number | null
  desiredMonthlyIncome: number | null
  expectedReturnRate: number | null
  otherPensionIncome: number | null
  otherFinancialIncome: number | null
  healthInsuranceStatus:
    | 'employee'
    | 'regional'
    | 'dependent'
    | 'unknown'
}

export type WithdrawalOptionId =
  | 'lump_sum'
  | 'pension_10y'
  | 'pension_21y_plus'

export type ConditionalImpactStatus =
  | 'none'
  | 'possible'
  | 'confirmed'
  | 'unavailable'

export interface ConditionalImpact {
  basis: CalculationBasis
  status: ConditionalImpactStatus
  amount: number | null
  description: string
}

export interface WithdrawalOptionResult {
  id: WithdrawalOptionId
  label: string
  periodLabel: string

  confirmedAfterTaxAmount: MoneyValue
  estimatedTotalCashflow: MoneyValue
  estimatedMonthlyCashflow: MoneyValue

  retirementIncomeTax: MoneyValue
  pensionTaxEffect: MoneyValue
  taxSavingFromLumpSum?: MoneyValue
  applicableRate?: number

  healthInsuranceImpact: ConditionalImpact
  financialIncomeTaxImpact: ConditionalImpact

  differenceFromBaseline: MoneyValue | null
  reasons: string[]
  cautions: string[]
  evidenceIds: string[]
  toolResultId?: string
  formula?: string
  ruleId?: string
  ruleVersion?: string
}

export interface WithdrawalAssumption {
  id: string
  label: string
  value: string
  source: 'user' | 'rule' | 'scenario'
  editable: boolean
}

export interface WithdrawalEvidence {
  id: string
  organization?: string
  title: string
  location: string
  url?: string
  summary: string
  validFrom?: string | null
  validTo?: string | null
  claimIds: string[]
  documentId?: string
  chunkId?: string
  page?: number | null
}

export interface WithdrawalDecisionViewModel {
  status: WithdrawalDecisionStatus
  scenarioTitle: string

  input: WithdrawalDecisionInput
  missingFields: Array<keyof WithdrawalDecisionInput>

  summary: string
  limitations: string[]

  options: WithdrawalOptionResult[]
  assumptions: WithdrawalAssumption[]
  evidence: WithdrawalEvidence[]

  baselineOptionId: WithdrawalOptionId | null
  highlightedOptionId: WithdrawalOptionId | null
  highlightReason: string | null

  canCompare: boolean
  canRetry: boolean

  /** Safe-to-display transport diagnostic code (e.g. "WD-TIMEOUT"), set only
   *  when status is 'error'. Full detail (URL, HTTP status, raw error) goes
   *  to the developer console via chat-diagnostics.ts, never to this field. */
  diagnosticCode?: string | null
}
