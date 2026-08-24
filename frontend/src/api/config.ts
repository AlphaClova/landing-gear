export interface ApiClientConfig {
  useMockApi: boolean
  baseUrl: string
  timeoutMs: number
}

const DEFAULT_TIMEOUT_MS = 10_000

const parseTimeout = (value: string | undefined) => {
  if (!value) return DEFAULT_TIMEOUT_MS
  const timeout = Number(value)
  return Number.isFinite(timeout) && timeout > 0 ? timeout : DEFAULT_TIMEOUT_MS
}

export const apiClientConfig: ApiClientConfig = {
  useMockApi: import.meta.env.VITE_USE_MOCK_API !== 'false',
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api',
  timeoutMs: parseTimeout(import.meta.env.VITE_API_TIMEOUT_MS),
}

export const isMockApiEnabled = apiClientConfig.useMockApi
