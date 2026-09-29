import asyncio

from app.agent.engine import CallingAgent


def run(coro):
    return asyncio.run(coro)


def test_agent_collects_capacity_and_does_not_reask_it():
    agent = CallingAgent()
    state = agent.initial_state("Rahul", "Grand Hotel", "Commercial RO System")
    first = agent.greeting(state, "Commercial RO System")
    assert first.state.current_field in {"ro_capacity", "application"}

    if first.state.current_field == "application":
        reply = run(agent.respond(first.state, "Drinking water for my hotel"))
        state = reply.state
    else:
        state = first.state

    reply = run(agent.respond(state, "Around 500 LPH"))
    assert reply.state.ro_capacity == "500 LPH"
    assert reply.state.current_field != "ro_capacity"


def test_agent_ends_on_customer_request():
    agent = CallingAgent()
    state = agent.initial_state("Rahul")
    agent.greeting(state)
    reply = run(agent.respond(state, "No thank you, please end call"))
    assert reply.should_end is True
    assert reply.action.value == "end"


def test_agent_handles_silence_twice():
    agent = CallingAgent()
    state = agent.initial_state("Rahul")
    first = run(agent.respond(state, ""))
    assert first.should_end is False
    second = run(agent.respond(first.state, ""))
    assert second.should_end is True


def test_generic_campaign_purpose_is_not_mistaken_for_requirement():
    agent = CallingAgent()
    state = agent.initial_state("Rahul", "Grand Hotel", "Product enquiry")
    greeting = agent.greeting(state, "Commercial RO System")
    assert greeting.state.requirement is None
    assert greeting.state.current_field == "requirement"


def test_not_interested_sets_explicit_disposition():
    agent = CallingAgent()
    state = agent.initial_state("Rahul")
    agent.greeting(state)
    reply = run(agent.respond(state, "I am not interested, please stop calling"))
    assert reply.should_end is True
    assert reply.state.status == "not_interested"


def test_second_silence_sets_no_response_disposition():
    agent = CallingAgent()
    state = agent.initial_state("Rahul")
    first = run(agent.respond(state, ""))
    second = run(agent.respond(first.state, ""))
    assert second.should_end is True
    assert second.state.status == "no_response"


class FakeLLM:
    enabled = True
    last_error = None

    async def generate_json(self, prompt):
        return {
            "requirement": "Commercial RO System for hotel",
            "ro_capacity": "500 LPH",
            "location": "Bangalore",
            "budget": "INR 1 lakh",
            "timeline": "within 1 month",
        }

    async def generate_text(self, prompt):
        return "Understood. Any additional requirement I should note?"


def test_llm_extraction_can_fill_multiple_slots_and_skip_reasking():
    agent = CallingAgent(FakeLLM())
    state = agent.initial_state("Rahul", "Grand Hotel", "Product enquiry")
    agent.greeting(state, "Commercial RO System")
    reply = run(agent.respond(state, "We need the system soon."))
    assert reply.state.ro_capacity == "500 LPH"
    assert reply.state.location == "Bangalore"
    assert reply.state.budget == "INR 1 lakh"
    assert reply.state.timeline == "within 1 month"
    assert reply.state.current_field not in {"requirement", "ro_capacity", "location", "budget", "timeline"}


class FailingLLM:
    enabled = True
    last_error = "simulated provider failure"

    async def generate_json(self, prompt):
        return None

    async def generate_text(self, prompt):
        return None


def test_agent_continues_when_llm_provider_fails():
    agent = CallingAgent(FailingLLM())
    state = agent.initial_state("Rahul", None, "Product enquiry")
    agent.greeting(state, "Commercial RO System")
    reply = run(agent.respond(state, "I need a commercial RO system"))
    assert reply.action.value == "collect"
    assert reply.text.startswith("Got it.")
    assert reply.state.requirement
