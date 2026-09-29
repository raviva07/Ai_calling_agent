import asyncio

from app.agent.state import AgentState
from app.services.summary_service import SummaryService


def run(coro):
    return asyncio.run(coro)


def test_qualified_summary_marks_interested_and_follow_up():
    state = AgentState(
        customer_name="Rahul",
        requirement="Commercial RO System",
        ro_capacity="500 LPH",
        location="Bangalore",
        budget="INR 1 lakh",
        timeline="within 1 month",
        status="qualified",
    )
    structured, _ = run(SummaryService().build(state, []))
    assert structured["lead_status"] == "Interested"
    assert structured["follow_up_required"] is True
    assert structured["call_outcome"] == "Qualified lead"


def test_not_interested_summary_is_not_misclassified():
    state = AgentState(customer_name="Rahul", status="not_interested")
    structured, _ = run(SummaryService().build(state, []))
    assert structured["lead_status"] == "Not interested"
    assert structured["follow_up_required"] is False
    assert structured["call_outcome"] == "Not interested"


def test_no_response_summary_requires_follow_up():
    state = AgentState(customer_name="Rahul", status="no_response")
    structured, _ = run(SummaryService().build(state, []))
    assert structured["lead_status"] == "Needs follow-up"
    assert structured["follow_up_required"] is True
    assert structured["call_outcome"] == "No response"


class FakeSummaryLLM:
    enabled = True
    last_error = None

    async def generate_json(self, prompt):
        return {"follow_up_required": "No", "lead_status": "Not interested", "call_outcome": "Not interested", "summary_text": "Customer declined."}


def test_llm_string_boolean_is_normalized():
    state = AgentState(customer_name="Rahul", status="not_interested")
    structured, text = run(SummaryService(FakeSummaryLLM()).build(state, []))
    assert structured["follow_up_required"] is False
    assert text == "Customer declined."


def test_no_answer_summary_is_explicit():
    state = AgentState(customer_name="Rahul", status="no_answer")
    structured, text = run(SummaryService().build(state, []))
    assert structured["call_outcome"] == "Customer did not answer"
    assert structured["follow_up_required"] is True
    assert "not answered" in text.lower()


def test_disconnected_summary_is_explicit():
    state = AgentState(customer_name="Rahul", status="disconnected")
    structured, text = run(SummaryService().build(state, []))
    assert structured["call_outcome"] == "Disconnected"
    assert structured["follow_up_required"] is True
    assert "disconnected" in text.lower()


def test_provider_failure_summary_is_explicit():
    state = AgentState(customer_name="Rahul", status="provider_failure")
    structured, text = run(SummaryService().build(state, []))
    assert structured["call_outcome"] == "Provider failure"
    assert structured["follow_up_required"] is True
    assert "provider" in text.lower()
