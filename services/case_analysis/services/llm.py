import json
import os
import re
import time
from typing import Any
from mistralai.client import Mistral
from dotenv import load_dotenv
from groq import Groq, RateLimitError, APIStatusError

load_dotenv()

MISTRAL_API=os.environ.get("MISTRAL_API_KEY")
print(MISTRAL_API)

class MistralService:
    def __init__(self):
        self.client = Mistral(api_key=MISTRAL_API)
        print()
        self.model = os.getenv("MISTRAL_MODEL") or "codestral-2508"
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> dict[str, Any]:
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
                print(chat_completion)
                text = chat_completion.choices[0].message.content
                print("=" * 80)
                print("RAW LLM RESPONSE:")
                print(text)
                print("=" * 80)
                return self._extract_json(text)
            except (RateLimitError, APIStatusError) as e:
                if e.status_code == 429 and attempt < max_retries - 1:
                    wait = 2**attempt * 10  # 10s, 20s, 40s
                    time.sleep(wait)
                    continue
                raise

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
        max_retries: int = 3,
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
        max_retries : int
            Retries on 429 rate-limit errors with exponential backoff.

        Returns
        -------
        dict[str, Any]
            Parsed JSON object from the LLM response.
        """
        print(user_prompt)
        for attempt in range(max_retries):
            try:
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
                print("=" * 80)
                print("RAW LLM RESPONSE:")
                print(text)
                print("=" * 80)
                return self._extract_json(text)
            except (RateLimitError, APIStatusError) as e:
                if e.status_code == 429 and attempt < max_retries - 1:
                    wait = 2**attempt * 10  # 10s, 20s, 40s
                    time.sleep(wait)
                    continue
                raise

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


MistralLLM =  MistralService()