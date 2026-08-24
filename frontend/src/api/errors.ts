export class ApiHttpError extends Error {
  constructor(public readonly status: number) {
    super(`API request failed (${status})`)
    this.name = 'ApiHttpError'
  }
}

export class ApiNetworkError extends Error {
  constructor(options?: ErrorOptions) {
    super('API network request failed', options)
    this.name = 'ApiNetworkError'
  }
}

export class ApiTimeoutError extends Error {
  constructor() {
    super('API request timed out')
    this.name = 'ApiTimeoutError'
  }
}

export class ApiResponseError extends Error {
  constructor(message = 'API response did not match the required contract') {
    super(message)
    this.name = 'ApiResponseError'
  }
}
