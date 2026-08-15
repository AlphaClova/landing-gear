import type { PensionApiClient } from './client'
import { HttpPensionApiClient } from './http-client'
import { MockPensionApiClient } from './mock-client'
import { apiClientConfig } from './config'

export function createPensionApiClient(config = apiClientConfig): PensionApiClient {
  return config.useMockApi
    ? new MockPensionApiClient()
    : new HttpPensionApiClient(config.baseUrl, config.timeoutMs)
}

export const pensionApi: PensionApiClient = createPensionApiClient()

export type { PensionApiClient } from './client'
export { isMockApiEnabled } from './config'
