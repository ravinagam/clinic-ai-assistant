"""
Doctor-facing API — PIN login, personal schedule, appointment updates (status + notes).
"""
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import bcrypt
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from appointments.models import (
    Appointment, AppointmentStatus, Doctor, Patient,
)

router = APIRouter(prefix="/doctor", tags=["Doctor Portal"])
bearer = HTTPBearer()

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_token(doctor_id: int, doctor_name: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(doctor_id), "name": doctor_name, "exp": expire},
        settings.secret_key,
        algorithm=JWT_ALGORITHM,
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")


async def get_current_doctor(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Doctor:
    payload = _decode_token(creds.credentials)
    doctor_id = int(payload["sub"])
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id, Doctor.is_active == True))
    doctor = result.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found.")
    return doctor


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    doctor_id: int
    pin: str


class LoginResponse(BaseModel):
    token: str
    doctor_id: int
    doctor_name: str
    specialty: Optional[str]


class AppointmentNoteUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def doctor_login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Doctor).where(Doctor.id == req.doctor_id, Doctor.is_active == True)
    )
    doctor = result.scalar_one_or_none()

    if not doctor or not doctor.pin_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid doctor or PIN not set. Ask the clinic admin to set your PIN.",
        )

    if not bcrypt.checkpw(req.pin.encode('utf-8'), doctor.pin_hash.encode('utf-8')):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect PIN.")

    return LoginResponse(
        token=_create_token(doctor.id, doctor.name),
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        specialty=doctor.specialty,
    )


@router.get("/me")
async def get_me(doctor: Doctor = Depends(get_current_doctor)):
    return {
        "id": doctor.id,
        "name": doctor.name,
        "specialty": doctor.specialty,
        "phone": doctor.phone,
        "email": doctor.email,
    }


@router.get("/appointments")
async def my_appointments(
    days: int = 7,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Return appointments for the logged-in doctor — today + next `days` days."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    end = datetime.combine(date.today() + timedelta(days=days), datetime.max.time().replace(microsecond=0))

    result = await db.execute(
        select(Appointment)
        .where(
            and_(
                Appointment.doctor_id == doctor.id,
                Appointment.scheduled_at >= today_start,
                Appointment.scheduled_at <= end,
                Appointment.status.not_in([AppointmentStatus.cancelled]),
            )
        )
        .options(selectinload(Appointment.patient))
        .order_by(Appointment.scheduled_at)
    )
    appointments = result.scalars().all()

    return [
        {
            "id": a.id,
            "scheduled_at": a.scheduled_at.isoformat(),
            "status": a.status,
            "reason": a.reason,
            "notes": a.notes,
            "channel": a.channel,
            "patient_name": a.patient.name if a.patient else "—",
            "patient_phone": a.patient.phone if a.patient else "—",
            "patient_email": a.patient.email if a.patient else None,
        }
        for a in appointments
    ]


@router.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: int,
    body: AppointmentNoteUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Doctor updates status (completed/no_show) and/or adds consultation notes."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.doctor_id == doctor.id,
        )
    )
    apt = result.scalar_one_or_none()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    if body.status:
        try:
            apt.status = AppointmentStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    if body.notes is not None:
        apt.notes = body.notes

    await db.commit()
    await db.refresh(apt)
    return {"id": apt.id, "status": apt.status, "notes": apt.notes}
