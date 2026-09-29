from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..agent.engine import CallingAgent
from ..agent.state import AgentState
from ..db import SessionLocal
from ..models import CallSession
from ..services.call_service import add_event, add_turn, finish_call

router = APIRouter()


@router.websocket("/ws/calls/{call_id}")
async def call_socket(websocket: WebSocket, call_id: str):
    await websocket.accept()
    db = SessionLocal()
    agent = CallingAgent()
    try:
        call = db.scalar(select(CallSession).where(CallSession.id == call_id).options(selectinload(CallSession.customer), selectinload(CallSession.turns)))
        if not call:
            await websocket.send_json({"type": "error", "message": "Call not found"})
            await websocket.close(code=4404)
            return

        state = AgentState.from_dict(call.agent_state)
        if not call.turns:
            greeting = agent.greeting(state, call.customer.product)
            call.agent_state = greeting.state.to_dict()
            db.commit()
            add_turn(db, call, "ai", greeting.text)
            await websocket.send_json({"type": "agent", "text": greeting.text, "action": greeting.action.value, "state": greeting.state.to_dict()})

        while True:
            payload = await websocket.receive_json()
            message_type = payload.get("type")

            if message_type == "hangup":
                await finish_call(db, call, "ended_by_customer")
                await websocket.send_json({"type": "ended", "reason": "ended_by_customer"})
                await websocket.close()
                return

            if message_type == "event":
                add_event(db, call.id, str(payload.get("event_type", "client_event")), payload.get("details") or {})
                continue

            if message_type != "user_text":
                await websocket.send_json({"type": "error", "message": "Unsupported message type"})
                continue

            user_text = str(payload.get("text", "")).strip()
            add_turn(db, call, "customer", user_text or "[silence]")
            state = AgentState.from_dict(call.agent_state)
            reply = await agent.respond(state, user_text)
            if agent.llm.last_error:
                add_event(db, call.id, "ai_provider_fallback", {"message": agent.llm.last_error})
            call.agent_state = reply.state.to_dict()
            db.commit()
            add_turn(db, call, "ai", reply.text)

            await websocket.send_json({
                "type": "agent",
                "text": reply.text,
                "action": reply.action.value,
                "state": reply.state.to_dict(),
                "extracted": reply.extracted,
                "should_end": reply.should_end,
            })

            if reply.should_end:
                if reply.action.value == "complete":
                    reason = "qualified"
                elif reply.state.status in {"not_interested", "ended_by_customer"}:
                    reason = "ended_by_customer"
                else:
                    reason = reply.state.status
                await finish_call(db, call, reason)
                await websocket.send_json({"type": "ended", "reason": reason})
                await websocket.close()
                return

    except WebSocketDisconnect:
        if 'call' in locals() and call and not call.ended_at:
            add_event(db, call.id, "websocket_disconnected", {})
            await finish_call(db, call, "disconnected")
    except Exception as exc:
        if 'call' in locals() and call:
            call.error_code = "realtime_error"
            call.error_message = str(exc)[:1000]
            db.commit()
            add_event(db, call.id, "realtime_error", {"message": str(exc)[:500]})
            await finish_call(db, call, "failed")
        try:
            await websocket.send_json({"type": "error", "message": "Realtime call error"})
        except Exception:
            pass
    finally:
        db.close()
