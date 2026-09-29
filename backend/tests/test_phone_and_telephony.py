from pathlib import Path
import asyncio

from app.schemas import CustomerCreate, CallStart


def test_indian_ten_digit_phone_is_normalized_to_e164():
    customer = CustomerCreate(name="Rahul Kumar", phone_number="98765 43210")
    assert customer.phone_number == "+919876543210"


def test_e164_phone_is_preserved():
    customer = CustomerCreate(name="Rahul Kumar", phone_number="+91 98765-43210")
    assert customer.phone_number == "+919876543210"


def test_call_start_defaults_to_browser_for_safe_fallback():
    payload = CallStart(customer_id="abc")
    assert payload.mode == "browser"


def test_call_start_accepts_real_twilio_mode():
    payload = CallStart(customer_id="abc", mode="twilio")
    assert payload.mode == "twilio"



def test_conversation_relay_twiml_source_has_real_time_voice_controls():
    source = (Path(__file__).parents[1] / "app" / "api" / "twilio_routes.py").read_text()
    assert "ConversationRelay" in source
    assert 'interruptible=\"speech\"' in source
    assert 'reportInputDuringAgentSpeech=\"speech\"' in source
    assert 'speechTimeout=\"800\"' in source


def test_twilio_default_voice_mode_is_trial_friendly_gather():
    config_source = (Path(__file__).parents[1] / "app" / "core" / "config.py").read_text()
    assert 'twilio_voice_mode: str = "gather"' in config_source


def test_twilio_gather_real_call_uses_receiver_speech_result():
    source = (Path(__file__).parents[1] / "app" / "api" / "twilio_routes.py").read_text()
    assert 'input="speech"' in source
    assert 'SpeechResult: str = Form(default="")' in source
    assert 'add_turn(db, call, "customer", SpeechResult or "[silence]")' in source
    assert '<Say voice="Polly.Aditi" language="en-IN">{escape(prompt)}</Say>' in source


def test_twilio_trial_is_ready_for_trial_safe_bootstrap(monkeypatch):
    from app.services.telephony import twilio_provider as module

    monkeypatch.setattr(module.settings, "twilio_account_sid", "AC_TEST")
    monkeypatch.setattr(module.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(module.settings, "twilio_from_number", "+12025550100")
    monkeypatch.setattr(module.settings, "public_backend_url", "https://voice.example.com")
    monkeypatch.setattr(module.settings, "twilio_voice_mode", "gather")
    monkeypatch.setattr(module.settings, "twilio_account_tier", "trial")

    ready, reasons = module.twilio_readiness()
    assert ready is True
    assert reasons == []


def test_twilio_upgraded_is_ready_for_custom_webhook(monkeypatch):
    from app.services.telephony import twilio_provider as module

    monkeypatch.setattr(module.settings, "twilio_account_sid", "AC_TEST")
    monkeypatch.setattr(module.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(module.settings, "twilio_from_number", "+12025550100")
    monkeypatch.setattr(module.settings, "public_backend_url", "https://voice.example.com")
    monkeypatch.setattr(module.settings, "twilio_voice_mode", "gather")
    monkeypatch.setattr(module.settings, "twilio_account_tier", "upgraded")

    ready, reasons = module.twilio_readiness()
    assert ready is True
    assert reasons == []


def test_twilio_provider_dials_the_customer_number(monkeypatch):
    from app.services.telephony import twilio_provider as module

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"sid": "CA_REAL_TEST", "status": "queued"}

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 20.0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, *, auth, data):
            captured["endpoint"] = endpoint
            captured["auth"] = auth
            captured["data"] = data
            return FakeResponse()

    monkeypatch.setattr(module.settings, "twilio_account_sid", "AC_TEST")
    monkeypatch.setattr(module.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(module.settings, "twilio_from_number", "+12025550100")
    monkeypatch.setattr(module.settings, "public_backend_url", "https://voice.example.com")
    monkeypatch.setattr(module.settings, "twilio_voice_mode", "gather")
    monkeypatch.setattr(module.settings, "twilio_account_tier", "upgraded")
    monkeypatch.setattr(module.httpx, "Client", FakeClient)

    result = module.TwilioProvider().start_call(call_id="call-123", phone_number="+919876543210")

    assert captured["data"]["To"] == "+919876543210"
    assert captured["data"]["From"] == "+12025550100"
    assert captured["data"]["Url"] == "https://voice.example.com/api/telephony/twilio/answer/call-123"
    assert captured["data"]["StatusCallback"] == "https://voice.example.com/api/telephony/twilio/status/call-123"
    assert captured["data"]["StatusCallbackEvent"] == ["initiated", "ringing", "answered", "completed"]
    assert result.provider_call_id == "CA_REAL_TEST"
    assert result.mode == "twilio"



def test_twilio_trial_create_call_uses_twilio_sample_url(monkeypatch):
    from app.services.telephony import twilio_provider as module

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"sid": "CA_TRIAL_TEST", "status": "queued"}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, *, auth, data):
            captured["data"] = data
            captured["endpoint"] = endpoint
            return FakeResponse()

        def get(self, *args, **kwargs):
            class GetResponse:
                def raise_for_status(self):
                    return None
                def json(self):
                    return {"status": "completed"}
            return GetResponse()

    monkeypatch.setattr(module.settings, "twilio_account_sid", "AC_TEST")
    monkeypatch.setattr(module.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(module.settings, "twilio_from_number", "+17372508034")
    monkeypatch.setattr(module.settings, "public_backend_url", "https://voice.example.com")
    monkeypatch.setattr(module.settings, "twilio_voice_mode", "gather")
    monkeypatch.setattr(module.settings, "twilio_account_tier", "trial")
    monkeypatch.setattr(module.httpx, "Client", FakeClient)

    result = module.TwilioProvider().start_call(call_id="call-123", phone_number="+919876543210")

    assert captured["data"]["To"] == "+919876543210"
    assert captured["data"]["From"] == "+17372508034"
    assert captured["data"]["Url"] == module.TWILIO_TRIAL_SPEECH_URL
    assert captured["data"]["StatusCallback"] == "https://voice.example.com/api/telephony/twilio/status/call-123"
    assert "Method" not in captured["data"]
    assert result.provider_call_id == "CA_TRIAL_TEST"


def test_twilio_status_reconciliation_reads_latest_provider_state(monkeypatch):
    from app.services.telephony import twilio_provider as module

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "completed"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            assert timeout == 8.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, endpoint, *, auth):
            captured["endpoint"] = endpoint
            captured["auth"] = auth
            return FakeResponse()

    monkeypatch.setattr(module.settings, "twilio_account_sid", "AC_TEST")
    monkeypatch.setattr(module.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)

    status = asyncio.run(module.TwilioProvider.get_call_status("CA_STATUS_TEST"))

    assert status == "completed"
    assert captured["endpoint"].endswith("/Accounts/AC_TEST/Calls/CA_STATUS_TEST.json")
    assert captured["auth"] == ("AC_TEST", "secret")
