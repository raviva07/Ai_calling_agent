from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Action(str, Enum):
    GREET = "greet"
    COLLECT = "collect"
    CLARIFY = "clarify"
    COMPLETE = "complete"
    END = "end"


@dataclass
class AgentState:
    customer_name: str | None = None
    company_name: str | None = None
    requirement: str | None = None
    application: str | None = None
    ro_capacity: str | None = None
    location: str | None = None
    budget: str | None = None
    timeline: str | None = None
    additional_requirements: str | None = None
    current_field: str | None = None
    asked_fields: list[str] = field(default_factory=list)
    completed_fields: list[str] = field(default_factory=list)
    turn_count: int = 0
    silence_count: int = 0
    status: str = "collecting"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "AgentState":
        if not value:
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in value.items() if k in allowed})


FIELD_ORDER = [
    "customer_name",
    "company_name",
    "requirement",
    "application",
    "ro_capacity",
    "location",
    "budget",
    "timeline",
    "additional_requirements",
]

REQUIRED_FIELDS = [
    "customer_name",
    "requirement",
    "ro_capacity",
    "location",
    "budget",
    "timeline",
]

QUESTIONS = {
    "customer_name": "May I confirm your name, please?",
    "company_name": "What is your company or hotel name? You can say skip if this does not apply.",
    "requirement": "Could you briefly describe the RO system requirement?",
    "application": "What will the system mainly be used for, for example drinking water or general hotel usage?",
    "ro_capacity": "What RO capacity are you looking for, in litres per hour?",
    "location": "Which city will the system be installed in?",
    "budget": "Do you have a target budget or budget range?",
    "timeline": "When are you planning to purchase or install the system?",
    "additional_requirements": "Any additional requirement I should note? You can say no if there is nothing else.",
}
