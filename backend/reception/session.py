import json
import uuid
from datetime import timedelta
from typing import Optional
import redis.asyncio as aioredis
from config import settings

SESSION_TTL = timedelta(minutes=30)
MAX_HISTORY = 20  # keep last 20 turns to stay within token limits


class SessionManager:
    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def get_history(self, session_id: str) -> list[dict]:
        r = await self.client()
        raw = await r.get(self._key(session_id))
        if not raw:
            return []
        return json.loads(raw)

    async def append_message(self, session_id: str, role: str, content: str) -> list[dict]:
        history = await self.get_history(session_id)
        history.append({"role": role, "content": content})
        # Trim to avoid token bloat — keep last MAX_HISTORY messages
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        r = await self.client()
        await r.setex(
            self._key(session_id),
            int(SESSION_TTL.total_seconds()),
            json.dumps(history),
        )
        return history

    async def clear(self, session_id: str) -> None:
        r = await self.client()
        await r.delete(self._key(session_id))

    async def touch(self, session_id: str) -> None:
        """Reset TTL without modifying content."""
        r = await self.client()
        await r.expire(self._key(session_id), int(SESSION_TTL.total_seconds()))

    @staticmethod
    def new_session_id() -> str:
        return str(uuid.uuid4())


session_manager = SessionManager()
