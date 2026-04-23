from datetime import datetime, timedelta, date, time
from typing import Optional
from zoneinfo import ZoneInfo
import logging

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from appointments.models import (
    Appointment, AppointmentStatus, Patient, Doctor,
    DoctorAvailability, DayOfWeek, Channel, Conversation,
)
from config import settings

TZ = ZoneInfo(settings.clinic_timezone)
logger = logging.getLogger(__name__)


# ── Slot utilities ────────────────────────────────────────────────────────────

def generate_slots(start: time, end: time, duration_minutes: int) -> list[time]:
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
    day = DayOfWeek(target_date.weekday())

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

    free_slots = []
    for window in windows:
        for slot_time in generate_slots(
            window.start_time, window.end_time, window.slot_duration_minutes
        ):
            if slot_time not in booked_times:
                slot_dt = datetime.combine(target_date, slot_time)
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
    # Match on both phone AND name — same phone with a different name is a different
    # patient (e.g. a father booking for his son using his own number).
    result = await db.execute(
        select(Patient).where(
            Patient.phone == phone,
            func.lower(Patient.name) == name.strip().lower(),
        )
    )
    patient = result.scalar_one_or_none()
    if patient:
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

# Known specialties the clinic can handle — must match Doctor.specialty values in DB
KNOWN_SPECIALTIES = [
    "general medicine", "cardiology", "orthopedics", "pediatrics",
    "dermatology", "ent", "neurology", "gastroenterology",
    "gynecology", "ophthalmology", "psychiatry", "oncology",
    "urology", "endocrinology", "pulmonology", "rheumatology",
]

# Keyword fallback in case Claude call fails
SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "oncology":          ["cancer", "tumor", "oncol", "chemo", "biopsy", "malignant"],
    "cardiology":        ["heart", "chest pain", "cardiac", "palpitation", "blood pressure", "bp", "cholesterol"],
    "orthopedics":       ["bone", "joint", "fracture", "knee", "back pain", "spine", "ortho", "shoulder", "ankle", "ligament"],
    "pediatrics":        ["child", "baby", "infant", "kid", "pediatric", "toddler", "newborn"],
    "dermatology":       ["skin", "rash", "acne", "eczema", "derma", "allergy", "itching", "psoriasis", "hair loss"],
    "ent":               ["ear", "nose", "throat", "runny", "sinus", "ent", "hearing", "tonsil", "snoring"],
    "neurology":         ["headache", "migraine", "seizure", "neuro", "brain", "nerve", "dizziness", "numbness", "memory"],
    "gastroenterology":  ["stomach", "abdomen", "gastro", "digestion", "nausea", "vomit", "diarrhea", "constipation", "bloating", "liver"],
    "gynecology":        ["gynec", "women", "menstrual", "pregnancy", "obstet", "period", "uterus", "ovary"],
    "ophthalmology":     ["eye", "vision", "ophthalmol", "blurry", "glaucoma", "cataract"],
    "psychiatry":        ["mental", "anxiety", "depression", "psychiatr", "stress", "insomnia", "panic", "mood"],
    "urology":           ["urine", "urinary", "kidney", "bladder", "prostate"],
    "endocrinology":     ["diabetes", "thyroid", "hormone", "weight gain", "sugar"],
    "pulmonology":       ["lung", "breathing", "asthma", "cough", "respiratory", "shortness of breath"],
    "general medicine":  ["general", "checkup", "fever", "cold", "flu", "fatigue", "body ache", "weakness"],
}


