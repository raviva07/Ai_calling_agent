from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderStartResult:
    provider_call_id: str | None
    status: str
    mode: str


class TelephonyProvider(Protocol):
    def start_call(self, *, call_id: str, phone_number: str) -> ProviderStartResult: ...
