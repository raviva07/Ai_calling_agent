from ...core.config import get_settings
from .simulated import SimulatedProvider


def get_telephony_provider(provider_name: str | None = None):
    settings = get_settings()
    selected = (provider_name or settings.calling_provider or "simulated").lower()
    if selected in {"twilio", "real"}:
        from .twilio_provider import TwilioProvider
        return TwilioProvider()
    if selected in {"browser", "simulated", "simulation"}:
        return SimulatedProvider()
    raise RuntimeError(f"Unsupported calling provider: {selected}")
