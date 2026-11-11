"""Valid model configurations for LLMProvider, as a list of dicts.

    from model_configs import CONFIGS
    for cfg in CONFIGS:
        llm = LLMProvider(**cfg["kwargs"])

Each entry: {"name": "<model>@<effort>", "provider": ..., "kwargs": {...LLMProvider args...}}.

How these were found (2026-11-11):
- OpenAI: probed live with reasoning_effort in {omit, none, minimal, low, medium,
  high, xhigh, max} per model; the API's own 400 messages list the supported set.
  Docs: https://developers.openai.com/api/docs/guides/reasoning
- Anthropic: probed live with thinking in {omit, adaptive, disabled, between_tools}
  x effort in {omit, low, medium, high, xhigh, max}; results match the Models API
  capabilities (client.models.retrieve(id).capabilities).
  Docs: https://platform.claude.com/docs/en/build-with-claude/effort

Notes:
- Claude 5.5 models always think: thinking "disabled"/"enabled(budget_tokens)" are
  rejected, so only adaptive thinking (thinking=True) is listed. Sonnet 5.5 also
  accepts thinking {"type": "between_tools"} (effort omit/low/medium/high only; 400 at
  xhigh/max), which LLMProvider can't send yet. Opus 5.5 rejects between_tools.
- Omitting effort is valid everywhere (model default: medium on Opus 5.5 / GPT-5.5,
  high on Sonnet 5.5); list entries use explicit efforts only.
"""
from __future__ import annotations

# provider -> model -> supported efforts
_ANTHROPIC_EFFORTS = ["low", "medium", "high", "xhigh", "max"]

MODEL_OPTIONS: dict[str, dict[str, dict]] = {
    "anthropic": {
        "claude-opus-5-5": {"efforts": _ANTHROPIC_EFFORTS, "thinking": True},
        "claude-sonnet-5-5": {"efforts": _ANTHROPIC_EFFORTS, "thinking": True},
    },
    "openai": {
        "gpt-5.5": {"efforts": ["none", "low", "medium", "high", "xhigh"]},
        "gpt-5.4-mini": {"efforts": ["none", "low", "medium", "high", "xhigh"]},
        "gpt-5-mini": {"efforts": ["minimal", "low", "medium", "high"]},
    },
}


def _build() -> list[dict]:
    configs = []
    for provider, models in MODEL_OPTIONS.items():
        for model, opts in models.items():
            for effort in opts["efforts"]:
                kwargs = {"model": model, "effort": effort}
                if "thinking" in opts:
                    kwargs["thinking"] = opts["thinking"]
                configs.append({"name": f"{model}@{effort}", "provider": provider, "kwargs": kwargs})
    return configs


CONFIGS: list[dict] = _build()
