/**
 * Diagnostics for the withdrawal-decision /v1/chat transport.
 *
 * Scope: chat-client.ts (HttpChatApiClient) only — pension-chat's /answer
 * contract (public-answer-client.ts) is untouched and unaffected.
 *
 * Everything here is console-only (never rendered). The screen only ever
 * shows a short WithdrawalDiagnosticCode (see chat-client.ts), which carries
 * no URL, header, or internal-message content and is safe to display.
 */

export type WithdrawalDiagnosticCode =
  | 'WD-ABORTED'
  | 'WD-TIMEOUT'
  | 'WD-CORS'
  | 'WD-NETWORK'
  | 'WD-NETWORK-UNKNOWN'
  | 'WD-HTTP-4XX'
  | 'WD-HTTP-5XX'
  | 'WD-PROTOCOL'
  | 'WD-UNKNOWN'

export type ChatRequestStage =
  | 'request-sent'
  | 'response-received'
  | 'body-read'
  | 'response-validated'
  | 'http-error-mapped'

export interface ChatStageLogEntry {
  stage: ChatRequestStage
  url: string
  method: string
  elapsedMs: number
  status?: number | null
  contentType?: string | null
  requestId?: string | null
  detail?: string
}

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())
export const elapsedSince = (startedAt: number) => Math.round(now() - startedAt)
export const stageClock = now

export function logChatStage(entry: ChatStageLogEntry): void {
  console.info(
    `[withdrawal-chat] ${entry.stage} — ${entry.method} ${entry.url} (+${entry.elapsedMs}ms)`,
    {
      status: entry.status ?? null,
      contentType: entry.contentType ?? null,
      requestId: entry.requestId ?? null,
      detail: entry.detail,
    },
  )
}

export interface ChatFailureLogEntry {
  code: WithdrawalDiagnosticCode
  kind: string
  url: string
  method: string
  elapsedMs: number
  status: number | null
  requestId: string | null
  rawErrorName: string | null
  rawErrorMessage: string | null
  reachabilityProbe?: 'reachable' | 'unreachable' | 'inconclusive' | 'not-run'
}

export function logChatFailure(entry: ChatFailureLogEntry): void {
  console.error(
    `[withdrawal-chat] request failed — code=${entry.code} kind=${entry.kind} ` +
    `status=${entry.status ?? 'n/a'} elapsed=${entry.elapsedMs}ms`,
    {
      url: entry.url,
      method: entry.method,
      requestId: entry.requestId,
      rawErrorName: entry.rawErrorName,
      rawErrorMessage: entry.rawErrorMessage,
      reachabilityProbe: entry.reachabilityProbe ?? 'not-run',
    },
  )
}

/**
 * `fetch()` surfaces a CORS rejection and a genuine network failure (DNS,
 * TCP/TLS, proxy/firewall block) as the exact same `TypeError: Failed to
 * fetch`, with no further detail exposed to page JS — this is a deliberate
 * browser security boundary, not a gap in this client's error handling, and
 * it cannot be told apart by inspecting the error alone.
 *
 * A `no-cors` probe to the same origin sidesteps that: `no-cors` mode skips
 * the CORS access-control check entirely, so the probe request succeeds
 * (as an opaque response) whenever the server is actually reachable over the
 * network, and only rejects when the network path itself is broken. Diffing
 * the real request's outcome against this probe turns an ambiguous "failed
 * to fetch" into a confirmed CORS-vs-network classification.
 */
export async function probeReachability(
  healthUrl: string,
  probeTimeoutMs: number,
  fetcher: typeof fetch,
): Promise<'reachable' | 'unreachable' | 'inconclusive'> {
  const controller = new AbortController()
  const timer = globalThis.setTimeout(() => controller.abort(), probeTimeoutMs)
  try {
    await fetcher(healthUrl, { method: 'GET', mode: 'no-cors', signal: controller.signal })
    return 'reachable'
  } catch {
    return controller.signal.aborted ? 'inconclusive' : 'unreachable'
  } finally {
    globalThis.clearTimeout(timer)
  }
}
