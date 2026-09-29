from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..agent.engine import CallingAgent
from ..agent.llm import LLMClient
from ..db import get_db
from ..core.config import get_settings
from ..models import CallEvent, CallSession, Customer
from ..schemas import CallEnd, CallEventIn, CallOut, CallStart, CustomerCreate, CustomerOut, DashboardStats
from ..services.call_service import LIVE_CALL_STATUSES, add_event, finish_call, reconcile_twilio_call
from ..services.telephony.factory import get_telephony_provider
from ..services.telephony.twilio_provider import twilio_readiness

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]


def call_to_out(call: CallSession) -> CallOut:
    return CallOut(
        id=call.id,
        customer_id=call.customer_id,
        customer_name=call.customer.name,
        phone_number=call.phone_number,
        status=call.status,
        outcome=call.outcome,
        lead_status=call.lead_status,
        follow_up_required=call.follow_up_required,
        direction=call.direction,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        provider_call_id=call.provider_call_id,
        agent_state=call.agent_state or {},
        structured_summary=call.structured_summary,
        summary_text=call.summary_text,
        error_code=call.error_code,
        error_message=call.error_message,
        created_at=call.created_at,
        turns=call.turns,
    )


@router.get("/health")
def health():
    llm = LLMClient()
    return {
        "status": "ok",
        "ai_provider": llm.provider_name,
        "ai_model": llm.model,
        "ai_configured": llm.enabled,
        "calling_provider": get_settings().calling_provider,
    }


@router.get("/ai/test")
async def test_ai_provider():
    """Small evaluator-friendly connectivity check. Never returns or logs the API key."""
    return await LLMClient().test_connection()


@router.get("/telephony/config")
def telephony_config():
    settings = get_settings()
    ready, reasons = twilio_readiness()
    return {
        "browser_demo_ready": True,
        "real_call_provider": "twilio",
        "real_call_ready": ready,
        "reasons": reasons,
        "public_backend_url": settings.public_backend_url,
        "twilio_from_number_configured": bool(settings.twilio_from_number),
        "twilio_voice_mode": settings.twilio_voice_mode,
        "twilio_account_tier": settings.twilio_account_tier,
        "twilio_signature_validation": settings.twilio_validate_signature,
    }


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Db):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Db):
    return db.scalars(select(Customer).order_by(Customer.created_at.desc())).all()


@router.post("/calls/start", response_model=CallOut, status_code=201)
def start_call(payload: CallStart, db: Db):
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    agent = CallingAgent()
    state = agent.initial_state(customer.name, customer.company_name, customer.purpose)
    state_payload = state.to_dict()
    state_payload["call_mode"] = payload.mode
    call = CallSession(
        customer_id=customer.id,
        phone_number=customer.phone_number,
        status="created",
        started_at=datetime.now(timezone.utc),
        agent_state=state_payload,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    try:
        result = get_telephony_provider(payload.mode).start_call(call_id=call.id, phone_number=call.phone_number)
        call.provider_call_id = result.provider_call_id
        call.status = result.status
        db.add(CallEvent(call_id=call.id, event_type="call_started", details={"mode": result.mode}))
        db.commit()
    except Exception as exc:
        call.status = "failed"
        call.error_code = "provider_start_failed"
        call.error_message = str(exc)[:1000]
        db.add(CallEvent(call_id=call.id, event_type="provider_failure", details={"message": str(exc)[:500]}))
        db.commit()

    call = db.scalar(select(CallSession).where(CallSession.id == call.id).options(selectinload(CallSession.customer), selectinload(CallSession.turns)))
    return call_to_out(call)


@router.get("/calls", response_model=list[CallOut])
async def list_calls(
    db: Db,
    customer: str | None = None,
    status: str | None = None,
    lead_status: str | None = None,
    outcome: str | None = None,
    follow_up_required: bool | None = None,
    call_date: date | None = Query(default=None, alias="date"),
):
    stmt = select(CallSession).join(CallSession.customer).options(selectinload(CallSession.customer), selectinload(CallSession.turns)).order_by(CallSession.created_at.desc())
    if customer:
        stmt = stmt.where(Customer.name.ilike(f"%{customer}%"))
    if status:
        stmt = stmt.where(CallSession.status == status)
    if lead_status:
        stmt = stmt.where(CallSession.lead_status == lead_status)
    if outcome:
        stmt = stmt.where(CallSession.outcome.ilike(f"%{outcome}%"))
    if follow_up_required is not None:
        stmt = stmt.where(CallSession.follow_up_required == follow_up_required)
    if call_date:
        start = datetime.combine(call_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(call_date, time.max, tzinfo=timezone.utc)
        stmt = stmt.where(CallSession.created_at.between(start, end))
    calls = db.scalars(stmt).unique().all()
    for call in calls[:10]:
        if call.status in LIVE_CALL_STATUSES and not call.ended_at:
            await reconcile_twilio_call(db, call)
    return [call_to_out(call) for call in calls]


@router.get("/calls/{call_id}", response_model=CallOut)
async def get_call(call_id: str, db: Db):
    call = db.scalar(select(CallSession).where(CallSession.id == call_id).options(selectinload(CallSession.customer), selectinload(CallSession.turns)))
    if not call:
        raise HTTPException(404, "Call not found")
    await reconcile_twilio_call(db, call)
    return call_to_out(call)


@router.post("/calls/{call_id}/end", response_model=CallOut)
async def end_call(call_id: str, payload: CallEnd, db: Db):
    call = db.scalar(select(CallSession).where(CallSession.id == call_id).options(selectinload(CallSession.customer), selectinload(CallSession.turns)))
    if not call:
        raise HTTPException(404, "Call not found")
    await finish_call(db, call, payload.reason)
    return call_to_out(call)


@router.post("/calls/{call_id}/events", status_code=201)
def record_event(call_id: str, payload: CallEventIn, db: Db):
    if not db.get(CallSession, call_id):
        raise HTTPException(404, "Call not found")
    return {"id": add_event(db, call_id, payload.event_type, payload.details).id}


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Db):
    total = db.scalar(select(func.count(CallSession.id))) or 0
    active = db.scalar(
        select(func.count(CallSession.id)).where(
            CallSession.status.in_(LIVE_CALL_STATUSES),
            CallSession.ended_at.is_(None),
        )
    ) or 0
    completed = db.scalar(select(func.count(CallSession.id)).where(CallSession.status == "completed")) or 0
    failed = db.scalar(select(func.count(CallSession.id)).where(CallSession.status.in_(["failed", "no_answer", "disconnected", "no_response"]))) or 0
    interested = db.scalar(select(func.count(CallSession.id)).where(CallSession.lead_status == "Interested")) or 0
    followups = db.scalar(select(func.count(CallSession.id)).where(CallSession.follow_up_required.is_(True))) or 0
    avg_duration = db.scalar(select(func.avg(CallSession.duration_seconds)).where(CallSession.duration_seconds > 0)) or 0
    return DashboardStats(
        total_calls=total,
        active_calls=active,
        completed_calls=completed,
        failed_calls=failed,
        interested_leads=interested,
        follow_ups_required=followups,
        average_call_duration_seconds=round(float(avg_duration), 1),
    )
