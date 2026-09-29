# Submission checklist

Required deliverables:

- GitHub repository with `/backend`, `/frontend`, `/database`, `README.md`, `.env.example`.
- Working two-way voice demo: preferred real PSTN path when a carrier account permits it; clearly labelled browser fallback when free/trial restrictions block PSTN.
- Admin dashboard: customer management, explicit real/browser call actions, call history, live status, transcript, summary, outcome, lead status, follow-up, statistics and filters.
- Documentation: architecture, setup, schema, APIs, AI workflow, calling workflow, free-tier limitations and future improvements.
- No actual keys or secrets committed.

Before sending:

- Run `pytest -q` in `backend` (packaged source currently: **25/25 passing**).
- Run `npm install` and `npm run build` in `frontend` on the submission laptop.
- Open `http://localhost:8000/api/ai/test` and confirm OpenRouter is configured.
- Open `http://localhost:8000/api/telephony/config`; if `real_call_ready` is true, make one real test call to a verified/consenting number.
- If the carrier trial blocks custom outbound AI calling, demonstrate **Browser voice demo** and state the limitation exactly as allowed by the assignment.
- Verify a finished call stores transcript + structured summary + outcome + lead status + follow-up.
- Record a 3–5 minute backup demo video.
- Push the repository publicly or grant recruiter access.
- Verify README commands from a clean terminal.
