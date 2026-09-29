from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.state import AgentState
from ..models import CallEvent, CallSession, ConversationTurn
from .summary_service import SummaryService
from .telephony.twilio_provider import TwilioProvider


LIVE_CALL_STATUSES = {"created", "queued", "initiated", "ringing", "in_progress"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def add_turn(db: Session, call: CallSession, speaker: str, message: str) -> ConversationTurn:
    turn = ConversationTurn(call_id=call.id, speaker=speaker, message=message)
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return turn


def add_event(db: Session, call_id: str, event_type: str, details: dict | None = None) -> CallEvent:
    event = CallEvent(call_id=call_id, event_type=event_type, details=details or {})
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


async def finish_call(db: Session, call: CallSession, reason: str = "completed") -> CallSession:
    if call.ended_at:
        return call
    call.ended_at = utcnow()
    call.status = "completed" if reason in {"completed", "qualified", "ended_by_customer"} else reason
    if call.started_at:
        call.duration_seconds = max(0, int((call.ended_at - as_utc(call.started_at)).total_seconds()))

    state = AgentState.from_dict(call.agent_state)
    turns = db.scalars(select(ConversationTurn).where(ConversationTurn.call_id == call.id).order_by(ConversationTurn.created_at)).all()
    transcript = [{"speaker": t.speaker, "message": t.message} for t in turns]
    summary_service = SummaryService()
    structured, text = await summary_service.build(state, transcript)
    if summary_service.llm.last_error:
        db.add(CallEvent(call_id=call.id, event_type="ai_summary_fallback", details={"message": summary_service.llm.last_error}))
    call.structured_summary = structured
    call.summary_text = text
    call.outcome = structured.get("call_outcome") or reason
    call.lead_status = structured.get("lead_status")
    call.follow_up_required = bool(structured.get("follow_up_required"))
    db.add(call)
    db.add(CallEvent(call_id=call.id, event_type="call_ended", details={"reason": reason}))
    db.commit()
    db.refresh(call)
    return call


async def reconcile_twilio_call(db: Session, call: CallSession) -> CallSession:
    if call.ended_at or call.status not in LIVE_CALL_STATUSES:
        return call
    mode = str((call.agent_state or {}).get("call_mode") or "")
    if mode != "twilio" or not call.provider_call_id:
        return call

    provider_status = await TwilioProvider.get_call_status(call.provider_call_id)
    if not provider_status:
        return call

    normalized = provider_status.lower()
    stored_status = normalized.replace("-", "_")

    if normalized in {"queued", "initiated", "ringing"}:
        if call.status != stored_status:
            call.status = stored_status
            db.commit()
        return call

    if normalized in {"in-progress", "answered"}:
        if call.status != "in_progress":
            call.status = "in_progress"
            db.commit()
        return call

    if normalized in {"no-answer", "busy"}:
        state = AgentState.from_dict(call.agent_state)
        state.status = "no_answer"
        payload = state.to_dict()
        payload["call_mode"] = "twilio"
        call.agent_state = payload
        add_event(db, call.id, "twilio_status_reconciled", {"provider_status": normalized})
        return await finish_call(db, call, "no_answer")

    if normalized in {"failed", "canceled"}:
        state = AgentState.from_dict(call.agent_state)
        state.status = "provider_failure"
        payload = state.to_dict()
        payload["call_mode"] = "twilio"
        call.agent_state = payload
        call.error_code = "provider_failure"
        call.error_message = f"Twilio call status: {normalized}"
        add_event(db, call.id, "twilio_status_reconciled", {"provider_status": normalized})
        return await finish_call(db, call, "failed")

    if normalized == "completed":
        pending_reason = str((call.agent_state or {}).get("pending_end_reason") or "disconnected")
        if pending_reason == "disconnected":
            state = AgentState.from_dict(call.agent_state)
            state.status = "disconnected"
            payload = state.to_dict()
            payload["call_mode"] = "twilio"
            call.agent_state = payload
        add_event(db, call.id, "twilio_status_reconciled", {"provider_status": normalized})
        return await finish_call(db, call, pending_reason)

    return call
