"""
Web channel — REST endpoints consumed by the React chat widget.
"""
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from reception.bot import reception_bot
from appointments.engine import (
    book_appointment, get_available_slots, get_first_available_doctor, get_best_doctor,
)
from appointments.models import Channel, Conversation
from notifications.service import send_booking_confirmation
from channels.datetime_parser import parse_preferred_datetime

router = APIRouter(prefix="/chat", tags=["Web Chat"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    booking_completed: bool = False
    appointment_id: Optional[int] = None


# ── Slot finder ───────────────────────────────────────────────────────────────

async def find_best_slot(
    db: AsyncSession,
    doctor_id: int,
    preferred_dt: Optional[datetime],
) -> Optional[datetime]:
    """
    Find the best available slot:
    1. If preferred_dt given, try that day first (slot >= preferred time).
    2. Then search up to 14 days ahead for any open slot.
    """
    start_date = preferred_dt.date() if preferred_dt else (datetime.now() + timedelta(days=1)).date()

    for days_ahead in range(14):
        check_date = start_date + timedelta(days=days_ahead)
        slots = await get_available_slots(db, doctor_id, check_date)
        if not slots:
            continue
        if preferred_dt and days_ahead == 0:
            pref_time = preferred_dt.time()
            # Prefer slot at or after requested time
            after = [s for s in slots if s.time() >= pref_time]
            if after:
                return after[0]
            # No slot after requested time — return latest slot of that day
            # (patient asked for 5pm but last slot is 4:40 → give 4:40 same day)
            return slots[-1]
        return slots[0]

    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/message", response_model=ChatResponse)
async def send_message(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    from reception.session import session_manager

    bot_response = await reception_bot.chat(
        message=req.message,
        session_id=req.session_id,
        channel="web",
    )

    # Persist conversation log
    result = await db.execute(
        select(Conversation).where(Conversation.session_id == bot_response.session_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(session_id=bot_response.session_id, channel=Channel.web)
        db.add(conv)
    conv.messages = await session_manager.get_history(bot_response.session_id)
    await db.commit()

    # Auto-book when intent detected
    if bot_response.booking_intent:
        intent = bot_response.booking_intent
        try:
            doctor = await get_best_doctor(db, intent.get("reason", ""))
            if not doctor:
                return ChatResponse(
                    session_id=bot_response.session_id,
                    message=bot_response.message + "\n\nNo doctors are configured yet. Please call us to book.",
                    booking_completed=False,
                )

            # Parse preferred datetime (handles ISO + natural language)
            preferred_dt = parse_preferred_datetime(intent.get("preferred_datetime", ""))

            # Find best available slot
            slot = await find_best_slot(db, doctor.id, preferred_dt)
            if not slot:
                return ChatResponse(
                    session_id=bot_response.session_id,
                    message=bot_response.message + "\n\nI couldn't find an open slot in the next 2 weeks. Our team will call you to confirm a time.",
                    booking_completed=False,
                )

            appointment = await book_appointment(
                db=db,
                patient_name=intent["name"],
                patient_phone=intent["phone"],
                doctor_id=doctor.id,
                scheduled_at=slot,
                reason=intent.get("reason", "General Consultation"),
                channel=Channel.web,
                session_id=bot_response.session_id,
            )

            await send_booking_confirmation(
                patient_name=intent["name"],
                patient_phone=intent["phone"],
                patient_email=None,
                doctor_name=doctor.name,
                scheduled_at=slot,
                appointment_id=appointment.id,
                channel="web",
            )

            slot_str = slot.strftime("%A, %d %b at %I:%M %p")
            return ChatResponse(
                session_id=bot_response.session_id,
                message=bot_response.message + f"\n\n✅ Booked for {slot_str} with Dr. {doctor.name}.",
                booking_completed=True,
                appointment_id=appointment.id,
            )

        except ValueError as e:
            return ChatResponse(
                session_id=bot_response.session_id,
                message=f"{bot_response.message}\n\n⚠️ {e}",
                booking_completed=False,
            )

    return ChatResponse(
        session_id=bot_response.session_id,
        message=bot_response.message,
    )


@router.get("/slots")
async def available_slots(
    target_date: date,
    doctor_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    if not doctor_id:
        doctor = await get_first_available_doctor(db)
        if not doctor:
            raise HTTPException(status_code=404, detail="No doctors configured.")
        doctor_id = doctor.id

    slots = await get_available_slots(db, doctor_id, target_date)
    return {"slots": [s.isoformat() for s in slots]}
