# 5-minute evaluator demo script

## Preferred demo — real receiver phone

Use this only after `REAL_CALL_SETUP.md` is configured and `/api/telephony/config` returns `real_call_ready: true`.

1. Open the dashboard and say: "This is a Next.js admin dashboard backed by FastAPI and PostgreSQL. Real PSTN and browser fallback are deliberately separate."
2. Add Rahul Kumar / your verified consenting test phone / Product enquiry / Commercial RO System. Show that a normal Indian 10-digit number can be typed manually and is normalized to E.164.
3. Click **Call customer's phone**. Do **not** open or enable the laptop microphone.
4. Show the live monitor moving through queued/ringing/in-progress while the destination mobile rings.
5. Answer the destination phone. The AI greeting should be heard on that phone.
6. Speak on the destination phone: "I need a 500 LPH RO system for drinking water in my hotel."
7. Continue: "Bangalore", "around INR 1 lakh", "within one month", and answer any remaining question.
8. Point out the transcript and agent memory: already-collected facts should not be re-asked.
9. When the call completes, show the stored transcript, structured summary, outcome, lead status and follow-up.
10. Return to the dashboard, show statistics/filters, then open `/docs` to show the REST/webhook API design.

### Explain the real audio path

`receiver phone -> Twilio speech recognition -> FastAPI agent/OpenRouter -> Twilio TTS -> receiver phone`

The dashboard page is only a monitor during a real call. It never captures the laptop microphone.

## Assignment-permitted fallback — browser voice demo

If a free/trial carrier blocks the real outbound flow, say this explicitly and use **Browser voice demo**. The assignment permits this fallback when free/trial telephony is restricted.

1. Click **Browser voice demo**.
2. Enable the microphone in Chrome/Edge.
3. Speak the same qualification answers.
4. Show the identical backend agent memory, transcript, summary and dashboard persistence.

Never describe the browser demo as a PSTN/mobile call.

## Key explanation if they ask “why is this agentic?”

The LLM does not control the entire workflow. Each call has structured state. The engine extracts facts, updates memory, determines which required/optional objectives are still missing, chooses the next action, and only then uses the LLM for extraction/natural phrasing. This prevents repeated questions and keeps the workflow testable and resilient when the AI provider fails.
