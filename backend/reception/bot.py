import json
import re
from dataclasses import dataclass
from typing import Optional

import anthropic
from config import settings
from reception.session import session_manager
from reception.prompts import get_system_prompt


@dataclass
class BotResponse:
    session_id: str
    message: str
    booking_intent: Optional[dict] = None  # populated when bot collected all booking info


class ReceptionBot:
    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        channel: str = "web",
    ) -> BotResponse:
        # Create session if new conversation
        if not session_id:
            session_id = session_manager.new_session_id()

        # Persist user message
        history = await session_manager.append_message(session_id, "user", message)

        # Call Claude Haiku
        response = await self._client.messages.create(
            model=settings.claude_model,
            max_tokens=512,
            system=get_system_prompt(),
            messages=history,
        )

        assistant_text = response.content[0].text

        # Persist assistant reply
        await session_manager.append_message(session_id, "assistant", assistant_text)

        # Extract booking intent JSON if present
        booking_intent = self._extract_booking_intent(assistant_text)

        # Strip the JSON block from the visible message
        visible_message = self._strip_json_block(assistant_text)

        return BotResponse(
            session_id=session_id,
            message=visible_message.strip(),
            booking_intent=booking_intent,
        )

    def _extract_booking_intent(self, text: str) -> Optional[dict]:
        """Parse the structured JSON block the bot appends when booking intent is complete."""
        pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            if data.get("intent") == "book_appointment":
                return data
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _strip_json_block(self, text: str) -> str:
        """Remove the JSON block from the patient-facing message."""
        return re.sub(r"```json.*?```", "", text, flags=re.DOTALL).strip()


reception_bot = ReceptionBot()
