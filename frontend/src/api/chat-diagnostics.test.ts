import { describe, expect, it, vi } from 'vitest'
import { probeReachability } from './chat-diagnostics'

describe('probeReachability', () => {
  it('returns reachable when the no-cors probe resolves (server responded, opaque or not)', async () => {
    // A real no-cors probe resolves as an opaque Response (status 0), which only
    // the browser can construct; a 200 stand-in is enough since probeReachability
    // only cares whether the promise resolves at all, never its status/body.
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 200 }))
    const result = await probeReachability('https://api.example.com/health', 1000, fetcher)
    expect(result).toBe('reachable')
    expect(fetcher).toHaveBeenCalledWith('https://api.example.com/health', {
      method: 'GET', mode: 'no-cors', signal: expect.any(AbortSignal),
    })
  })

  it('returns unreachable when the probe itself fails (DNS/TCP/TLS/proxy-level failure)', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'))
    const result = await probeReachability('https://api.example.com/health', 1000, fetcher)
    expect(result).toBe('unreachable')
  })

  it('returns inconclusive when the probe itself times out rather than resolving either way', async () => {
    vi.useFakeTimers()
    try {
      const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
      }))
      const resultPromise = probeReachability('https://api.example.com/health', 50, fetcher)
      await vi.advanceTimersByTimeAsync(50)
      expect(await resultPromise).toBe('inconclusive')
    } finally {
      vi.useRealTimers()
    }
  })
})
