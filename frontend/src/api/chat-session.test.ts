import { describe, expect, it } from 'vitest'
import {
  CHAT_SESSION_STORAGE_KEY,
  getChatSessionId,
  isValidChatSessionId,
  resetChatSession,
} from './chat-session'

const UUID_ONE = '123e4567-e89b-42d3-a456-426614174000'
const UUID_TWO = '123e4567-e89b-42d3-b456-426614174001'

class MemoryStorage {
  readonly values = new Map<string, string>()
  getItem(key: string) { return this.values.get(key) ?? null }
  setItem(key: string, value: string) { this.values.set(key, value) }
  removeItem(key: string) { this.values.delete(key) }
}

describe('chat session', () => {
  it('creates and stores a UUID on the first call', () => {
    const storage = new MemoryStorage()
    expect(getChatSessionId(storage, () => UUID_ONE)).toBe(UUID_ONE)
    expect(storage.getItem(CHAT_SESSION_STORAGE_KEY)).toBe(UUID_ONE)
    expect(isValidChatSessionId(UUID_ONE)).toBe(true)
  })

  it('reuses the existing UUID in the same tab storage', () => {
    const storage = new MemoryStorage()
    storage.setItem(CHAT_SESSION_STORAGE_KEY, UUID_ONE)
    expect(getChatSessionId(storage, () => UUID_TWO)).toBe(UUID_ONE)
  })

  it('replaces a damaged stored ID', () => {
    const storage = new MemoryStorage()
    storage.setItem(CHAT_SESSION_STORAGE_KEY, 'damaged')
    expect(getChatSessionId(storage, () => UUID_TWO)).toBe(UUID_TWO)
    expect(storage.getItem(CHAT_SESSION_STORAGE_KEY)).toBe(UUID_TWO)
  })

  it('reset removes the old ID and returns a fresh UUID', () => {
    const storage = new MemoryStorage()
    storage.setItem(CHAT_SESSION_STORAGE_KEY, UUID_ONE)
    expect(resetChatSession(storage, () => UUID_TWO)).toBe(UUID_TWO)
    expect(storage.getItem(CHAT_SESSION_STORAGE_KEY)).toBe(UUID_TWO)
  })

  it('stores only the session key and no question or profile data', () => {
    const storage = new MemoryStorage()
    getChatSessionId(storage, () => UUID_ONE)
    expect([...storage.values.keys()]).toEqual([CHAT_SESSION_STORAGE_KEY])
    expect([...storage.values.values()].join(' ')).not.toMatch(/question|retirement|profile/i)
  })

  it('works without window-backed storage', () => {
    expect(getChatSessionId(null, () => UUID_ONE)).toBe(UUID_ONE)
    expect(resetChatSession(null, () => UUID_TWO)).toBe(UUID_TWO)
  })

  it('works when storage access throws', () => {
    const storage = {
      getItem: () => { throw new DOMException('blocked') },
      setItem: () => { throw new DOMException('blocked') },
      removeItem: () => { throw new DOMException('blocked') },
    }
    expect(getChatSessionId(storage, () => UUID_ONE)).toBe(UUID_ONE)
    expect(resetChatSession(storage, () => UUID_TWO)).toBe(UUID_TWO)
  })
})
