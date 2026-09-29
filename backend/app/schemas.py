import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone_number: str = Field(min_length=8, max_length=24)
    company_name: str | None = Field(default=None, max_length=200)
    purpose: str | None = Field(default=None, max_length=240)
    product: str | None = Field(default=None, max_length=240)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = re.sub(r"[\s().-]", "", value.strip())
        if re.fullmatch(r"[6-9]\d{9}", normalized):
            normalized = "+91" + normalized
        elif re.fullmatch(r"0[6-9]\d{9}", normalized):
            normalized = "+91" + normalized[1:]
        if not PHONE_RE.match(normalized):
            raise ValueError("Enter a valid phone number, e.g. +919876543210 or 9876543210")
        return normalized


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    phone_number: str
    company_name: str | None
    purpose: str | None
    product: str | None
    created_at: datetime


class CallStart(BaseModel):
    customer_id: str
    mode: Literal["browser", "twilio"] = "browser"


class CallEnd(BaseModel):
    reason: str = "completed"


class CallEventIn(BaseModel):
    event_type: str = Field(min_length=2, max_length=80)
    details: dict[str, Any] = Field(default_factory=dict)


class TurnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    speaker: str
    message: str
    created_at: datetime


class CallOut(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    phone_number: str
    status: str
    outcome: str | None
    lead_status: str | None
    follow_up_required: bool
    direction: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int
    provider_call_id: str | None
    agent_state: dict[str, Any]
    structured_summary: dict[str, Any] | None
    summary_text: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    turns: list[TurnOut] = Field(default_factory=list)


class DashboardStats(BaseModel):
    total_calls: int
    active_calls: int
    completed_calls: int
    failed_calls: int
    interested_leads: int
    follow_ups_required: int
    average_call_duration_seconds: float
