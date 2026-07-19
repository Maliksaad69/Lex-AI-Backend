"""LLM service for jury simulation — Mistral-only.

Provides a single MistralService class used by all jury simulation agents.
"""

import json
import os
import re
import time
from typing import Any

from mistralai.client import Mistral
from dotenv import load_dotenv

load_dotenv()


class MistralService:
    """Mistral AI LLM wrapper for structured JSON generation."""

    def __init__(self):
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is not set")
        self.client = Mistral(api_key=api_key)
        self.model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Send a system + user message to Mistral and return parsed JSON."""
        for attempt in range(max_retries):
            try:
                chat_completion = self.client.chat.complete(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                text = chat_completion.choices[0].message.content

                if os.getenv("DEBUG_LLM"):
                    print("=" * 80)
                    print("RAW LLM RESPONSE:")
                    print(text)
                    print("=" * 80)

                return self._extract_json(text)

            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2**attempt * 5
                    time.sleep(wait)
                    continue
                raise

    def _extract_json(self, text: str) -> dict:
        """Extract and parse JSON from a potentially code-fenced response."""
        text = text.strip()

        if text.startswith("```"):
            match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            brace_start = text.find("{")
            if brace_start != -1:
                depth = 0
                for i in range(brace_start, len(text)):
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[brace_start : i + 1])
                            except json.JSONDecodeError:
                                break
            raise ValueError(f"LLM returned invalid JSON.\n\n{text}")


# Module-level singleton for convenience
mistral_llm = MistralService()