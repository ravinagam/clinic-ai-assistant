import enum
from datetime import datetime, time
from sqlalchemy import (
    Column, String, Integer, DateTime, Time, Boolean,
    ForeignKey, Enum as SAEnum, Text, JSON, func
)
from sqlalchemy.orm import relationship
from database import Base


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class Channel(str, enum.Enum):
    web = "web"
    whatsapp = "whatsapp"
    sms = "sms"
    phone = "phone"


class DayOfWeek(int, enum.Enum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(120), nullable=True)
    date_of_birth = Column(String(20), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    appointments = relationship("Appointment", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    specialty = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(120), nullable=True)
    google_calendar_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    availability = relationship("DoctorAvailability", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class DoctorAvailability(Base):
    """Recurring weekly availability windows per doctor."""
    __tablename__ = "doctor_availability"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    day_of_week = Column(SAEnum(DayOfWeek), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_duration_minutes = Column(Integer, default=20)
    is_active = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="availability")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=20)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(AppointmentStatus), default=AppointmentStatus.scheduled)
    channel = Column(SAEnum(Channel), default=Channel.web)
    notes = Column(Text, nullable=True)
    reminder_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")


class Conversation(Base):
    """Persisted conversation logs for audit + training."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    channel = Column(SAEnum(Channel), default=Channel.web)
    patient_phone = Column(String(20), nullable=True)
    messages = Column(JSON, default=list)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
