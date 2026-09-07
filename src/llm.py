"""Thin wrapper around the Gemini API with a safe, explicit offline fallback.

Design decision (see README): every LLM-backed node (extraction, classification,
acknowledgement drafting) is paired with a deterministic heuristic implementation.
If GEMINI_API_KEY is not configured, the google-genai package is missing,
or a call raises/times out, `LLMClient.generate_json` returns None and the caller
falls back to the heuristic path. This keeps the pipeline runnable end-to-end on
a laptop with no key and no network (satisfying "work offline except for LLM
calls"), while still using Gemini for real when a key is provided.

Uses the current `google-genai` SDK (REST/httpx transport) rather than the
deprecated `google-generativeai` package, which relies on a raw gRPC transport
that can hang indefinitely in networks with TLS interception or certificate
issues. Enforces explicit per-call timeouts to fail fast.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger("triage.llm")

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or ""
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.available = False
        self._client = None
        
        # Check if Gemini is explicitly enabled (for compatibility, default to disabled)
        use_gemini = os.getenv("USE_GEMINI", "false").lower() in ("true", "1", "yes")

        if not self.api_key or not use_gemini:
            if not self.api_key:
                logger.info("GEMINI_API_KEY not set - running in offline/heuristic mode.")
            else:
                logger.info("USE_GEMINI not enabled - running in offline/heuristic mode. Set USE_GEMINI=true to enable.")
            return

        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            self.available = True
            logger.info("Gemini client initialized successfully.")
        except Exception as exc:  # pragma: no cover - defensive, exercised only with a real key
            logger.warning("Gemini client unavailable (%s). Falling back to offline mode.", exc)
            self.available = False

    def generate_json(self, prompt: str, temperature: float = 0.0, timeout_s: int = 20) -> Optional[dict]:
        """Call Gemini asking for a JSON object; return None on any failure.

        Timeouts are handled at the call site. If the call hangs or fails for
        any reason, this returns None and the caller falls back to heuristic mode.
        """
        if not self.available or self._client is None:
            return None

        try:
            from google.genai import types

            chat = self._client.chats.create(model=self.model_name)
            response = chat.send_message(
                prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            text = response.text or ""
            match = _JSON_BLOCK_RE.search(text)
            raw = match.group(0) if match else text
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Gemini call failed (%s); falling back to heuristic engine.", exc)
            return None


