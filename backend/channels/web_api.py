"""
Web channel — REST endpoints consumed by the React chat widget.
"""
from datetime import datetime, date, timedelta
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from database import get_db
from reception.bot import reception_bot
from appointments.engine import (
    book_appointment, get_available_slots, get_first_available_doctor,
    get_best_doctor, get_doctor_by_name, get_next_available_slot_for_doctor,
    classify_specialty_with_ai, classify_specialty_with_keywords,
)
from appointments.models import Channel, Conversation, Doctor
from notifications.service import send_booking_confirmation
from channels.datetime_parser import parse_preferred_datetime

router = APIRouter(prefix="/chat", tags=["Web Chat"])


# ── Doctor availability tool handler ─────────────────────────────────────────

def make_tool_handler(db: AsyncSession):
    """Returns a tool handler closure with DB access for use in the chat endpoint."""

    async def handle_tool(tool_name: str, tool_input: dict) -> str:
        if tool_name != "get_available_doctors":
            return "Unknown tool."

        symptoms = tool_input.get("symptoms_or_specialty", "")
        preferred_date_str = tool_input.get("preferred_date")

        preferred_date = None
        if preferred_date_str:
            try:
                preferred_date = date.fromisoformat(preferred_date_str)
            except ValueError:
                pass

        # Classify the symptoms → specialty
        specialty = await classify_specialty_with_ai(symptoms)
        if not specialty:
            specialty = classify_specialty_with_keywords(symptoms)

        # Fetch doctors matching the specialty (or all doctors if no match)
        if specialty:
            primary_word = specialty.split()[0]
            result = await db.execute(
                select(Doctor).where(
                    Doctor.is_active == True,
                    func.lower(Doctor.specialty).contains(primary_word),
                )
            )
            doctors = result.scalars().all()
        else:
            result = await db.execute(
                select(Doctor).where(Doctor.is_active == True)
            )
            doctors = result.scalars().all()

        if not doctors:
            return f"No doctors found for '{symptoms}'. The clinic will assign the most suitable doctor when you book."

        # Get next available slot for each doctor
        lines = []
        for doctor in doctors:
            next_slot = await get_next_available_slot_for_doctor(db, doctor.id, preferred_date)
            if next_slot:
                slot_str = next_slot.strftime("%A, %d %b at %I:%M %p")
                lines.append(f"• Dr. {doctor.name} ({doctor.specialty or 'General'}) — Next available: {slot_str}")
            else:
                lines.append(f"• Dr. {doctor.name} ({doctor.specialty or 'General'}) — No slots in the next 2 weeks")

        specialty_label = f" for {specialty}" if specialty else ""
        return f"Available doctors{specialty_label}:\n" + "\n".join(lines)

    return handle_tool


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
    from main import logger
    logger.info(f"Incoming chat message: {req.message}")
    from reception.session import session_manager

    bot_response = await reception_bot.chat(
        message=req.message,
        session_id=req.session_id,
        channel="web",
        tool_handler=make_tool_handler(db),
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
            # Parse preferred datetime first so we can factor it into doctor selection
            preferred_dt = parse_preferred_datetime(intent.get("preferred_datetime", ""))
            preferred_date = preferred_dt.date() if preferred_dt else None

            preferred_doctor_name = (intent.get("preferred_doctor") or "").strip()

            # ── Patient requested a specific doctor ───────────────────────────
            if preferred_doctor_name and preferred_doctor_name.lower() != "null":
                doctor = await get_doctor_by_name(db, preferred_doctor_name)

                if not doctor:
                    # Doctor name not found — fall back to symptom-based assignment
                    logger.info(f"Requested doctor '{preferred_doctor_name}' not found, falling back to symptom match")
                    doctor = await get_best_doctor(db, intent.get("reason", ""), preferred_date)
                else:
                    # Doctor found — check if they have a slot at the preferred time
                    slot = await find_best_slot(db, doctor.id, preferred_dt)
                    if not slot:
                        # No slot at all in next 14 days
                        return ChatResponse(
                            session_id=bot_response.session_id,
                            message=bot_response.message + f"\n\n⚠️ Dr. {doctor.name} has no available slots in the next 2 weeks. Our team will contact you to schedule.",
                            booking_completed=False,
                        )

                    # Check if preferred time was honoured; if not, we already have the next slot
                    slot_str = slot.strftime("%A, %d %b at %I:%M %p")

                    # If the slot differs significantly from the preferred time, warn the patient
                    if preferred_dt and abs((slot - preferred_dt).total_seconds()) > 3600:
                        # Find next available slot to suggest
                        next_slot = await get_next_available_slot_for_doctor(db, doctor.id, preferred_date)
                        next_str = next_slot.strftime("%A, %d %b at %I:%M %p") if next_slot else None
                        suggestion = f" The earliest available slot with Dr. {doctor.name} is {next_str}." if next_str else ""
                        return ChatResponse(
                            session_id=bot_response.session_id,
                            message=bot_response.message + f"\n\n⚠️ Dr. {doctor.name} is not available at your preferred time.{suggestion} Would you like to book that slot instead? Please confirm and we'll finalise your appointment.",
                            booking_completed=False,
                        )

            # ── No specific doctor — auto-assign by symptoms ──────────────────
            else:
                doctor = await get_best_doctor(db, intent.get("reason", ""), preferred_date)

            if not doctor:
                return ChatResponse(
                    session_id=bot_response.session_id,
                    message=bot_response.message + "\n\nNo doctors are configured yet. Please call us to book.",
                    booking_completed=False,
                )

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
