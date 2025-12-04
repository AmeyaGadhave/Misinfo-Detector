# backend/app/services/research_agent.py
# __define-ocg__   <-- required keyword included in the file per assignment

from typing import Dict, Any, List
from app.services.scraper import Scraper
from app.services.llm_agent import LLMAgent
from app.services.knowledge_graph import build_graph
import math

# assignment-required variables
varFiltersCg = {"domains": [], "min_reliability": 0.0}
varOcg = {"mode": "llm-upgrade-demo"}


class ResearchAgent:
    def __init__(self):
        self.llm = LLMAgent()
        self.filters = varFiltersCg
        self.varOcg = varOcg

    def _make_evidence_snippets(self, text: str, max_snips: int = 6) -> List[str]:
        # Split into sentences and return top N short snippets
        if not text:
            return []
        # naive: split by punctuation.
        import re
        sents = re.split(r'(?<=[.!?])\s+', text.strip())
        snips = [s for s in sents if len(s.strip()) > 30][:max_snips]
        if not snips:
            # fallback: take chunks
            return [text.strip()[:300]]
        return snips

    def analyze(self, article: Dict[str, Any]) -> Dict[str, Any]:
        text = (article.get("text") or "").strip()
        title = article.get("title") or ""

        # Evidence extraction
        evidence_snips = self._make_evidence_snippets(text, max_snips=8)

        # Multilingual summary via LLM
        summary = self.llm.summarize(text) if text else "(no text to summarize)"

        # Stance + support analysis: check claim (title) vs evidence
        claim = title or (text.split(".")[0] if text else "")
        stance_result = self.llm.analyze_claims(claim, evidence_snips) if claim else {"support": 0.5, "stance": "mixed", "note": "no claim"}

        # Source verification heuristic: domain reliability + content length
        domain_score = self._domain_reliability_score(article.get("url", ""))
        length_score = min(0.95, (len(text) / 5000) + 0.1) if text else 0.3

        # Sentiment / bias: use LLM quick probe (we ask for tone)
        bias_note = "(no bias check performed)"
        if self.llm.client:
            try:
                bias_prompt = (
                    "Return a one-sentence assessment of the article's overall tone and potential bias "
                    "(e.g., neutral, slightly biased, opinionated, sensational). Keep response short."
                )
                bias_resp = self.llm.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": "You are a tone and bias detector."},
                              {"role": "user", "content": bias_prompt + "\n\n" + (text[:3000])}],
                    max_tokens=60
                )
                bias_note = bias_resp.choices[0].message.get("content", "").strip()
            except Exception:
                bias_note = "(bias detection unavailable)"
        else:
            # heuristic fallback
            bias_note = "sensational" if any(ex in text.lower() for ex in ["shocking", "must read", "unbelievable", "you won't believe"]) else "neutral"

        # Combined credibility: simple aggregation
        support_score = float(stance_result.get("support", 0.5))
        combined = (0.5 * length_score) + (0.3 * domain_score) + (0.2 * support_score)
        credibility_score = round(max(0.0, min(1.0, combined)), 3)

        # Build knowledge graph
        kg = build_graph(text)

        # Construct evidence list with short descriptions
        evidence = []
        evidence.append(f"Article length: {len(text)}")
        evidence.append(f"Title: {title}")
        for i, s in enumerate(evidence_snips[:6]):
            evidence.append(f"Snippet {i+1}: {s[:240]}")

        contradictions = []
        if stance_result.get("stance") == "contradicts":
            contradictions.append("LLM found evidence that contradicts the main claim.")

        return {
            "summary": summary,
            "evidence": evidence,
            "contradictions": contradictions,
            "credibility_score": round(credibility_score*1.0, 3),
            "knowledge_graph": kg,
            "stance": stance_result,
            "bias_note": bias_note
        }

    def _domain_reliability_score(self, url: str) -> float:
        """
        Basic domain reliability heuristics. For demonstration only.
        - Known reputable TLDs/news domains get higher scores.
        - Academic/publisher domains can be lower if they block scraping (we can't judge).
        """
        if not url:
            return 0.5
        url = url.lower()
        # quick trusted domains list (extend as needed)
        trusted = ["bbc.", "reuters.", "nytimes.", "theguardian.", "washingtonpost.", "cnn.", "aljazeera."]
        for t in trusted:
            if t in url:
                return 0.9
        # academic publishers
        academic = ["ieee.", "springer.", "nature.", "sciencedirect.", "acm."]
        for a in academic:
            if a in url:
                # publishers can be behind paywalls or bot-blocking -> slightly lower
                return 0.6
        # default neutral
        return 0.5
