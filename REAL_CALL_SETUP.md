# Real phone call setup — Twilio PSTN

The app has two deliberately separate call modes:

1. **Call customer's phone** — a real outbound PSTN call through Twilio. The receiver speaks on the destination phone. The laptop microphone is **not** used.
2. **Browser voice demo** — the assignment-permitted fallback. It uses the laptop browser microphone and is clearly labelled as a simulation/demo.

## Real-call architecture

The default real-phone mode is the simpler Twilio `<Gather input="speech">` loop because `<Gather>`, `<Say>`, and their action callbacks are supported building blocks for speech collection/TTS and are substantially more trial-friendly than ConversationRelay.

`Next.js -> FastAPI -> Twilio Calls API -> customer mobile -> Twilio <Gather> STT -> FastAPI agent/OpenRouter -> Twilio <Say> TTS -> customer mobile`

The FastAPI application owns the actual agent memory, missing-field policy, OpenRouter call, transcript persistence, summary, outcome and follow-up state.

An **optional `relay` mode** is also implemented for accounts that have ConversationRelay enabled. It uses a secure WebSocket and supports lower-latency streaming plus explicit interruption events. Current Twilio trial documentation lists `<ConversationRelay>` as blocked during trial, so do not select `relay` for a normal free trial.

## 1. Create / use a Twilio trial

Create a Twilio trial account and verify the phone number you will use as the interview recipient. Trial Voice restricts calls to verified recipient numbers.

Collect from the Twilio Console:

- Account SID (`AC...`)
- Auth Token
- Voice-capable trial/from number shown by Twilio

**Important:** Twilio trial capabilities and outbound restrictions can vary by account/country. If Twilio prevents a custom outbound AI flow in the trial, use the browser fallback for the assignment demo or use an enabled/paid Twilio account. The application will never disguise the browser fallback as a PSTN call.

## 2. Expose FastAPI publicly

Twilio cannot call `http://localhost:8000`. Keep FastAPI running on port 8000 and expose it through HTTPS. With Cloudflare Quick Tunnel:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Copy the generated URL, for example:

```text
https://example-random.trycloudflare.com
```

Keep that terminal running. Quick-tunnel URLs change when restarted.

## 3. Configure `backend/.env`

Keep your current PostgreSQL and OpenRouter settings and add/update:

```env
PUBLIC_BACKEND_URL=https://example-random.trycloudflare.com

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=your_twilio_voice_number

# Default real-phone mode: Twilio speech Gather + Say loop
TWILIO_VOICE_MODE=gather
TWILIO_RELAY_LANGUAGE=en-IN

# Recommended when the public URL above is stable
TWILIO_VALIDATE_SIGNATURE=true
```

`CALLING_PROVIDER` may remain `simulated`; the dashboard selects browser vs Twilio explicitly for each call.

If signature validation causes a tunnel-only test problem, temporarily set `TWILIO_VALIDATE_SIGNATURE=false`, restart FastAPI, test, and restore it before deployment. Never expose a production webhook without validation.

## 4. Restart FastAPI

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Keep the Cloudflare tunnel running too.

## 5. Verify readiness

Open:

```text
http://localhost:8000/api/telephony/config
```

You need:

```json
{
  "browser_demo_ready": true,
  "real_call_provider": "twilio",
  "real_call_ready": true,
  "twilio_voice_mode": "gather"
}
```

If `real_call_ready` is false, the `reasons` array tells you exactly what is missing.

## 6. Place a real test call

1. Open `http://localhost:3000`.
2. Add the recipient. The phone field accepts `+919876543210` or an Indian 10-digit mobile number and normalizes it to E.164.
3. For a Twilio trial, use a destination verified in your Twilio account.
4. Click **Call customer's phone** — not **Browser voice demo**.
5. The monitoring page shows `queued -> ringing -> in progress` and refreshes automatically.
6. Answer the destination phone. The AI prompt is played **on that phone**.
7. Speak on the destination phone. Twilio converts the receiver's speech to text and posts `SpeechResult` to FastAPI.
8. FastAPI updates the same agent state, calls OpenRouter when available, stores the turn, and returns the next TwiML prompt.
9. Twilio speaks the AI response back into the same phone call and gathers the next receiver response.
10. At completion the call is hung up and PostgreSQL contains the full transcript, structured summary, outcome, lead status and follow-up state.

## Optional upgraded mode — ConversationRelay

If your Twilio account has ConversationRelay enabled, set:

```env
TWILIO_VOICE_MODE=relay
```

This switches the answered PSTN call to the implemented `/api/telephony/twilio/relay/{call_id}` WebSocket path, which receives final `prompt` messages, sends `text` messages back for TTS and records `interrupt` events. `PUBLIC_BACKEND_URL` must be HTTPS so the derived WebSocket URL is `wss://`.

## India-specific reality

Twilio currently documents that outbound calls to India must originate from international (non-Indian) Twilio numbers and that commercial calls require appropriate recipient consent. Trial geographic/recipient restrictions may further constrain what your specific account can dial. Test only a number you own or have permission to call.

## Why browser mode remains in the project

A free LLM key cannot ring a phone. OpenRouter provides GenAI only; telephony must come from a carrier/voice API. The assignment explicitly permits a browser/WebRTC/simulated two-way implementation if free/trial provider limitations prevent real outbound calling. The dashboard therefore keeps this fallback but labels it honestly.


## Twilio account tier

For the full custom AI phone flow, use an **upgraded Twilio account** and set:

```env
TWILIO_ACCOUNT_TIER=upgraded
```

On a Twilio trial, the Create Call API only permits Twilio trial sample-call instruction URLs; the application therefore reports the real custom PSTN path as unavailable instead of pretending the trial call is using the agent. Use the Browser Voice Demo on trial, or switch this value to `upgraded` on your upgraded Twilio account.
