from datetime import datetime, timedelta, date, time
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, func, String
from sqlalchemy.ext.asyncio import AsyncSession

from appointments.models import (
    Appointment, AppointmentStatus, Patient, Doctor,
    DoctorAvailability, DayOfWeek, Channel, Conversation,
)
from config import settings

TZ = ZoneInfo(settings.clinic_timezone)


# ── Slot utilities ────────────────────────────────────────────────────────────

def generate_slots(start: time, end: time, duration_minutes: int) -> list[time]:
    """Return list of slot start times within [start, end)."""
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    delta = timedelta(minutes=duration_minutes)
    while current + delta <= end_dt:
        slots.append(current.time())
        current += delta
    return slots


async def get_available_slots(
    db: AsyncSession,
    doctor_id: int,
    target_date: date,
) -> list[datetime]:
    """Return list of available datetimes for a doctor on a given date."""
    day = DayOfWeek(target_date.weekday())

    # Fetch availability windows for this day
    avail_result = await db.execute(
        select(DoctorAvailability).where(
            and_(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.day_of_week == day,
                DoctorAvailability.is_active == True,
            )
        )
    )
    windows = avail_result.scalars().all()
    if not windows:
        return []

    # Fetch already-booked slots on this date (naive datetimes — DB stores TIMESTAMP WITHOUT TIME ZONE)
    day_start = datetime.combine(target_date, time(0, 0))
    day_end = datetime.combine(target_date, time(23, 59))

    booked_result = await db.execute(
        select(Appointment.scheduled_at).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_at >= day_start,
                Appointment.scheduled_at <= day_end,
                Appointment.status.not_in(
                    [AppointmentStatus.cancelled, AppointmentStatus.no_show]
                ),
            )
        )
    )
    booked_times = {r.scheduled_at.time() for r in booked_result}

    # Build free slot list
    free_slots = []
    for window in windows:
        for slot_time in generate_slots(
            window.start_time, window.end_time, window.slot_duration_minutes
        ):
            if slot_time not in booked_times:
                slot_dt = datetime.combine(target_date, slot_time)
                # Only future slots
                if slot_dt > datetime.now():
                    free_slots.append(slot_dt)

    return sorted(free_slots)


# ── Patient helpers ───────────────────────────────────────────────────────────

async def get_or_create_patient(
    db: AsyncSession,
    name: str,
    phone: str,
    email: Optional[str] = None,
) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.phone == phone)
    )
    patient = result.scalar_one_or_none()
    if patient:
        if name and patient.name != name:
            patient.name = name
        return patient

    patient = Patient(name=name, phone=phone, email=email)
    db.add(patient)
    await db.flush()
    return patient


# ── Booking ───────────────────────────────────────────────────────────────────

async def book_appointment(
    db: AsyncSession,
    patient_name: str,
    patient_phone: str,
    doctor_id: int,
    scheduled_at: datetime,
    reason: str,
    channel: Channel = Channel.web,
    session_id: Optional[str] = None,
) -> Appointment:
    patient = await get_or_create_patient(db, patient_name, patient_phone)

    # Recheck slot is still free (race condition guard)
    duration_result = await db.execute(
        select(DoctorAvailability.slot_duration_minutes).where(
            DoctorAvailability.doctor_id == doctor_id,
            DoctorAvailability.is_active == True,
        ).limit(1)
    )
    duration = duration_result.scalar_one_or_none() or 20

    conflict = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_at == scheduled_at,
                Appointment.status.not_in(
                    [AppointmentStatus.cancelled, AppointmentStatus.no_show]
                ),
            )
        )
    )
    if conflict.scalar_one_or_none():
        raise ValueError("This slot was just taken. Please choose another time.")

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        duration_minutes=duration,
        reason=reason,
        status=AppointmentStatus.scheduled,
        channel=channel,
    )
    db.add(appointment)
    await db.flush()

    # Link conversation if provided
    if session_id:
        conv_result = await db.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
        conv = conv_result.scalar_one_or_none()
        if conv:
            conv.appointment_id = appointment.id

    await db.commit()
    await db.refresh(appointment)
    return appointment


# ── Cancellation ─────────────────────────────────────────────────────────────

async def cancel_appointment(db: AsyncSession, appointment_id: int) -> Appointment:
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    apt = result.scalar_one_or_none()
    if not apt:
        raise ValueError(f"Appointment {appointment_id} not found.")
    apt.status = AppointmentStatus.cancelled
    await db.commit()
    await db.refresh(apt)
    return apt


# ── Doctor resolver ───────────────────────────────────────────────────────────

# Symptom/reason → specialty keyword mapping
SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "oncology":       ["cancer", "tumor", "oncol", "chemo", "biopsy", "malignant"],
    "cardiology":     ["heart", "chest pain", "cardiac", "palpitation", "blood pressure", "bp"],
    "orthopedics":    ["bone", "joint", "fracture", "knee", "back pain", "spine", "ortho"],
    "pediatrics":     ["child", "baby", "infant", "kid", "pediatric"],
    "dermatology":    ["skin", "rash", "acne", "eczema", "derma", "allergy"],
    "ent":            ["ear", "nose", "throat", "runny", "sinus", "ent", "hearing"],
    "neurology":      ["headache", "migraine", "seizure", "neuro", "brain", "nerve"],
    "gastroenterology": ["stomach", "abdomen", "gastro", "digestion", "nausea", "vomit"],
    "gynecology":     ["gynec", "women", "menstrual", "pregnancy", "obstet"],
    "ophthalmology":  ["eye", "vision", "ophthalmol"],
    "psychiatry":     ["mental", "anxiety", "depression", "psychiatr", "stress"],
    "general medicine": ["general", "checkup", "fever", "cold", "flu", "cough", "fatigue"],
}


async def get_best_doctor(db: AsyncSession, reason: str) -> Optional[Doctor]:
    """
    Match patient reason to doctor specialty.
    Falls back to first active doctor if no specialty match found.
    """
    reason_lower = reason.lower()
    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        for kw in keywords:
            if kw in reason_lower:
                result = await db.execute(
                    select(Doctor).where(
                        Doctor.is_active == True,
                        func.lower(Doctor.specialty).contains(specialty.split()[0]),
                    ).limit(1)
                )
                doctor = result.scalar_one_or_none()
                if doctor:
                    return doctor
    return await get_first_available_doctor(db)


async def get_first_available_doctor(db: AsyncSession) -> Optional[Doctor]:
    result = await db.execute(
        select(Doctor).where(Doctor.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()
