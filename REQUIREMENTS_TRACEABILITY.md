# Assignment requirements traceability

| Requirement | Implementation |
|---|---|
| Admin creates campaign/contact | Dashboard form in `frontend/app/page.tsx`; `POST /api/customers` |
| Admin starts call | Separate **Call customer’s phone** and **Browser voice demo** actions; `POST /api/calls/start` with explicit mode |
| Automatic outbound calling | Explicit real Twilio `calls.create` route plus separate browser fallback; real button is disabled until telephony is configured |
| Two-way voice | Real PSTN: receiver phone → Twilio speech `<Gather>` → FastAPI agent/OpenRouter → Twilio `<Say>` → receiver phone. Separate browser fallback uses SpeechRecognition/WebSocket/speechSynthesis |
| Agentic AI | `backend/app/agent/state.py` + `engine.py`: structured memory, missing-slot policy, explicit actions |
| Context | Persistent `agent_state` JSON; asked/completed fields prevent repeated questions |
| Conversation storage | `conversation_turns` table; saved after every customer/AI turn |
| AI call summary | `SummaryService`; OpenRouter JSON summary with deterministic fallback |
| Admin statistics | `GET /api/dashboard`; six required metrics shown on dashboard |
| Call list/details | Dashboard history + `/calls/[id]` transcript/summary/detail view |
| Search/filtering | Dashboard UI + API support customer, date, call status, lead status, follow-up and outcome filters |
| No answer | Twilio status webhook finalizes no-answer/busy with stored summary, outcome and follow-up state |
| Disconnect | Browser WebSocket disconnect event + Twilio status callbacks; optional ConversationRelay completion callback when relay mode is enabled |
| Speech failure | Browser error event stored; typed fallback remains available |
| AI/API failure | LLM adapter falls back to deterministic behavior and records fallback events |
| Invalid phone | Pydantic phone validation (HTTP 422) |
| Provider failure | Start failure stored in call + event |
| Silence | One reprompt; second silence gracefully terminates |
| Customer interrupts AI | Default Twilio nested speech `<Gather>` accepts speech during prompts; optional ConversationRelay mode records explicit `interrupt` events; browser fallback records Interrupt & talk |
| Free/trial path | Browser fallback needs no telephony subscription. Twilio `<Gather>`/`<Say>` real-call code is included, while current trial recipient/geographic/outbound restrictions and blocked ConversationRelay are documented honestly |
| Documentation | README: setup, architecture, API, DB schema, AI/calling workflows, limitations, future improvements |
| Required source structure | `/backend`, `/frontend`, `/database`, `README.md`, `.env.example` |
| Secrets | `.gitignore` excludes secrets; `.env.example` contains placeholders only |
