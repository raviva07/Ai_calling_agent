from __future__ import annotations

import threading
import time
from urllib.parse import urlparse
from xml.sax.saxutils import escape

import httpx

from ...core.config import get_settings
from .base import ProviderStartResult

settings = get_settings()

TWILIO_TRIAL_SPEECH_URL = "https://webhooks.twilio.com/v1/Voice/Template/voice_speech_recognition"
TWILIO_TERMINAL_STATUSES = {"completed", "busy", "failed", "no-answer", "canceled"}


def twilio_readiness() -> tuple[bool, list[str]]:
    reasons: list[str] = []
    voice_mode = (settings.twilio_voice_mode or "gather").lower()
    account_tier = (settings.twilio_account_tier or "trial").lower()
    if account_tier not in {"trial", "upgraded"}:
        reasons.append("TWILIO_ACCOUNT_TIER must be trial or upgraded")
    if voice_mode not in {"gather", "relay"}:
        reasons.append("TWILIO_VOICE_MODE must be gather or relay")
    if account_tier == "trial" and voice_mode == "relay":
        reasons.append("Twilio trial blocks ConversationRelay; use gather on trial")
    if not settings.twilio_account_sid:
        reasons.append("TWILIO_ACCOUNT_SID is missing")
    if not settings.twilio_auth_token:
        reasons.append("TWILIO_AUTH_TOKEN is missing")
    if not settings.twilio_from_number:
        reasons.append("TWILIO_FROM_NUMBER is missing")

    parsed = urlparse(settings.public_backend_url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        reasons.append("PUBLIC_BACKEND_URL must be a valid public URL")
    elif host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        reasons.append("PUBLIC_BACKEND_URL cannot be localhost for a real phone call; use an HTTPS tunnel")
    elif voice_mode == "relay" and parsed.scheme != "https":
        reasons.append("ConversationRelay requires an HTTPS PUBLIC_BACKEND_URL so Twilio can open a secure WSS connection")
    return (not reasons, reasons)


def _trial_redirect_twiml(answer_url: str) -> str:
    """Trial-safe inline TwiML: redirect an already-connected call to our app.

    The outbound Create Call API on a Twilio trial only accepts Twilio's built-in
    sample Voice URLs. Once the call is actually in progress, we switch it to
    our FastAPI conversation using trial-supported custom TwiML.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Redirect method="POST">{escape(answer_url)}</Redirect>'
        '</Response>'
    )


class TwilioProvider:
    """Twilio Voice REST adapter.

    Trial accounts use Twilio's permitted Speech Recognition bootstrap URL for
    Create Call, then a short status poller redirects the live call into our
    custom FastAPI TwiML. Upgraded accounts use our answer webhook directly.
    """

    def __init__(self) -> None:
        ready, reasons = twilio_readiness()
        if not ready:
            raise RuntimeError("Real calling is not configured: " + "; ".join(reasons))

    def start_call(self, *, call_id: str, phone_number: str) -> ProviderStartResult:
        base = settings.public_backend_url.rstrip("/")
        answer_url = f"{base}/api/telephony/twilio/answer/{call_id}"
        status_url = f"{base}/api/telephony/twilio/status/{call_id}"
        endpoint = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{settings.twilio_account_sid}/Calls.json"
        )
        trial = (settings.twilio_account_tier or "trial").lower() == "trial"
        if trial:
            # Match the request produced by Twilio Console's working trial
            # Speech Recognition test. Do not send custom Url/Method/Timeout
            # parameters here because the trial Create Call endpoint restricts them.
            data = {
                "To": phone_number,
                "From": settings.twilio_from_number or "",
                "Url": TWILIO_TRIAL_SPEECH_URL,
                "StatusCallback": status_url,
            }
        else:
            data = {
                "To": phone_number,
                "From": settings.twilio_from_number or "",
                "Url": answer_url,
                "Method": "POST",
                "StatusCallback": status_url,
                "StatusCallbackMethod": "POST",
                "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
                "Timeout": "30",
            }
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    endpoint,
                    auth=(settings.twilio_account_sid or "", settings.twilio_auth_token or ""),
                    data=data,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:800] if exc.response is not None else str(exc)
            raise RuntimeError(f"Twilio rejected outbound call: {detail}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Twilio outbound call request failed: {exc}") from exc

        sid = str(payload.get("sid") or "").strip()
        if not sid:
            raise RuntimeError("Twilio returned no call SID")
        status = str(payload.get("status") or "queued").lower().replace("-", "_")
        if trial:
            threading.Thread(
                target=self._bootstrap_trial_call,
                args=(sid, answer_url),
                daemon=True,
                name=f"twilio-trial-bootstrap-{call_id[:8]}",
            ).start()
        return ProviderStartResult(provider_call_id=sid, status=status, mode="twilio")

    @staticmethod
    async def get_call_status(call_sid: str) -> str | None:
        """Read the provider's latest call status.

        Twilio normally pushes lifecycle callbacks to our webhook, but a local
        demo tunnel can briefly miss or delay a callback. The dashboard uses
        this as a lightweight reconciliation path so an ended phone call never
        remains visually stuck as active.
        """
        if not call_sid or not settings.twilio_account_sid or not settings.twilio_auth_token:
            return None
        endpoint = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{settings.twilio_account_sid}/Calls/{call_sid}.json"
        )
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    endpoint,
                    auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                )
                response.raise_for_status()
                status = str(response.json().get("status") or "").strip().lower()
                return status or None
        except (httpx.HTTPError, ValueError):
            # Reconciliation is best-effort. The webhook remains the primary
            # source of truth and the UI should continue working if Twilio is
            # temporarily unreachable.
            return None

    def _bootstrap_trial_call(self, call_sid: str, answer_url: str) -> None:
        """Wait until a trial call is in progress, then switch it to our app."""
        endpoint = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{settings.twilio_account_sid}/Calls/{call_sid}.json"
        )
        twiml = _trial_redirect_twiml(answer_url)
        deadline = time.time() + 55
        try:
            with httpx.Client(timeout=15.0) as client:
                while time.time() < deadline:
                    response = client.get(
                        endpoint,
                        auth=(settings.twilio_account_sid or "", settings.twilio_auth_token or ""),
                    )
                    response.raise_for_status()
                    payload = response.json()
                    status = str(payload.get("status") or "").lower()
                    if status == "in-progress":
                        update = client.post(
                            endpoint,
                            auth=(settings.twilio_account_sid or "", settings.twilio_auth_token or ""),
                            data={"Twiml": twiml},
                        )
                        update.raise_for_status()
                        return
                    if status in TWILIO_TERMINAL_STATUSES:
                        return
                    time.sleep(1.0)
        except Exception:
            # The status callback / call record captures the provider outcome.
            # The browser fallback remains available if the trial blocks the live update.
            return
