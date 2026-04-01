"""
Staff portal API — appointment management, doctor config, availability setup.
"""
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from appointments.models import (
    Appointment, AppointmentStatus, Doctor, DoctorAvailability,
    Patient, DayOfWeek,
)

router = APIRouter(prefix="/staff", tags=["Staff Portal"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class DoctorCreate(BaseModel):
    name: str
    specialty: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class AvailabilityCreate(BaseModel):
    doctor_id: int
    day_of_week: int  # 0=Monday … 6=Sunday
    start_time: time
    end_time: time
    slot_duration_minutes: int = 20


class AppointmentUpdate(BaseModel):
    status: Optional[AppointmentStatus] = None
    notes: Optional[str] = None
    scheduled_at: Optional[datetime] = None


# ── Doctors ───────────────────────────────────────────────────────────────────

@router.post("/doctors")
async def create_doctor(body: DoctorCreate, db: AsyncSession = Depends(get_db)):
    doctor = Doctor(**body.model_dump())
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


@router.get("/doctors")
async def list_doctors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Doctor).where(Doctor.is_active == True))
    return result.scalars().all()


# ── Availability ──────────────────────────────────────────────────────────────

@router.post("/availability")
async def set_availability(
    body: AvailabilityCreate, db: AsyncSession = Depends(get_db)
):
    avail = DoctorAvailability(
        doctor_id=body.doctor_id,
        day_of_week=DayOfWeek(body.day_of_week),
        start_time=body.start_time,
        end_time=body.end_time,
        slot_duration_minutes=body.slot_duration_minutes,
    )
    db.add(avail)
    await db.commit()
    await db.refresh(avail)
    return avail


@router.get("/availability/{doctor_id}")
async def get_availability(doctor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DoctorAvailability).where(
            and_(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.is_active == True,
            )
        )
    )
    return result.scalars().all()


# ── Appointments ──────────────────────────────────────────────────────────────

@router.get("/appointments")
async def list_appointments(
    target_date: Optional[date] = None,
    doctor_id: Optional[int] = None,
    status: Optional[AppointmentStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Appointment)
    conditions = []

    if target_date:
        from datetime import time as _time
        day_start = datetime.combine(target_date, _time(0, 0))
        day_end = datetime.combine(target_date, _time(23, 59))
        conditions.append(Appointment.scheduled_at >= day_start)
        conditions.append(Appointment.scheduled_at <= day_end)

    if doctor_id:
        conditions.append(Appointment.doctor_id == doctor_id)

    if status:
        conditions.append(Appointment.status == status)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.options(
        selectinload(Appointment.doctor),
        selectinload(Appointment.patient),
    ).order_by(Appointment.scheduled_at)

    result = await db.execute(query)
    appointments = result.scalars().all()

    return [
        {
            "id": a.id,
            "scheduled_at": a.scheduled_at.isoformat(),
            "status": a.status,
            "reason": a.reason,
            "channel": a.channel,
            "notes": a.notes,
            "doctor_name": a.doctor.name if a.doctor else "—",
            "patient_name": a.patient.name if a.patient else "—",
            "patient_phone": a.patient.phone if a.patient else "—",
        }
        for a in appointments
    ]


@router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    apt = result.scalar_one_or_none()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return apt


@router.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    apt = result.scalar_one_or_none()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    if body.status is not None:
        apt.status = body.status
    if body.notes is not None:
        apt.notes = body.notes
    if body.scheduled_at is not None:
        apt.scheduled_at = body.scheduled_at

    await db.commit()
    await db.refresh(apt)
    return apt


# ── Patients ──────────────────────────────────────────────────────────────────

@router.get("/patients")
async def list_patients(
    search: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    query = select(Patient)
    if search:
        from sqlalchemy import or_
        query = query.where(
            or_(
                Patient.name.ilike(f"%{search}%"),
                Patient.phone.ilike(f"%{search}%"),
            )
        )
    result = await db.execute(query.order_by(Patient.name))
    return result.scalars().all()


@router.get("/patients/{patient_id}/appointments")
async def patient_appointments(patient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
    )
    return result.scalars().all()
