from __future__ import annotations

from typing import Any

from ..agent.llm import LLMClient
from ..agent.state import AgentState


class SummaryService:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    async def build(self, state: AgentState, transcript: list[dict[str, str]]) -> tuple[dict[str, Any], str]:
        deterministic = self._deterministic(state)
        if self.llm.enabled:
            prompt = f"""Generate a structured sales-call summary from this state and transcript.
Return JSON only with keys: customer, company, requirement, capacity, location, application, budget, purchase_timeline, key_requirements, customer_intent, important_points, follow_up_required, lead_status, call_outcome, summary_text.
follow_up_required must be a JSON boolean (true/false). Use only facts present. State: {state.to_dict()}
Transcript: {transcript}"""
            llm_result = await self.llm.generate_json(prompt)
            if llm_result:
                merged = {**deterministic, **{k: v for k, v in llm_result.items() if v not in (None, "")}}
                merged["follow_up_required"] = self._normalize_bool(
                    merged.get("follow_up_required"), deterministic["follow_up_required"]
                )
                summary_text = str(merged.pop("summary_text", self._summary_text(state)))
                return merged, summary_text
        return deterministic, self._summary_text(state)

    @staticmethod
    def _normalize_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "y", "1", "required"}:
                return True
            if lowered in {"false", "no", "n", "0", "not required"}:
                return False
        return default

    def _deterministic(self, state: AgentState) -> dict[str, Any]:
        required = [state.requirement, state.ro_capacity, state.location, state.budget, state.timeline]
        qualified = all(required)
        if state.status == "not_interested":
            customer_intent, lead_status, outcome, follow_up = "Not interested", "Not interested", "Not interested", False
        elif qualified:
            customer_intent, lead_status, outcome, follow_up = "Interested / qualified", "Interested", "Qualified lead", True
        elif state.status == "no_response":
            customer_intent, lead_status, outcome, follow_up = "No response", "Needs follow-up", "No response", True
        elif state.status == "no_answer":
            customer_intent, lead_status, outcome, follow_up = "Not reached", "Needs follow-up", "Customer did not answer", True
        elif state.status == "disconnected":
            customer_intent, lead_status, outcome, follow_up = "Conversation interrupted", "Needs follow-up", "Disconnected", True
        elif state.status == "provider_failure":
            customer_intent, lead_status, outcome, follow_up = "Call not connected", "Needs follow-up", "Provider failure", True
        else:
            customer_intent, lead_status, outcome, follow_up = "Information collection incomplete", "Needs follow-up", "Incomplete", True
        return {
            "customer": state.customer_name,
            "company": state.company_name,
            "requirement": state.requirement,
            "capacity": state.ro_capacity,
            "location": state.location,
            "application": state.application,
            "budget": state.budget,
            "purchase_timeline": state.timeline,
            "additional_requirements": state.additional_requirements,
            "key_requirements": [v for v in [state.requirement, state.ro_capacity, state.application, state.location] if v],
            "customer_intent": customer_intent,
            "important_points": [v for v in [state.budget, state.timeline, state.additional_requirements] if v],
            "follow_up_required": follow_up,
            "lead_status": lead_status,
            "call_outcome": outcome,
        }

    @staticmethod
    def _summary_text(state: AgentState) -> str:
        name = state.customer_name or "Customer"
        if state.status == "not_interested":
            return f"{name} indicated they are not interested at this time."
        if state.status == "no_response":
            return f"{name} did not provide a usable response after retrying."
        if state.status == "no_answer":
            return f"The outbound call to {name} was not answered."
        if state.status == "disconnected":
            return f"The call with {name} disconnected before qualification was completed."
        if state.status == "provider_failure":
            return f"The outbound call to {name} could not be connected because the calling provider failed."
        requirement = state.requirement or "an RO solution"
        details = [
            f"capacity {state.ro_capacity}" if state.ro_capacity else None,
            f"in {state.location}" if state.location else None,
            f"budget {state.budget}" if state.budget else None,
            f"timeline {state.timeline}" if state.timeline else None,
        ]
        suffix = ", ".join(x for x in details if x)
        return f"{name} is looking for {requirement}" + (f" with {suffix}." if suffix else ".")
