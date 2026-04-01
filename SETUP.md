# Clinic AI OS — Phase 1 Setup Guide

## Prerequisites
- Docker Desktop
- Node.js 20+ (for local frontend dev)
- Python 3.12+ (for local backend dev)

## Quick Start (Docker)

```bash
# 1. Copy env file and fill in your keys
cp .env.example .env

# 2. Start everything
docker-compose up --build

# Services:
#   API:          http://localhost:8000
#   API Docs:     http://localhost:8000/docs
#   Chat Widget:  http://localhost:3000
#   Staff Portal: http://localhost:3001
```

## Local Development (without Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in values
uvicorn main:app --reload
```

### Frontend (Chat Widget)
```bash
cd frontend/chat-widget
npm install
npm run dev   # http://localhost:3000
```

### Frontend (Staff Portal)
```bash
cd frontend/staff-portal
npm install
npm run dev   # http://localhost:3001
```

## First-Time Setup (via Staff Portal)

1. Open http://localhost:3001
2. Go to **Doctors** → Add a doctor (e.g. "Rajesh Kumar", Specialty: "General Medicine")
3. Click **Set Availability** → Add Mon–Fri 09:00–17:00, 20-min slots
4. Visit http://localhost:3000 to test the patient chat flow

## Twilio WhatsApp Setup
1. Create a Twilio account at twilio.com
2. Enable WhatsApp Sandbox under Messaging
3. Add to `.env`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`
4. Set webhook URL in Twilio console: `https://your-domain.com/twilio/webhook`

## Environment Variables (Required)
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | From console.anthropic.com |
| `CLINIC_NAME` | Your clinic name |

## Environment Variables (Optional)
| Variable | Description |
|---|---|
| `TWILIO_*` | For SMS/WhatsApp |
| `RESEND_API_KEY` | For email confirmations |
| `GOOGLE_CLIENT_*` | For Google Calendar sync |

## Project Structure
```
backend/
  main.py              — FastAPI app + scheduler
  config.py            — Settings from .env
  database.py          — SQLAlchemy async engine
  reception/           — AI bot (Claude Haiku)
  appointments/        — Slot engine + DB models
  notifications/       — SMS/email service
  channels/            — web_api + twilio webhooks
  staff/               — Staff portal API
frontend/
  chat-widget/         — Patient-facing React chat
  staff-portal/        — Staff management React app
```
