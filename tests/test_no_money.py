"""An account with no money on it, told apart from one that is merely busy.

Waiting out an empty account costs a church its Sunday and teaches it that the app hangs.
The answer is twenty euros, and the app has to say so.
"""

import pytest

from backend import discovery


class Said(Exception):
    """Stands in for an anthropic error, which carries its reason on .message."""

    def __init__(self, message: str, status_code: int = 429):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# --- which refusal is about money ---------------------------------------------------


@pytest.mark.parametrize("said", [
    "Your credit balance is too low to access the Anthropic API.",
    "credit balance is too low",
    "This request would exceed your organization's monthly spend limit.",
    "Insufficient credit for this request.",
    "Billing error: add a payment method.",
    "Monthly usage limit reached.",
    "QUOTA EXCEEDED",
])
def test_a_refusal_about_money_is_recognised(said):
    assert discovery.about_money(said)


@pytest.mark.parametrize("said", [
    "Number of request tokens has exceeded your per-minute rate limit.",
    "Overloaded",
    "rate_limit_error",
    "Internal server error",
    "",
])
def test_an_ordinary_rate_limit_is_not_about_money(said):
    assert not discovery.about_money(said)


def test_nothing_at_all_is_not_about_money():
    assert not discovery.about_money(None)


# --- and what happens to it -----------------------------------------------------------


def anthropic_raising(monkeypatch, exc):
    """Make one call to Claude fail with `exc`, with the SDK's error classes in place."""
    import anthropic

    def refuse(*_a, **_k):
        raise exc

    class Messages:
        create = staticmethod(refuse)
        parse = staticmethod(refuse)

    class Client:
        def __init__(self, *a, **k):
            self.messages = Messages()

    monkeypatch.setattr(anthropic, "Anthropic", Client)
    monkeypatch.setattr(discovery, "_anthropic_request", refuse)
    return anthropic


def test_an_empty_account_is_not_retried(monkeypatch):
    """Retrying with growing pauses ends in a message about a limit when the answer is money."""
    import anthropic

    empty = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    empty.message = "Your credit balance is too low to access the Anthropic API."
    empty.status_code = 429
    anthropic_raising(monkeypatch, empty)

    tried = []
    monkeypatch.setattr(discovery.time, "sleep", lambda s: tried.append(s))
    with pytest.raises(discovery.NoMoney) as caught:
        discovery.ask("x", "y", discovery.LlmAnalysis)
    assert tried == [], "er is niet gewacht"
    assert "tegoed" in str(caught.value)
    assert "console.anthropic.com" in str(caught.value)


def test_an_ordinary_rate_limit_is_still_retried(monkeypatch):
    import anthropic

    busy = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    busy.message = "Number of requests has exceeded your per-minute rate limit."
    busy.status_code = 429
    anthropic_raising(monkeypatch, busy)

    tried = []
    monkeypatch.setattr(discovery.time, "sleep", lambda s: tried.append(s))
    with pytest.raises(discovery.Retryable):
        discovery.ask("x", "y", discovery.LlmAnalysis)
    assert len(tried) == discovery.LLM_ATTEMPTS - 1, "er is wel gewacht"


def test_a_four_hundred_about_money_says_money_rather_than_config(monkeypatch):
    import anthropic

    empty = anthropic.APIStatusError.__new__(anthropic.APIStatusError)
    empty.message = "Your credit balance is too low to access the Anthropic API."
    empty.status_code = 400
    anthropic_raising(monkeypatch, empty)
    with pytest.raises(discovery.NoMoney):
        discovery.ask("x", "y", discovery.LlmAnalysis)


def test_a_four_hundred_about_anything_else_still_points_at_the_settings(monkeypatch):
    import anthropic

    wrong = anthropic.APIStatusError.__new__(anthropic.APIStatusError)
    wrong.message = "output_config.effort: Input should be 'low', 'medium', 'high'"
    wrong.status_code = 400
    anthropic_raising(monkeypatch, wrong)
    with pytest.raises(RuntimeError) as caught:
        discovery.ask("x", "y", discovery.LlmAnalysis)
    assert not isinstance(caught.value, discovery.NoMoney)
    assert "config.env" in str(caught.value)


def test_money_stops_the_whole_run_rather_than_counting_failed_passages(monkeypatch):
    """Every other passage fails the same way; one sentence beats a tally."""
    from backend.models import Segment, Transcript

    transcript = Transcript(language="nl", segments=[
        Segment(start=i * 4.0, end=i * 4.0 + 3.6, text=f"Zin {i} van de preek.")
        for i in range(3000)])

    def empty(*_a, **_k):
        raise discovery.NoMoney(discovery.OUT_OF_MONEY)

    monkeypatch.setattr(discovery, "check_provider", lambda: None)
    monkeypatch.setattr(discovery, "analyze_window", empty)
    with pytest.raises(discovery.NoMoney) as caught:
        discovery.discover(transcript)
    said = str(caught.value)
    assert said == discovery.OUT_OF_MONEY, "geen voorvoegsel over mislukte stukken"


# --- and when the key is first tried --------------------------------------------------


def test_trying_a_key_on_an_empty_account_says_what_to_do(monkeypatch):
    import anthropic

    empty = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    empty.message = "Your credit balance is too low."
    empty.status_code = 429
    anthropic_raising(monkeypatch, empty)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "A" * 24)
    monkeypatch.setattr(discovery, "LLM_PROVIDER", "anthropic")
    with pytest.raises(RuntimeError) as caught:
        discovery.try_key()
    assert "tegoed" in str(caught.value) and "Billing" in str(caught.value)


def test_a_key_hitting_a_plain_rate_limit_is_told_to_wait(monkeypatch):
    import anthropic

    busy = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    busy.message = "per-minute rate limit"
    busy.status_code = 429
    anthropic_raising(monkeypatch, busy)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "A" * 24)
    monkeypatch.setattr(discovery, "LLM_PROVIDER", "anthropic")
    with pytest.raises(RuntimeError) as caught:
        discovery.try_key()
    assert "over een minuut" in str(caught.value)