async def classify_specialty_with_ai(reason: str) -> Optional[str]:
    """Use Claude Haiku to semantically classify patient symptoms into a specialty."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        specialties_str = ", ".join(KNOWN_SPECIALTIES)

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=15,
            messages=[{
                "role": "user",
                "content": (
                    f'Patient complaint: "{reason}"\n\n'
                    f"Which medical specialty is most appropriate? "
                    f"Choose exactly one from: {specialties_str}\n\n"
                    f"Reply with ONLY the specialty name, nothing else."
                ),
            }],
        )
        raw = response.content[0].text.strip().lower()
        # Match against known list (handle partial matches)
        for s in KNOWN_SPECIALTIES:
            if raw == s or raw.startswith(s) or s.startswith(raw):
                logger.info(f"AI classified '{reason[:40]}' → '{s}'")
                return s
    except Exception as e:
        logger.warning(f"AI specialty classification failed: {e}")
    return None


def classify_specialty_with_keywords(reason: str) -> Optional[str]:
    """Keyword fallback for specialty classification."""
    reason_lower = reason.lower()
    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        for kw in keywords:
            if kw in reason_lower:
                return specialty
    return None


async def find_doctor_with_earliest_slot(
    db: AsyncSession,
    candidates: list[Doctor],
    preferred_date: Optional[date],
) -> Optional[Doctor]:
    """
    Among a list of candidate doctors, return the one with the
    earliest available slot on or after preferred_date (up to 7 days).
    """
    start = preferred_date or (date.today() + timedelta(days=1))
    best_doctor: Optional[Doctor] = None
    best_slot: Optional[datetime] = None

    for doctor in candidates:
        for days_ahead in range(7):
            check_date = start + timedelta(days=days_ahead)
            slots = await get_available_slots(db, doctor.id, check_date)
            if slots:
                # First available slot for this doctor
                if best_slot is None or slots[0] < best_slot:
                    best_slot = slots[0]
                    best_doctor = doctor
                break  # no need to check further days for this doctor

    return best_doctor


async def get_best_doctor(
    db: AsyncSession,
    reason: str,
    preferred_date: Optional[date] = None,
) -> Optional[Doctor]:
    """
    Smart doctor assignment:
    1. Use Claude AI to semantically classify symptoms → specialty
    2. Find all active doctors with that specialty
    3. Among them, pick the one with earliest availability near preferred_date
    4. Fallback: keyword matching with same availability check
    5. Fallback: any doctor with availability
    6. Fallback: first active doctor
    """
    # Step 1: AI classification
    specialty = await classify_specialty_with_ai(reason)

    # Step 2: keyword fallback if AI failed
    if not specialty:
        specialty = classify_specialty_with_keywords(reason)
        if specialty:
            logger.info(f"Keyword classified '{reason[:40]}' → '{specialty}'")

    # Step 3: find doctors matching the specialty
    if specialty:
        # Match against the first meaningful word (handles "general medicine" → "general")
        primary_word = specialty.split()[0]
        result = await db.execute(
            select(Doctor).where(
                Doctor.is_active == True,
                func.lower(Doctor.specialty).contains(primary_word),
            )
        )
        candidates = result.scalars().all()

        if candidates:
            # Step 4: pick the one with earliest availability
            best = await find_doctor_with_earliest_slot(db, candidates, preferred_date)
            if best:
                logger.info(f"Assigned Dr. {best.name} ({best.specialty}) for: '{reason[:40]}'")
                return best
            # All specialty-matched doctors are fully booked — still return first match
            logger.info(f"Specialty match found but no slots — returning Dr. {candidates[0].name}")
            return candidates[0]

    # Step 5: any doctor with availability
    logger.info(f"No specialty match for '{reason[:40]}' — falling back to first available doctor")
    return await get_first_available_doctor(db)


async def get_first_available_doctor(db: AsyncSession) -> Optional[Doctor]:
    result = await db.execute(
        select(Doctor).where(Doctor.is_active == True).limit(1)
    )
    return result.scalar_one_or_none()


async def get_doctor_by_name(db: AsyncSession, name: str) -> Optional[Doctor]:
    """Fuzzy match a doctor by name (case-insensitive, partial match)."""
    name_clean = name.lower().replace("dr.", "").replace("dr ", "").strip()
    result = await db.execute(
        select(Doctor).where(
            Doctor.is_active == True,
            func.lower(Doctor.name).contains(name_clean),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_available_slot_for_doctor(
    db: AsyncSession,
    doctor_id: int,
    preferred_date: Optional[date] = None,
    days_to_search: int = 14,
) -> Optional[datetime]:
    """Return the earliest available slot for a specific doctor within days_to_search days."""
    start = preferred_date or date.today()
    for days_ahead in range(days_to_search):
        check_date = start + timedelta(days=days_ahead)
        slots = await get_available_slots(db, doctor_id, check_date)
        if slots:
            return slots[0]
    return None
