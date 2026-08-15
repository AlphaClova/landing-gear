import type { PensionApiClient } from './client'
import { HttpPensionApiClient } from './http-client'
import { MockPensionApiClient } from './mock-client'

const useMock = import.meta.env.VITE_USE_MOCK_API !== 'false'

export const pensionApi: PensionApiClient = useMock
  ? new MockPensionApiClient()
  : new HttpPensionApiClient(import.meta.env.VITE_API_BASE_URL ?? '/api')

export type { PensionApiClient } from './client'

