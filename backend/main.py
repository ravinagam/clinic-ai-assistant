import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from database import create_tables, AsyncSessionLocal
from channels.web_api import router as web_router
from channels.twilio_webhook import router as twilio_router
from staff.router import router as staff_router
from notifications.service import log_notification_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ── Reminder cron job ─────────────────────────────────────────────────────────

async def send_reminders():
    """Run daily — sends reminder to patients with appointments tomorrow."""
    from datetime import datetime, timedelta, date, time
    from zoneinfo import ZoneInfo
    from sqlalchemy import select, and_
    from appointments.models import Appointment, AppointmentStatus
    from notifications.service import send_appointment_reminder

    tomorrow = (datetime.now() + timedelta(days=1)).date()
    day_start = datetime.combine(tomorrow, time(0, 0))
    day_end = datetime.combine(tomorrow, time(23, 59))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment).where(
                and_(
                    Appointment.scheduled_at >= day_start,
                    Appointment.scheduled_at <= day_end,
                    Appointment.status == AppointmentStatus.scheduled,
                    Appointment.reminder_sent == False,
                )
            )
        )
        appointments = result.scalars().all()

        for apt in appointments:
            try:
                await db.refresh(apt, ["patient", "doctor"])
                await send_appointment_reminder(
                    patient_name=apt.patient.name,
                    patient_phone=apt.patient.phone,
                    patient_email=apt.patient.email,
                    doctor_name=apt.doctor.name,
                    scheduled_at=apt.scheduled_at,
                    appointment_id=apt.id,
                )
                apt.reminder_sent = True
                logger.info(f"Reminder sent for appointment #{apt.id}")
            except Exception as e:
                logger.error(f"Reminder failed for #{apt.id}: {e}")

        await db.commit()


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry DB connection — handles any residual startup lag
    import asyncio
    for attempt in range(10):
        try:
            await create_tables()
            break
        except Exception as e:
            if attempt == 9:
                raise
            logger.warning(f"DB not ready (attempt {attempt + 1}/10): {e}. Retrying in 3s…")
            await asyncio.sleep(3)

    log_notification_config()
    scheduler.add_job(send_reminders, "cron", hour=9, minute=0)  # 9 AM daily
    scheduler.start()
    logger.info("Clinic AI backend started.")
    yield
    scheduler.shutdown()
    logger.info("Clinic AI backend shut down.")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Clinic AI OS — Reception API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(web_router)
app.include_router(twilio_router)
app.include_router(staff_router)


@app.get("/health")
async def health():
    return {"status": "ok", "clinic": settings.clinic_name}
