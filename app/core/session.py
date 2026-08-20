import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class SessionState:
    slots: dict[str, object] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


class SessionStore:
    """역질문 이후 슬롯을 유지하기 위한 최소 in-memory 세션 저장소.

    프로세스 재기동 시 초기화된다. 다중 워커/영속성이 필요해지면
    Redis 등으로 교체하되 인터페이스(get/merge/clear)는 유지한다.
    """

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, SessionState] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> dict[str, object]:
        with self._lock:
            self._evict_expired()
            state = self._store.get(session_id)
            return dict(state.slots) if state else {}

    def merge(self, session_id: str, new_slots: dict[str, object]) -> dict[str, object]:
        with self._lock:
            self._evict_expired()
            state = self._store.setdefault(session_id, SessionState())
            state.slots.update({k: v for k, v in new_slots.items() if v is not None})
            state.updated_at = time.time()
            return dict(state.slots)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._store.items() if now - s.updated_at > self._ttl]
        for sid in expired:
            del self._store[sid]


_default_store: SessionStore | None = None


def get_session_store(ttl_seconds: int = 1800) -> SessionStore:
    global _default_store
    if _default_store is None:
        _default_store = SessionStore(ttl_seconds=ttl_seconds)
    return _default_store
