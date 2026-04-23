import json
import re
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
import logging

import anthropic

from config import settings
from reception.session import session_manager
from reception.prompts import get_system_prompt

logger = logging.getLogger(__name__)

# Tool the bot can call to look up real doctor availability from the DB
TOOLS = [
    {
        "name": "get_available_doctors",
        "description": (
            "Look up which doctors are available at this clinic for a given symptom or specialty. "
            "Call this when the patient asks: which doctor should I see, who is available, "
            "do you have a cardiologist, who treats chest pain, etc. "
            "Returns real doctor names and their next available appointment slots."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symptoms_or_specialty": {
                    "type": "string",
                    "description": "Patient's symptoms or the medical specialty they asked about (e.g. 'chest pain', 'cardiology', 'skin rash')",
                },
                "preferred_date": {
                    "type": "string",
                    "description": "Optional preferred date in YYYY-MM-DD format",
                },
            },
            "required": ["symptoms_or_specialty"],
        },
    }
]

ToolHandler = Callable[[str, dict], Awaitable[str]]


@dataclass
class BotResponse:
    session_id: str
    message: str
    booking_intent: Optional[dict] = None


class ReceptionBot:
    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        channel: str = "web",
        tool_handler: Optional[ToolHandler] = None,
    ) -> BotResponse:
        if not session_id:
            session_id = session_manager.new_session_id()

        history = await session_manager.append_message(session_id, "user", message)

        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
        ]

        try:
            response = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=get_system_prompt(),
                messages=messages,
                tools=TOOLS if tool_handler else [],
            )

            # Handle tool call — Claude wants to query doctor availability
            if response.stop_reason == "tool_use" and tool_handler:
                tool_block = next(b for b in response.content if b.type == "tool_use")
                logger.info(f"Bot tool call: {tool_block.name}({tool_block.input})")

                tool_result = await tool_handler(tool_block.name, tool_block.input)

                # Feed result back to Claude for the final patient-facing reply
                messages_with_tool = messages + [
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": tool_result,
                        }],
                    },
                ]

                final_response = await self._client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=512,
                    system=get_system_prompt(),
                    messages=messages_with_tool,
                    tools=TOOLS,
                )
                assistant_text = next(
                    b.text for b in final_response.content if b.type == "text"
                )
            else:
                assistant_text = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return BotResponse(
                session_id=session_id,
                message="I'm having a temporary issue. Please try again in a moment.",
                booking_intent=None,
            )

        # Save only the final text reply to session history
        await session_manager.append_message(session_id, "assistant", assistant_text)

        booking_intent = self._extract_booking_intent(assistant_text)
        visible_message = self._strip_json_block(assistant_text)

        return BotResponse(
            session_id=session_id,
            message=visible_message.strip(),
            booking_intent=booking_intent,
        )

    def _extract_booking_intent(self, text: str) -> Optional[dict]:
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
        return re.sub(r"```json.*?```", "", text, flags=re.DOTALL).strip()


reception_bot = ReceptionBot()
