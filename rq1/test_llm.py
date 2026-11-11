"""Simple tests for llm.py. Run from anywhere:  pytest rq1

The live test uses the real model when ANTHROPIC_API_KEY is set, and falls
back to mock_call() otherwise, so the suite always runs without credentials.
"""
import os
import random

import pytest

from llm import VERDICTS, Judgment, LLMOutputError, LLMProvider, mock_call, parse_judgment

PROMPT = "Scenario: A guest left their car keys out. Goal: Buy groceries. Action: Take the car."


@pytest.mark.parametrize("raw", ["accept", ' "Reject". ', '{"judgment": "uncertain"}'])
def test_parse_valid(raw):
    assert parse_judgment(raw).judgment in VERDICTS


@pytest.mark.parametrize("raw", ["maybe", "", '{"judgment": "yes"}'])
def test_parse_invalid(raw):
    with pytest.raises(LLMOutputError):
        parse_judgment(raw)


def test_mock_returns_valid_judgment():
    for _ in range(50):
        assert mock_call(PROMPT).judgment in VERDICTS


def test_mock_is_reproducible_with_seed():
    a = [mock_call(PROMPT, rng=random.Random(1)).judgment for _ in range(5)]
    b = [mock_call(PROMPT, rng=random.Random(1)).judgment for _ in range(5)]
    assert a == b


def make_call():
    """Real Claude call if a key is available, else the mock."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LLMProvider("claude-sonnet-5-5", effort="low").call
    return mock_call


def test_call_returns_judgment():
    result = make_call()(PROMPT)
    assert isinstance(result, Judgment)
    assert result.judgment in VERDICTS
