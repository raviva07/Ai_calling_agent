# Final QA audit — real-call correction

## What was corrected after live user testing

- Fixed the phone field so numbers can be manually typed normally (`type=tel`) and added India-friendly normalization from 10 digits to `+91...`.
- Removed the misleading single "Start call" behavior.
- Added two explicit modes: **Call customer's phone** (real PSTN) and **Browser voice demo** (laptop mic fallback).
- A real PSTN call never routes to the browser microphone page; it opens a monitoring/details screen instead.
- Added telephony readiness endpoint so the real button is disabled until carrier credentials and a public callback URL are genuinely configured.
- Added real Twilio outbound Calls API integration using `httpx` (no Twilio Python SDK dependency).
- Default real voice loop uses Twilio speech `<Gather>` + `<Say>`: receiver speech becomes `SpeechResult`, goes through the FastAPI agent/OpenRouter, is persisted, and the next AI response is spoken back into the receiver call.
- Preserved optional ConversationRelay/WebSocket mode for Twilio accounts where that product is enabled; it is not presented as a normal free-trial feature.
- Added/retained provider status handling for initiated/ringing/answered/completed/no-answer/busy/failed/canceled.
- Real monitor auto-refreshes status and transcript and clearly says the laptop microphone is not being used.

## Verification performed in this build

- Backend automated tests: **25/25 PASS**.
- Python source compilation: PASS.
- Route-level API smoke test: PASS.
  - customer creation: HTTP 201
  - manually entered Indian number normalized to `+919876543210`
  - call session creation: PASS
  - Twilio answer webhook: HTTP 200 `application/xml`
  - generated TwiML contains speech `<Gather>`, backend response callback, TTS `<Say>`, and silence handling
  - telephony config endpoint correctly reports `real_call_ready: false` when real credentials are absent instead of pretending to call
- Provider unit test verifies the actual destination number is sent as Twilio `To`, the configured carrier number as `From`, and answer/status callback URLs are supplied.
- No Twilio Python SDK is required at runtime.

## External checks that cannot be truthfully completed without the user's carrier account

A physical PSTN call cannot be executed in this build environment because there are no user Twilio credentials, verified recipient, carrier-assigned from number, or public tunnel bound to the user's account. The app therefore does not claim such a call was physically placed here.

Current Twilio trial documentation also restricts trial recipients/geography and blocks `<ConversationRelay>` during trial. The project defaults to the simpler Gather/Say path and documents that the trial Calls API may still restrict a custom autonomous outbound flow. The browser fallback remains because the assignment explicitly permits it when free/trial telephony is restricted.

## Frontend verification note

The revised frontend separates real/browser actions and the real-call monitor at source level. A full `npm run build` should be run on the submission laptop after extracting this ZIP. No frontend package dependency was added by the real-call correction.
