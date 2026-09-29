from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlparse
from xml.sax.saxutils import escape, quoteattr

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..agent.engine import CallingAgent
from ..agent.state import AgentState
from ..core.config import get_settings
from ..db import SessionLocal, get_db
from ..models import CallSession
from ..services.call_service import add_event, add_turn, finish_call

router = APIRouter(prefix="/api/telephony/twilio")
settings = get_settings()


def _load_call(db: Session, call_id: str) -> CallSession:
    call = db.scalar(
        select(CallSession)
        .where(CallSession.id == call_id)
        .options(selectinload(CallSession.customer), selectinload(CallSession.turns))
    )
    if not call:
        raise HTTPException(404, "Call not found")
    return call


def _xml(value: str) -> Response:
    return Response(content=value, media_type="application/xml")


def _public_http_url(path: str) -> str:
    return f"{settings.public_backend_url.rstrip('/')}{path}"


def _public_ws_url(path: str) -> str:
    parsed = urlparse(settings.public_backend_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}{path}"


def _expected_twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    # Twilio webhook signature: URL + sorted POST parameter names/values, HMAC-SHA1, base64.
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


async def _validate_http_signature(request: Request) -> None:
    if not settings.twilio_validate_signature:
        return
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature or not settings.twilio_auth_token:
        raise HTTPException(403, "Missing Twilio webhook signature")
    form = await request.form()
    public_url = _public_http_url(request.url.path)
    params = {str(k): str(v) for k, v in form.items()}
    expected = _expected_twilio_signature(public_url, params, settings.twilio_auth_token)
    if not secrets.compare_digest(expected, signature):
        raise HTTPException(403, "Invalid Twilio webhook signature")


def _relay_signature_valid(websocket: WebSocket, call_id: str) -> bool:
    if not settings.twilio_validate_signature:
        return True
    signature = websocket.headers.get("x-twilio-signature", "")
    if not signature or not settings.twilio_auth_token:
        return False
    public_url = _public_ws_url(f"/api/telephony/twilio/relay/{call_id}")
    expected = _expected_twilio_signature(public_url, {}, settings.twilio_auth_token)
    return secrets.compare_digest(expected, signature)


def _with_mode(state: AgentState, **extras: object) -> dict:
    payload = state.to_dict()
    payload["call_mode"] = "twilio"
    payload.update(extras)
    return payload


def _reason_for_reply(reply) -> str:
    if reply.action.value == "complete":
        return "qualified"
    if reply.state.status in {"not_interested", "ended_by_customer"}:
        return "ended_by_customer"
    return reply.state.status or "completed"


# -----------------------------
# Twilio ConversationRelay mode
# -----------------------------

def _conversation_relay_twiml(greeting: str, call_id: str) -> str:
    relay_ws = _public_ws_url(f"/api/telephony/twilio/relay/{call_id}")
    action_url = _public_http_url(f"/api/telephony/twilio/relay-ended/{call_id}")
    lang = settings.twilio_relay_language or "en-IN"
    # Raw XML keeps the app compatible even if a locally installed Twilio SDK predates
    # ConversationRelay. ConversationRelay itself handles STT, TTS, barge-in and turn taking.
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Connect action={quoteattr(action_url)} method="POST">'
        f'<ConversationRelay url={quoteattr(relay_ws)} '
        f'welcomeGreeting={quoteattr(greeting)} '
        f'language={quoteattr(lang)} '
        'welcomeGreetingInterruptible="speech" '
        'interruptible="speech" '
        'interruptSensitivity="medium" '
        'reportInputDuringAgentSpeech="speech" '
        'ignoreBackchannel="true" '
        'preemptible="true" '
        'speechTimeout="800" '
        'events="speaker-events tokens-played" />'
        '</Connect>'
        '</Response>'
    )


