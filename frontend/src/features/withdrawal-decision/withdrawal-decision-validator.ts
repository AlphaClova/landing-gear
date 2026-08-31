import type { MoneyValue, WithdrawalDecisionViewModel, WithdrawalOptionResult } from './withdrawal-decision-view-model'

const bases = new Set(['exact', 'scenario', 'conditional', 'unavailable'])
const statuses = new Set(['complete', 'needs_input', 'limited', 'error'])
const optionIds = new Set(['lump_sum', 'pension_10y', 'pension_21y_plus'])

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isMoneyValue = (value: unknown): value is MoneyValue => isRecord(value)
  && Object.hasOwn(value, 'amount')
  && (value.amount === null || typeof value.amount === 'number')
  && value.currency === 'KRW'
  && bases.has(String(value.basis))
  && typeof value.label === 'string'

const isOption = (value: unknown): value is WithdrawalOptionResult => isRecord(value)
  && optionIds.has(String(value.id))
  && typeof value.label === 'string'
  && typeof value.periodLabel === 'string'
  && isMoneyValue(value.confirmedAfterTaxAmount)
  && isMoneyValue(value.estimatedTotalCashflow)
  && isMoneyValue(value.estimatedMonthlyCashflow)
  && isMoneyValue(value.retirementIncomeTax)
  && isMoneyValue(value.pensionTaxEffect)
  && (!Object.hasOwn(value, 'taxSavingFromLumpSum') || isMoneyValue(value.taxSavingFromLumpSum))
  && (!Object.hasOwn(value, 'applicableRate')
    || (typeof value.applicableRate === 'number' && value.applicableRate >= 0 && value.applicableRate <= 1))
  && (value.differenceFromBaseline === null || isMoneyValue(value.differenceFromBaseline))
  && (!Object.hasOwn(value, 'formula') || typeof value.formula === 'string')
  && (!Object.hasOwn(value, 'ruleId') || typeof value.ruleId === 'string')
  && (!Object.hasOwn(value, 'ruleVersion') || typeof value.ruleVersion === 'string')
  && Array.isArray(value.evidenceIds)
  && value.evidenceIds.every((id) => typeof id === 'string')

export function validateWithdrawalDecisionViewModel(value: unknown): WithdrawalDecisionViewModel {
  if (!isRecord(value)
    || !statuses.has(String(value.status))
    || typeof value.scenarioTitle !== 'string'
    || !isRecord(value.input)
    || !Array.isArray(value.missingFields)
    || typeof value.summary !== 'string'
    || !Array.isArray(value.limitations)
    || !Array.isArray(value.options)
    || !value.options.every(isOption)
    || !Array.isArray(value.assumptions)
    || !Array.isArray(value.evidence)) {
    throw new TypeError('Withdrawal decision response did not match the required view model')
  }

  const evidenceIds = new Set(value.evidence
    .filter(isRecord)
    .map((evidence) => evidence.id)
    .filter((id): id is string => typeof id === 'string'))
  const hasUnknownEvidence = value.options.some((option) =>
    (option as WithdrawalOptionResult).evidenceIds.some((id) => !evidenceIds.has(id)))
  if (hasUnknownEvidence) throw new TypeError('Withdrawal decision response referenced unknown evidence')

  return value as unknown as WithdrawalDecisionViewModel
}
