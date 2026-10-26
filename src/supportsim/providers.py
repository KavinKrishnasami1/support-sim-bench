"""Model providers, pricing and the hard cost cap.

A provider starts conversations; a conversation takes user text or tool results
and returns one assistant turn (text and/or tool calls). The conversation keeps
its own native message history, so provider-specific content (for Anthropic,
thinking blocks) is passed back unchanged and the history is append-only.

Any model can be plugged in by writing a Provider subclass and passing
`--agent-provider my_module:MyProvider` (see README).
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# USD per million tokens: (input, output). Cache writes cost 1.25x input, cache reads 0.1x input.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "scripted": (0.0, 0.0),
}


class BudgetExceeded(RuntimeError):
    pass


class ModelRefused(RuntimeError):
    pass


class Budget:
    """Hard cap on total spend. Checked before every API call, so a run can exceed
    the cap by at most the cost of the calls already in flight."""

    def __init__(self, cap_usd: float):
        self.cap = cap_usd
        self.spent = 0.0
        self.calls = 0
        self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            if self.spent >= self.cap:
                raise BudgetExceeded(f"cost cap ${self.cap:.2f} reached (spent ${self.spent:.4f})")

    def add(self, usd: float) -> None:
        with self._lock:
            self.spent += usd
            self.calls += 1


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0

    def cost(self, model: str) -> float:
        pin, pout = PRICES[model]
        return (self.input * pin + self.cache_write * pin * 1.25 + self.cache_read * pin * 0.1
                + self.output * pout) / 1e6

    def __iadd__(self, o: "Usage") -> "Usage":
        self.input += o.input
        self.output += o.output
        self.cache_write += o.cache_write
        self.cache_read += o.cache_read
        return self


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)


class Conversation(ABC):
    @abstractmethod
    def send_user(self, text: str) -> Turn: ...

    @abstractmethod
    def send_tool_results(self, results: list[tuple[str, dict, bool]]) -> Turn:
        """results: (tool_call_id, result, is_error)"""


class Provider(ABC):
    model: str

    @abstractmethod
    def start(self, system: str, tools: list[dict] | None = None) -> Conversation: ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
class AnthropicProvider(Provider):
    def __init__(self, model: str, budget: Budget, effort: str | None = None, max_tokens: int = 16000):
        import anthropic

        if model not in PRICES:
            raise SystemExit(f"No price for {model}; add it to PRICES in providers.py so the cost cap works.")
        self.client = anthropic.Anthropic(max_retries=4)
        self.model, self.budget, self.effort, self.max_tokens = model, budget, effort, max_tokens

    def start(self, system: str, tools: list[dict] | None = None) -> Conversation:
        return AnthropicConversation(self, system, tools or [])


class AnthropicConversation(Conversation):
    def __init__(self, p: AnthropicProvider, system: str, tools: list[dict]):
        self.p = p
        # tools render before system, so this one breakpoint caches both.
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        self.tools = tools
        self.messages: list[dict] = []

    def send_user(self, text: str) -> Turn:
        self.messages.append({"role": "user", "content": text})
        return self._call()

    def send_tool_results(self, results: list[tuple[str, dict, bool]]) -> Turn:
        # All results for one assistant turn go back in a single user message.
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tid, "content": json.dumps(res), "is_error": err}
            for tid, res, err in results]})
        return self._call()

    def send_user_json(self, text: str, schema: dict) -> dict:
        """One user message answered as JSON that matches `schema` (structured output)."""
        self.messages.append({"role": "user", "content": text})
        turn = self._call(output_format={"type": "json_schema", "schema": schema})
        return json.loads(turn.text)

    def _call(self, output_format: dict | None = None) -> Turn:
        self.p.budget.check()
        kwargs = dict(model=self.p.model, max_tokens=self.p.max_tokens, system=self.system,
                      messages=self.messages, cache_control={"type": "ephemeral"})
        if self.tools:
            kwargs["tools"] = self.tools
        output_config = {}
        if self.p.effort:
            output_config["effort"] = self.p.effort
        if output_format:
            output_config["format"] = output_format
        if output_config:
            kwargs["output_config"] = output_config
        resp = self.p.client.messages.create(**kwargs)
        u = resp.usage
        usage = Usage(u.input_tokens, u.output_tokens, u.cache_creation_input_tokens or 0,
                      u.cache_read_input_tokens or 0)
        self.p.budget.add(usage.cost(self.p.model))
        # Append the full content (thinking blocks included) so the history stays append-only.
        self.messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason == "refusal":
            raise ModelRefused(str(getattr(resp, "stop_details", "") or "refusal"))
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        return Turn(text, calls, resp.stop_reason, usage)


# ---------------------------------------------------------------------------
# Scripted (tests and dry runs; no API calls)
# ---------------------------------------------------------------------------
class ScriptedProvider(Provider):
    """Replays a fixed list of turns. Each turn is a str (text reply) or a dict
    {"text": ..., "tool_calls": [{"name": ..., "args": {...}}]}."""

    model = "scripted"

    def __init__(self, turns: list):
        self.turns = turns

    def start(self, system: str, tools: list[dict] | None = None) -> Conversation:
        return ScriptedConversation(list(self.turns))


class ScriptedConversation(Conversation):
    def __init__(self, turns: list):
        self.turns = turns
        self.n = 0
        self.received: list = []

    def _next(self) -> Turn:
        t = self.turns.pop(0) if self.turns else "###STOP###"
        if isinstance(t, str):
            return Turn(t)
        self.n += 1
        calls = [ToolCall(f"call_{self.n}_{i}", c["name"], c.get("args", {})) for i, c in enumerate(t.get("tool_calls", []))]
        return Turn(t.get("text", ""), calls, "tool_use" if calls else "end_turn")

    def send_user(self, text: str) -> Turn:
        self.received.append(text)
        return self._next()

    def send_tool_results(self, results: list[tuple[str, dict, bool]]) -> Turn:
        self.received.append(results)
        return self._next()


def load_provider(spec: str, model: str, budget: Budget, effort: str | None) -> Provider:
    if spec == "anthropic":
        return AnthropicProvider(model, budget, effort)
    import importlib

    module, _, cls = spec.partition(":")
    return getattr(importlib.import_module(module), cls)(model=model, budget=budget, effort=effort)
