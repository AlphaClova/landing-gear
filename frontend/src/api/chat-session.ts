const CHAT_SESSION_STORAGE_KEY = 'landing-gear.chat-session-id'

type SessionStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
type UuidFactory = () => string

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export const isValidChatSessionId = (value: unknown): value is string =>
  typeof value === 'string' && UUID_PATTERN.test(value)

const fallbackUuid = (): string => {
  const bytes = new Uint8Array(16)
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes)
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256)
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

const defaultUuidFactory: UuidFactory = () => globalThis.crypto?.randomUUID?.() ?? fallbackUuid()

const browserSessionStorage = (): SessionStorage | null => {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

const safelyRead = (storage: SessionStorage | null): string | null => {
  try {
    return storage?.getItem(CHAT_SESSION_STORAGE_KEY) ?? null
  } catch {
    return null
  }
}

const safelyWrite = (storage: SessionStorage | null, sessionId: string) => {
  try {
    storage?.setItem(CHAT_SESSION_STORAGE_KEY, sessionId)
  } catch {
    // Storage may be unavailable in SSR, privacy mode, or constrained embeds.
  }
}

export function getChatSessionId(
  storage: SessionStorage | null = browserSessionStorage(),
  uuidFactory: UuidFactory = defaultUuidFactory,
): string {
  const existing = safelyRead(storage)
  if (isValidChatSessionId(existing)) return existing

  const created = uuidFactory()
  if (!isValidChatSessionId(created)) throw new TypeError('Chat session UUID factory returned an invalid UUID')
  safelyWrite(storage, created)
  return created
}

export function resetChatSession(
  storage: SessionStorage | null = browserSessionStorage(),
  uuidFactory: UuidFactory = defaultUuidFactory,
): string {
  try {
    storage?.removeItem(CHAT_SESSION_STORAGE_KEY)
  } catch {
    // A reset still returns a fresh ephemeral ID when storage cannot be used.
  }
  return getChatSessionId(storage, uuidFactory)
}

export { CHAT_SESSION_STORAGE_KEY }
