# Run me first — Windows

## What works without a telephony account

You need PostgreSQL, Python 3.12+, Node.js/npm, Chrome/Edge, and an OpenRouter key. This runs the full backend/admin/agent/database flow plus the clearly labelled **Browser voice demo**.

## What is additionally required to ring a real phone

A free LLM key cannot place a phone call. To use **Call customer's phone**, configure a supported telephony provider. This build includes Twilio PSTN integration. See `REAL_CALL_SETUP.md` for Account SID/Auth Token/from number + public HTTPS tunnel setup and current trial restrictions.

## Fastest base setup

From the extracted project folder:

```powershell
.\SETUP_WINDOWS.bat
```

Then configure OpenRouter:

```powershell
powershell -ExecutionPolicy Bypass -File .\CONFIGURE_OPENROUTER_WINDOWS.ps1
```

Then start the app:

```powershell
.\START_APP_WINDOWS.bat
```

Open:

- Dashboard: `http://localhost:3000`
- FastAPI Swagger: `http://localhost:8000/docs`
- AI connectivity: `http://localhost:8000/api/ai/test`
- Telephony readiness: `http://localhost:8000/api/telephony/config`

## Minimum backend `.env` for browser fallback

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_calling_agent
FRONTEND_URL=http://localhost:3000
PUBLIC_BACKEND_URL=http://localhost:8000
CALLING_PROVIDER=simulated
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=PASTE_YOUR_KEY_HERE
OPENROUTER_MODEL=openrouter/free
```

## Test browser fallback

1. Open the dashboard.
2. Add Rahul Kumar and manually type `9876543210` or `+919876543210`.
3. Click **Browser voice demo**.
4. Enable the mic and speak naturally.
5. Verify agent memory, transcript, structured summary, outcome and dashboard statistics.

## Test a real receiver phone

Follow `REAL_CALL_SETUP.md`. Once `/api/telephony/config` says `real_call_ready: true`, click **Call customer's phone**. The receiver should answer and speak on their mobile; the laptop microphone is not used in that mode.


## Twilio account tier

For the full custom AI phone flow, use an **upgraded Twilio account** and set:

```env
TWILIO_ACCOUNT_TIER=upgraded
```

On a Twilio trial, the Create Call API only permits Twilio trial sample-call instruction URLs; the application therefore reports the real custom PSTN path as unavailable instead of pretending the trial call is using the agent. Use the Browser Voice Demo on trial, or switch this value to `upgraded` on your upgraded Twilio account.
