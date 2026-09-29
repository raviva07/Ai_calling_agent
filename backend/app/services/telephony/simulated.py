from .base import ProviderStartResult


class SimulatedProvider:
    def start_call(self, *, call_id: str, phone_number: str) -> ProviderStartResult:
        return ProviderStartResult(provider_call_id=f"sim-{call_id}", status="in_progress", mode="browser")