@router.websocket("/relay/{call_id}")
async def conversation_relay_socket(websocket: WebSocket, call_id: str):
    if not _relay_signature_valid(websocket, call_id):
        await websocket.close(code=1008, reason="Invalid Twilio signature")
        return

    await websocket.accept()
    db = SessionLocal()
    try:
        call = _load_call(db, call_id)
        agent = CallingAgent()
        add_event(db, call.id, "conversation_relay_connected", {})

        while True:
            message = await websocket.receive_json()
            msg_type = str(message.get("type", ""))

            if msg_type == "setup":
                call.provider_call_id = message.get("callSid") or call.provider_call_id
                call.status = "in_progress"
                current = dict(call.agent_state or {})
                current["call_mode"] = "twilio"
                current["relay_session_id"] = message.get("sessionId")
                call.agent_state = current
                db.commit()
                add_event(db, call.id, "conversation_relay_setup", {
                    "session_id": message.get("sessionId"),
                    "call_sid": message.get("callSid"),
                    "call_type": message.get("callType"),
                })
                continue

            if msg_type == "interrupt":
                add_event(db, call.id, "customer_interrupted_ai", {
                    "source": "twilio_conversation_relay",
                    "utterance_until_interrupt": message.get("utteranceUntilInterrupt"),
                    "duration_ms": message.get("durationUntilInterruptMs"),
                })
                continue

            if msg_type == "error":
                add_event(db, call.id, "conversation_relay_error", {
                    "description": str(message.get("description", "Unknown ConversationRelay error"))[:1000]
                })
                continue

            if msg_type != "prompt":
                # Speaker/token/debug events are useful operational telemetry but not customer turns.
                if msg_type:
                    add_event(db, call.id, f"conversation_relay_{msg_type}"[:80], {
                        k: v for k, v in message.items() if k != "type"
                    })
                continue

            # ConversationRelay may emit partial prompts; act only on a final utterance.
            if message.get("last") is False:
                continue

            customer_text = str(message.get("voicePrompt") or "").strip()
            add_turn(db, call, "customer", customer_text or "[silence]")
            state = AgentState.from_dict(call.agent_state)
            reply = await agent.respond(state, customer_text)
            if agent.llm.last_error:
                add_event(db, call.id, "ai_provider_fallback", {"message": agent.llm.last_error})

            extras: dict[str, object] = {"relay_session_id": (call.agent_state or {}).get("relay_session_id")}
            if reply.should_end:
                extras["pending_end_reason"] = _reason_for_reply(reply)
            call.agent_state = _with_mode(reply.state, **extras)
            db.commit()
            add_turn(db, call, "ai", reply.text)

            await websocket.send_json({
                "type": "text",
                "token": reply.text,
                "last": True,
                "lang": settings.twilio_relay_language or "en-IN",
                "interruptible": True,
                "preemptible": True,
            })

            if reply.should_end:
                # Give the final sentence a moment to start/play before handing the session back.
                # Final persistence is completed by relay-ended/status callback, so the real phone
                # lifecycle—not the browser—decides when the call actually ended.
                await asyncio.sleep(min(4.0, max(1.5, len(reply.text) / 35.0)))
                await websocket.send_json({
                    "type": "end",
                    "handoffData": json.dumps({"reason": _reason_for_reply(reply)})
                })

    except WebSocketDisconnect:
        try:
            add_event(db, call_id, "conversation_relay_disconnected", {})
        except Exception:
            pass
    except Exception as exc:
        try:
            add_event(db, call_id, "conversation_relay_backend_error", {"message": str(exc)[:1000]})
        except Exception:
            pass
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        db.close()


@router.post("/relay-ended/{call_id}")
async def relay_ended(
    call_id: str,
    request: Request,
    HandoffData: str = Form(default=""),
    SessionStatus: str = Form(default=""),
    db: Session = Depends(get_db),
):
    await _validate_http_signature(request)
    call = _load_call(db, call_id)
    reason = str((call.agent_state or {}).get("pending_end_reason") or "disconnected")
    if HandoffData:
        try:
            reason = json.loads(HandoffData).get("reason") or reason
        except Exception:
            pass
    add_event(db, call.id, "conversation_relay_ended", {
        "session_status": SessionStatus or None,
        "reason": reason,
    })
    if not call.ended_at:
        await finish_call(db, call, reason)
    return _xml(_hangup())


# -----------------------------
# Gather fallback mode
# -----------------------------

def _gather(prompt: str, call_id: str) -> str:
    action_url = _public_http_url(f"/api/telephony/twilio/respond/{call_id}")
    silence_url = _public_http_url(f"/api/telephony/twilio/silence/{call_id}")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Gather input="speech" action={quoteattr(action_url)} method="POST" '
        'speechTimeout="auto" timeout="6" language="en-IN" actionOnEmptyResult="true">'
        f'<Say voice="Polly.Aditi" language="en-IN">{escape(prompt)}</Say>'
        '</Gather>'
        f'<Redirect method="POST">{escape(silence_url)}</Redirect>'
        '</Response>'
    )


def _say_and_hangup(text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Say voice="Polly.Aditi" language="en-IN">{escape(text)}</Say>'
        '<Hangup/>'
        '</Response>'
    )


def _hangup() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>'


