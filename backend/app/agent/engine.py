from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .llm import LLMClient
from .state import AgentState, FIELD_ORDER, QUESTIONS, REQUIRED_FIELDS, Action


END_PATTERNS = re.compile(r"\b(bye|goodbye|hang up|end call|not interested|stop calling|no thank you)\b", re.I)
SKIP_PATTERNS = re.compile(r"\b(skip|not applicable|n/?a|none|no company|nothing else|no additional)\b", re.I)
NOT_INTERESTED_PATTERNS = re.compile(r"\b(not interested|stop calling|do not call|don't call|no thank you)\b", re.I)
GENERIC_PURPOSES = {"product enquiry", "product inquiry", "enquiry", "inquiry", "sales enquiry", "sales inquiry"}


@dataclass
class AgentReply:
    text: str
    action: Action
    state: AgentState
    extracted: dict[str, Any]
    should_end: bool = False


class CallingAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def initial_state(self, customer_name: str | None = None, company_name: str | None = None, purpose: str | None = None) -> AgentState:
        seeded_requirement = purpose.strip() if purpose and purpose.strip().lower() not in GENERIC_PURPOSES else None
        state = AgentState(customer_name=customer_name, company_name=company_name, requirement=seeded_requirement)
        self._refresh_completed(state)
        return state

    def greeting(self, state: AgentState, product: str | None = None) -> AgentReply:
        name = state.customer_name or "there"
        subject = f" about {product}" if product else " about your RO requirement"
        field = self._next_field(state)
        state.current_field = field
        if field and field not in state.asked_fields:
            state.asked_fields.append(field)
        question = QUESTIONS.get(field, "How can I help you today?") if field else "How can I help you today?"
        text = f"Hello {name}. I am the AI calling assistant from AI Calling Agent{subject}. {question}"
        return AgentReply(text=text, action=Action.GREET, state=state, extracted={})

    async def respond(self, state: AgentState, user_text: str) -> AgentReply:
        clean = " ".join(user_text.strip().split())
        state.turn_count += 1

        if not clean:
            state.silence_count += 1
            if state.silence_count >= 2:
                state.status = "no_response"
                return AgentReply(
                    text="I am unable to hear you clearly. I will end this call for now. We can follow up later.",
                    action=Action.END,
                    state=state,
                    extracted={},
                    should_end=True,
                )
            return AgentReply(
                text="I did not catch that. Could you please repeat it?",
                action=Action.CLARIFY,
                state=state,
                extracted={},
            )

        state.silence_count = 0
        if END_PATTERNS.search(clean):
            state.status = "not_interested" if NOT_INTERESTED_PATTERNS.search(clean) else "ended_by_customer"
            return AgentReply(
                text="Understood. Thank you for your time. Have a good day.",
                action=Action.END,
                state=state,
                extracted={"end_intent": True},
                should_end=True,
            )

        extracted = await self._extract(state, clean)
        self._apply(state, extracted, clean)
        self._refresh_completed(state)

        next_field = self._next_field(state)
        if next_field is None:
            state.status = "qualified"
            summary = self._short_confirmation(state)
            return AgentReply(
                text=f"Thank you. I have everything I need. {summary} Our team can follow up with you shortly.",
                action=Action.COMPLETE,
                state=state,
                extracted=extracted,
                should_end=True,
            )

        state.current_field = next_field
        if next_field not in state.asked_fields:
            state.asked_fields.append(next_field)

        question = QUESTIONS[next_field]
        llm_text = await self._naturalize(state, clean, question)
        text = llm_text or self._deterministic_ack(clean, question)
        return AgentReply(text=text, action=Action.COLLECT, state=state, extracted=extracted)

    async def _extract(self, state: AgentState, text: str) -> dict[str, Any]:
        result = self._rule_extract(state, text)
        if self.llm.enabled:
            prompt = f"""You extract sales-call slots for a commercial RO system lead.
Return JSON only. Allowed keys: customer_name, company_name, requirement, application, ro_capacity, location, budget, timeline, additional_requirements.
Do not invent values. Use null for unknown. Existing state: {state.to_dict()}
Latest customer utterance: {text!r}
If the user answers the currently asked field ({state.current_field}), prioritize that field."""
            llm_result = await self.llm.generate_json(prompt)
            if llm_result:
                for key, value in llm_result.items():
                    if key in FIELD_ORDER and value not in (None, "", "unknown"):
                        result[key] = str(value).strip()
        return result

    def _rule_extract(self, state: AgentState, text: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        lower = text.lower()
        cap = re.search(r"\b(\d{2,5})\s*(?:lph|lit(?:re|er)s?\s*per\s*hour)\b", lower)
        if cap:
            out["ro_capacity"] = f"{cap.group(1)} LPH"

        money = re.search(r"(?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?\s*(?:lakh|lakhs|k)?|[\d,]+\s*(?:lakh|lakhs|k)\b", lower)
        if money:
            out["budget"] = money.group(0).strip()

        timeline = re.search(r"\b(?:within\s+)?(?:\d+\s*(?:day|days|week|weeks|month|months)|this\s+(?:week|month)|next\s+(?:week|month)|immediately|asap)\b", lower)
        if timeline:
            out["timeline"] = timeline.group(0)

        app_keywords = ["hotel", "hospital", "school", "restaurant", "factory", "office", "apartment", "drinking water", "general usage"]
        for keyword in app_keywords:
            if keyword in lower:
                out["application"] = keyword.title()
                break

        if state.current_field and state.current_field not in out:
            if SKIP_PATTERNS.search(lower) and state.current_field in {"company_name", "application", "additional_requirements"}:
                out[state.current_field] = "Not applicable"
            elif len(text) <= 180 and state.current_field in FIELD_ORDER:
                out[state.current_field] = text
        return out

    def _apply(self, state: AgentState, extracted: dict[str, Any], raw_text: str) -> None:
        for key, value in extracted.items():
            if key in FIELD_ORDER and value:
                setattr(state, key, value)

        lower = raw_text.lower()
        if not state.requirement and any(k in lower for k in ("ro", "water purifier", "purification", "reverse osmosis")):
            state.requirement = raw_text

    def _refresh_completed(self, state: AgentState) -> None:
        state.completed_fields = [field for field in FIELD_ORDER if getattr(state, field, None)]

    def _next_field(self, state: AgentState) -> str | None:
        for field in REQUIRED_FIELDS:
            if not getattr(state, field):
                return field
        for field in FIELD_ORDER:
            if not getattr(state, field):
                return field
        return None

    async def _naturalize(self, state: AgentState, latest: str, required_question: str) -> str | None:
        if not self.llm.enabled:
            return None
        prompt = f"""You are a concise professional voice sales qualification assistant for commercial RO systems.
State: {state.to_dict()}
Customer just said: {latest!r}
Your next objective is exactly this question: {required_question!r}
Respond in 1-2 short spoken sentences. Briefly acknowledge the customer's latest answer and ask only that one question. Do not repeat already collected questions. Do not make pricing/product claims."""
        return await self.llm.generate_text(prompt)

    @staticmethod
    def _deterministic_ack(latest: str, question: str) -> str:
        return f"Got it. {question}"

    @staticmethod
    def _short_confirmation(state: AgentState) -> str:
        parts = []
        if state.ro_capacity:
            parts.append(f"capacity {state.ro_capacity}")
        if state.location:
            parts.append(f"location {state.location}")
        if state.budget:
            parts.append(f"budget {state.budget}")
        if state.timeline:
            parts.append(f"timeline {state.timeline}")
        return "I noted " + ", ".join(parts) + "." if parts else "Your requirements are recorded."
