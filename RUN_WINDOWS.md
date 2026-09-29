# Windows quick run

For the easiest path use the included scripts from the project root.

## First time only

```powershell
.\SETUP_WINDOWS.bat
powershell -ExecutionPolicy Bypass -File .\CONFIGURE_OPENROUTER_WINDOWS.ps1
```

The second command asks for your OpenRouter key with hidden input and writes it to `backend/.env` (Git-ignored). The default AI model is `openrouter/free`.

## Every time you want to run the app

```powershell
.\START_APP_WINDOWS.bat
```

Then open:

- `http://localhost:3000` — admin dashboard
- `http://localhost:8000/docs` — FastAPI Swagger
- `http://localhost:8000/api/ai/test` — OpenRouter connectivity check

Use Chrome or Edge for microphone speech recognition. Keep `CALLING_PROVIDER=simulated`; Twilio keys are **not required** for the assignment browser voice demo.

If you do not use Docker, create PostgreSQL database `ai_calling_agent` locally and ensure `DATABASE_URL` in `backend/.env` matches your username/password/port.

See `RUN_ME_FIRST.md` for the full click-by-click test flow.


## Twilio account tier

For the full custom AI phone flow, use an **upgraded Twilio account** and set:

```env
TWILIO_ACCOUNT_TIER=upgraded
```

On a Twilio trial, the Create Call API only permits Twilio trial sample-call instruction URLs; the application therefore reports the real custom PSTN path as unavailable instead of pretending the trial call is using the agent. Use the Browser Voice Demo on trial, or switch this value to `upgraded` on your upgraded Twilio account.
