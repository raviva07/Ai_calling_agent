# Upgraded Twilio Account Setup

Use this project with an upgraded/paid Twilio account for the real custom AI phone flow.

## 1. backend/.env

Set:

```env
CALLING_PROVIDER=twilio
TWILIO_ACCOUNT_TIER=upgraded
TWILIO_ACCOUNT_SID=YOUR_UPGRADED_ACCOUNT_SID
TWILIO_AUTH_TOKEN=YOUR_UPGRADED_AUTH_TOKEN
TWILIO_FROM_NUMBER=YOUR_TWILIO_VOICE_NUMBER
TWILIO_VOICE_MODE=gather
TWILIO_VALIDATE_SIGNATURE=false
PUBLIC_BACKEND_URL=https://YOUR-PUBLIC-HTTPS-URL
```

Keep your existing OpenRouter and PostgreSQL settings.

## 2. Public backend URL

Run FastAPI locally on port 8000 and expose it with HTTPS, for example:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Copy the `https://...trycloudflare.com` URL into `PUBLIC_BACKEND_URL`.

## 3. Verify readiness

Open:

`http://localhost:8000/api/telephony/config`

You want:

```json
"real_call_ready": true
```

and:

```json
"twilio_account_tier": "upgraded"
```

## 4. Test

Create a customer with a real E.164 phone number, then click:

**Call customer's phone**

The browser microphone is NOT used for this mode.

Call path:

Customer phone -> Twilio -> FastAPI `/answer/{call_id}` -> Twilio `<Gather speech>` -> FastAPI `/respond/{call_id}` -> Agent/OpenRouter -> Twilio `<Say>` -> customer phone.

## 5. Trial account

Do not set `TWILIO_ACCOUNT_TIER=upgraded` on a trial account. The app will intentionally keep the custom PSTN button unavailable and direct you to the Browser Voice Demo, because Twilio trial Create Call restrictions require an approved Twilio bootstrap URL, so the project switches the live call into custom Gather/Say TwiML after it is connected.
