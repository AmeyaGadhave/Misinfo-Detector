# backend/app/services/llm_agent.py
# __define-ocg__
"""
Robust LLM wrapper for summarization and claim analysis.

Features:
 - Uses official OpenAI Python SDK if OPENAI_API_KEY is present.
 - Attempts to call both chat.completions.create and responses.create (SDKs differ).
 - Safe fallbacks when no key or when API calls fail.
 - Small, deterministic mock behavior for offline testing.
"""

from typing import Optional, List, Dict, Any
import os
import logging
import textwrap
import json
import re

# Assignment-required variables
varOcg = {"service": "llm_agent", "version": "v1"}
varFiltersCg = {"domains": [], "min_reliability": 0.0}

logger = logging.getLogger("llm_agent")
logger.setLevel(logging.WARNING)

# Read key & model from env
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # configurable via env

# Try to import the OpenAI client only if key present
OpenAI = None
_client_available = False
_client = None
if OPENAI_KEY:
    try:
        from openai import OpenAI  # type: ignore
        try:
            _client = OpenAI(api_key=OPENAI_KEY)
            _client_available = True
        except Exception as e:
            logger.warning("OpenAI client init failed: %s", str(e)[:200])
            _client_available = False
    except Exception as e:
        logger.warning("OpenAI import failed: %s", str(e)[:200])
        OpenAI = None
        _client_available = False


def _safe_truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else text[:max_chars].rsplit(" ", 1)[0] + "..."


def _parse_model_response(resp: Any) -> str:
    """
    Try to extract a string reply from multiple SDK response shapes.
    Works with: resp.choices[0].message.content  OR  resp.output_text  OR  resp.output[0].content[0].text
    """
    try:
        # OpenAI chat style
        if hasattr(resp, "choices"):
            choices = getattr(resp, "choices")
            if choices and len(choices) > 0:
                first = choices[0]
                # message might be dict or object-like
                if isinstance(first, dict):
                    msg = first.get("message") or first.get("delta")
                    if isinstance(msg, dict):
                        return msg.get("content", "") or msg.get("text", "")
                # try attribute access
                if hasattr(first, "message"):
                    m = first.message
                    if isinstance(m, dict):
                        return m.get("content", "") or m.get("text", "")
                    # else try attribute
                    if hasattr(m, "content"):
                        return getattr(m, "content", "")
        # responses.create style: resp.output_text (convenience)
        if hasattr(resp, "output_text"):
            return getattr(resp, "output_text", "")
        # responses.create richer shape: resp.output -> list of content objects
        if hasattr(resp, "output") and isinstance(resp.output, list) and len(resp.output) > 0:
            o0 = resp.output[0]
            if isinstance(o0, dict):
                # try several common keys
                for key in ("content", "text", "data"):
                    if key in o0:
                        v = o0.get(key)
                        if isinstance(v, str):
                            return v
                        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and "text" in v[0]:
                            return v[0]["text"]
        # fallback to string representation
        return str(resp)
    except Exception as e:
        logger.debug("parse_model_response failed: %s", str(e))
        return ""


