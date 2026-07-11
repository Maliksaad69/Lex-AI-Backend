"""GROQ-powered LLM service for structured JSON generation.

Fixes: passes system_prompt correctly, uses the right Groq API method,
and auto-extracts JSON from LLM responses (including code-fenced blocks).
"""

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


class GROQService:
    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Send a system + user message to Groq and return parsed JSON.

        Parameters
        ----------
        system_prompt : str
            The system-level instruction (role, constraints, output schema).
        user_prompt : str
            The context-specific request (case text, user query).
        max_tokens : int
            Maximum output tokens.
        temperature : float
            Sampling temperature.  Keep low (0.0–0.2) for deterministic extraction;
            raise to 0.5–0.7 for creative assessment / recommendations.

        Returns
        -------
        dict[str, Any]
            Parsed JSON object from the LLM response.
        """
        chat_completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = chat_completion.choices[0].message.content
        return self._extract_json(text)

    def _extract_json(self, text: str) -> dict:
        """Extract and parse JSON from a potentially code-fenced response."""
        text = text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            match = re.search(
                r"```(?:json)?\s*(.*?)```",
                text,
                re.DOTALL,
            )
            if match:
                text = match.group(1).strip()

        # Try to parse the (possibly cleaned) text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Last resort — try to find the outermost JSON object via brace matching
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
            raise ValueError(
                f"LLM returned invalid JSON.\n\n{text}"
            ) from e


GroqLLM = GROQService()