@router.post("/answer/{call_id}")
async def answer(call_id: str, request: Request, db: Session = Depends(get_db)):
    await _validate_http_signature(request)
    call = _load_call(db, call_id)

    if call.turns and call.turns[0].speaker == "ai":
        greeting_text = call.turns[0].message
    else:
        agent = CallingAgent()
        state = AgentState.from_dict(call.agent_state)
        greeting = agent.greeting(state, call.customer.product)
        greeting_text = greeting.text
        call.agent_state = _with_mode(greeting.state)
        db.commit()
        add_turn(db, call, "ai", greeting_text)

    call.status = "in_progress"
    db.commit()
    add_event(db, call.id, "twilio_answered", {"voice_mode": settings.twilio_voice_mode})

    if settings.twilio_voice_mode.lower() == "gather":
        return _xml(_gather(greeting_text, call.id))
    return _xml(_conversation_relay_twiml(greeting_text, call.id))


@router.post("/respond/{call_id}")
async def respond(
    call_id: str,
    request: Request,
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default=""),
    db: Session = Depends(get_db),
):
    await _validate_http_signature(request)
    call = _load_call(db, call_id)
    agent = CallingAgent()
    add_event(db, call.id, "twilio_speech_result", {"confidence": Confidence or None})
    add_turn(db, call, "customer", SpeechResult or "[silence]")
    state = AgentState.from_dict(call.agent_state)
    reply = await agent.respond(state, SpeechResult)
    if agent.llm.last_error:
        add_event(db, call.id, "ai_provider_fallback", {"message": agent.llm.last_error})
    call.agent_state = _with_mode(reply.state)
    db.commit()
    add_turn(db, call, "ai", reply.text)

    if reply.should_end:
        await finish_call(db, call, _reason_for_reply(reply))
        return _xml(_say_and_hangup(reply.text))
    return _xml(_gather(reply.text, call.id))


@router.post("/silence/{call_id}")
async def silence(call_id: str, request: Request, db: Session = Depends(get_db)):
    await _validate_http_signature(request)
    call = _load_call(db, call_id)
    agent = CallingAgent()
    add_turn(db, call, "customer", "[silence]")
    state = AgentState.from_dict(call.agent_state)
    reply = await agent.respond(state, "")
    if agent.llm.last_error:
        add_event(db, call.id, "ai_provider_fallback", {"message": agent.llm.last_error})
    call.agent_state = _with_mode(reply.state)
    db.commit()
    add_turn(db, call, "ai", reply.text)
    if reply.should_end:
        await finish_call(db, call, "no_response")
        return _xml(_say_and_hangup(reply.text))
    return _xml(_gather(reply.text, call.id))


@router.post("/status/{call_id}")
async def status(
    call_id: str,
    request: Request,
    CallStatus: str = Form(default="unknown"),
    CallSid: str = Form(default=""),
    CallDuration: str = Form(default=""),
    db: Session = Depends(get_db),
):
    await _validate_http_signature(request)
    call = _load_call(db, call_id)
    call.provider_call_id = CallSid or call.provider_call_id
    normalized = CallStatus.lower()
    add_event(db, call.id, f"twilio_{normalized}"[:80], {"provider_call_id": CallSid})

    # Twilio callbacks can occasionally arrive out of order. Once our record is
    # terminal, never let a later callback revive it. If Twilio supplies its
    # final billed/call duration after our own finish logic ran, keep that more
    # authoritative duration without changing the already-terminal status.
    if call.ended_at:
        if CallDuration.isdigit() and normalized in {"completed", "busy", "failed", "no-answer", "canceled"}:
            call.duration_seconds = int(CallDuration)
        db.commit()
        return {"ok": True}

    if normalized in {"no-answer", "busy"}:
        state = AgentState.from_dict(call.agent_state)
        state.status = "no_answer"
        call.agent_state = _with_mode(state)
        await finish_call(db, call, "no_answer")
        if CallDuration.isdigit():
            call.duration_seconds = int(CallDuration)
            db.commit()
        return {"ok": True}

    if normalized in {"failed", "canceled"}:
        state = AgentState.from_dict(call.agent_state)
        state.status = "provider_failure"
        call.agent_state = _with_mode(state)
        call.error_code = "provider_failure"
        call.error_message = f"Twilio call status: {normalized}"
        await finish_call(db, call, "failed")
        if CallDuration.isdigit():
            call.duration_seconds = int(CallDuration)
            db.commit()
        return {"ok": True}

    if normalized == "ringing":
        call.status = "ringing"
    elif normalized in {"in-progress", "answered"}:
        call.status = "in_progress"
    elif normalized == "completed" and not call.ended_at:
        pending_reason = str((call.agent_state or {}).get("pending_end_reason") or "disconnected")
        if pending_reason == "disconnected":
            state = AgentState.from_dict(call.agent_state)
            state.status = "disconnected"
            call.agent_state = _with_mode(state)
        await finish_call(db, call, pending_reason)
        if CallDuration.isdigit():
            call.duration_seconds = int(CallDuration)
            db.commit()
        return {"ok": True}
    db.commit()
    return {"ok": True}