class LLMAgent:
    def __init__(self, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.available = _client_available
        self.client = _client if _client_available else None

    def _call_model(self, messages: List[Dict[str, str]], max_tokens: int = 300, temperature: float = 0.2) -> str:
        """
        Try multiple API call shapes depending on the SDK version.
        Returns the textual response (or raises on hard failure).
        """
        if not self.available or not self.client:
            raise RuntimeError("LLM client not available")

        # 1) Try chat.completions.create (older/newer chat shape)
        try:
            if hasattr(self.client, "chat") and hasattr(self.client.chat, "completions"):
                resp = self.client.chat.completions.create(model=self.model, messages=messages, max_tokens=max_tokens, temperature=temperature)
                txt = _parse_model_response(resp)
                if txt:
                    return txt.strip()
        except Exception as e:
            logger.debug("chat.completions.create failed: %s", str(e)[:300])

        # 2) Try responses.create (newer structured responses)
        try:
            # For responses, convert messages into a single 'input' string
            input_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages if 'role' in m and 'content' in m])
            if hasattr(self.client, "responses") and hasattr(self.client.responses, "create"):
                resp = self.client.responses.create(model=self.model, input=input_text, max_tokens=max_tokens, temperature=temperature)
                txt = _parse_model_response(resp)
                if txt:
                    return txt.strip()
        except Exception as e:
            logger.debug("responses.create failed: %s", str(e)[:300])

        # If both styles fail, raise so caller can fallback
        raise RuntimeError("Model call failed (all shapes)")

    def summarize(self, text: str, max_tokens: int = 300, target_language: Optional[str] = None) -> str:
        """
        Summarize text concisely (2-4 sentences). If no LLM client is available, returns a deterministic mock.
        """
        text = (text or "").strip()
        if not text:
            return "(mock) No content to summarize."

        # Mock fallback
        if not self.available:
            snippet = _safe_truncate(text, max_tokens)
            return f"(mock) {snippet}"

        # Build messages
        system = (
            "You are a concise multilingual summarization assistant. Produce a 2-4 sentence factual summary in the same language "
            "unless target language is explicitly requested. Keep output factual and avoid adding novel claims."
        )
        user_prompt = f"Summarize the following text concisely (2-4 sentences). Keep the original language:\n\n{_safe_truncate(text, 12000)}"
        if target_language:
            user_prompt = f"Summarize the following text concisely (2-4 sentences) in {target_language}:\n\n{_safe_truncate(text, 12000)}"

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]
        try:
            out = self._call_model(messages, max_tokens=max_tokens, temperature=0.15)
            return out
        except Exception as e:
            logger.warning("summarize call failed: %s", str(e)[:300])
            # fallback to mock snippet if LLM fails
            return f"(mock fallback due to LLM error) {_safe_truncate(text, max_tokens)}"

    def analyze_claims(self, claim: str, evidence_snippets: List[str]) -> Dict[str, Any]:
        """
        Ask the LLM whether evidence supports a claim. Returns:
        { "support": float(0-1), "stance": "supports"|"contradicts"|"mixed", "note": str }
        If no LLM available, returns a deterministic heuristic.
        """

        claim = (claim or "").strip()
        snippets = evidence_snippets or []

        # Heuristic fallback
        if not self.available:
            lc = " ".join(snippets).lower()
            score = 0.5
            if any(w in lc for w in ["study", "evidence", "found", "shows", "reported"]):
                score += 0.2
            if any(w in lc for w in ["no evidence", "not", "contradict", "refute", "denies"]):
                score -= 0.2
            stance = "supports" if score >= 0.55 else ("contradicts" if score <= 0.45 else "mixed")
            return {"support": round(max(0.0, min(1.0, score)), 2), "stance": stance, "note": "(heuristic fallback)"}

        # Build a JSON-returning instruction
        system = (
            "You are an evidence synthesizer. Given a brief Claim and several evidence snippets, "
            "decide how well the evidence supports the claim. RETURN A JSON OBJECT with keys: "
            "\"support\" (0.0-1.0), \"stance\" (one of 'supports','contradicts','mixed'), and \"note\" (a one-sentence explanation)."
        )
        user = f"Claim: {claim}\n\nEvidence:\n" + "\n".join(f"- {_safe_truncate(s, 800)}" for s in snippets[:8]) + "\n\nReturn JSON only."

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            raw = self._call_model(messages, max_tokens=200, temperature=0.0)
        except Exception as e:
            logger.warning("analyze_claims LLM call failed: %s", str(e)[:300])
            return {"support": 0.5, "stance": "mixed", "note": "(llm error)"}

        # Try to parse JSON from the model output
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                # Normalize
                support = float(obj.get("support", 0.5))
                stance = obj.get("stance", "mixed")
                note = str(obj.get("note", "")).strip()
                return {"support": round(max(0.0, min(1.0, support)), 2), "stance": stance, "note": note}
            except Exception:
                # fallback: return raw as note
                return {"support": 0.5, "stance": "mixed", "note": raw.strip()}
        # No JSON detected — return raw in note
        return {"support": 0.5, "stance": "mixed", "note": raw.strip()}
