"""Обёртка над Anthropic SDK (AsyncAnthropic + client.messages.create)."""
import json
import re

import anthropic


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, api_key: str, model: str, effort: str = "low"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.effort = effort

    async def complete(self, system: str, messages: list[dict], max_tokens: int = 400) -> str:
        kwargs = {}
        if self.effort:  # thinking не включаем; effort=low ради скорости
            kwargs["output_config"] = {"effort": self.effort}
        try:
            resp = await self.client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system, messages=messages, **kwargs
            )
        except anthropic.APIError as e:
            raise LLMError(str(e)) from e
        if resp.stop_reason == "refusal":
            raise LLMError("refusal")
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    async def complete_json(self, system: str, messages: list[dict], max_tokens: int = 400) -> dict:
        return parse_json(await self.complete(system, messages, max_tokens))


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LLMError("no json")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError("bad json") from e
