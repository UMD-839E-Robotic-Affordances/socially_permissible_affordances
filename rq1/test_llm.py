"""Simple tests for llm.py. Run from anywhere:  pytest rq1

test_call_returns_judgment uses OpenAI (else Anthropic) if a key is found in the
env or ~/.secrets, and otherwise warns and falls back to the mock, so the suite
always runs without credentials.
"""
import os
import random
import warnings

import pytest

from model_configs import CONFIGS
from llm import VERDICTS, Judgment, LLMOutputError, LLMProvider, default_llm, ensure_api_key, parse_judgment

PROMPT = "Scenario: A guest left their car keys out. Goal: Buy groceries. Action: Take the car."


@pytest.mark.parametrize("raw", ["accept", ' "Reject". ', '{"judgment": "uncertain"}'])
def test_parse_valid(raw):
    assert parse_judgment(raw).judgment in VERDICTS


@pytest.mark.parametrize("raw", ["maybe", "", '{"judgment": "yes"}'])
def test_parse_invalid(raw):
    with pytest.raises(LLMOutputError):
        parse_judgment(raw)


def test_mock_returns_valid_judgment():
    llm = LLMProvider("mock")
    for _ in range(50):
        assert llm.call(PROMPT).judgment in VERDICTS


def test_mock_is_reproducible_with_seed():
    a = LLMProvider("mock", rng=random.Random(1))
    b = LLMProvider("mock", rng=random.Random(1))
    a, b = [[x.call(PROMPT).judgment for _ in range(20)] for x in (a, b)]
    assert a == b


def test_call_returns_judgment():
    # Real OpenAI/Anthropic if a key exists; otherwise default_llm() warns and mocks.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        llm = default_llm()
    if llm.provider == "mock":
        assert any("mock" in str(w.message) for w in caught)
    result = llm.call(PROMPT)
    assert isinstance(result, Judgment)
    assert result.judgment in VERDICTS


def test_ensure_api_key_reads_existing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".secrets").mkdir()
    (tmp_path / ".secrets" / "openai_api_key").write_text("sk-fake\n")
    assert ensure_api_key("openai") == "sk-fake"


def test_ensure_api_key_prompts_and_saves_with_mode_600(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt: "sk-pasted")
    assert ensure_api_key("openai") == "sk-pasted"
    f = tmp_path / ".secrets" / "openai_api_key"
    assert f.read_text().strip() == "sk-pasted"
    assert oct(f.stat().st_mode & 0o777) == "0o600"


def test_ensure_api_key_errors_without_tty(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(LLMOutputError):
        ensure_api_key("openai")


# --- Live tests: OFF by default (they cost money). Enable with:  RUN_LIVE_LLM=1 pytest rq1 -k live
# One cheap-effort config per model, taken from model_configs.CONFIGS.
LIVE_CONFIGS = [c for c in CONFIGS if c["kwargs"]["effort"] in ("low", "none")]


@pytest.mark.skipif(not os.environ.get("RUN_LIVE_LLM"), reason="live LLM tests disabled; set RUN_LIVE_LLM=1")
@pytest.mark.parametrize("cfg", LIVE_CONFIGS, ids=lambda c: c["name"])
def test_live_config_returns_judgment(cfg):
    result = LLMProvider(**cfg["kwargs"]).call(PROMPT)
    assert result.judgment in VERDICTS
