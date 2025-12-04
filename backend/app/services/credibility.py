# backend/app/services/credibility.py
# __define-ocg__
"""
Credibility scoring engine.
Combines domain heuristics, content heuristics, LLM-based claim support (if available),
and knowledge-graph centrality signals to produce a final score 0.0 - 1.0.
"""

from typing import Dict, Any
from math import log1p

# assignment-required variables present
varFiltersCg = {"domains": [], "min_reliability": 0.0}
varOcg = {"mode": "credibility-v1"}

# try to import llm wrapper (optional)
try:
    from app.services.llm_agent import LLMAgent
    _has_llm = True
except Exception:
    LLMAgent = None
    _has_llm = False

# try to import networkx to compute centrality
try:
    import networkx as nx
    _has_nx = True
except Exception:
    nx = None
    _has_nx = False


class CredibilityEngine:
    def __init__(self):
        self.llm = LLMAgent() if (_has_llm and LLMAgent is not None) else None

    def score(self, article: Dict[str, Any], kg_data: Dict[str, Any], stance: Dict[str, Any], bias_note: str = "") -> float:
        """
        Returns score in [0,1].
        We compute sub-scores:
         - domain_score: heuristic based on URL
         - content_score: based on text length & density
         - support_score: LLM support of title/claim from evidence (stance['support'])
         - centrality_score: if knowledge graph has meaningful nodes, high central nodes -> higher score
         - bias_penalty: penalize sensational language
        """
        url = article.get("url", "")
        text = (article.get("text") or "").strip()

        domain_score = self._domain_reliability_score(url)  # 0-1
        content_score = self._content_score(text)           # 0-1

        # stance/support (0-1) -> fallback 0.5
        support_score = float(stance.get("support", 0.5)) if isinstance(stance, dict) else 0.5

        centrality_score = self._kg_centrality_score(kg_data) if kg_data else 0.5

        bias_penalty = self._bias_penalty(bias_note)

        # Weighted aggregation (weights chosen for interpretability)
        w_domain = 0.30
        w_content = 0.25
        w_support = 0.30
        w_central = 0.15

        raw = w_domain * domain_score + w_content * content_score + w_support * support_score + w_central * centrality_score
        score = max(0.0, min(1.0, raw - bias_penalty))

        return round(score, 3)

    def _domain_reliability_score(self, url: str) -> float:
        if not url:
            return 0.45
        u = url.lower()
        trusted = ["bbc.", "reuters.", "nytimes.", "theguardian.", "washingtonpost.", "cnn.", "aljazeera.", "apnews."]
        for t in trusted:
            if t in u:
                return 0.95
        academic = ["ieee.", "springer.", "nature.", "sciencedirect.", "acm.", "nih.gov"]
        for a in academic:
            if a in u:
                return 0.85
        local = ["thehindu", "timesofindia", "indianexpress", "lallantop"]
        for l in local:
            if l in u:
                return 0.7
        # unknown
        return 0.5

    def _content_score(self, text: str) -> float:
        if not text:
            return 0.2
        # length normalized via log1p to reduce heavy influence of long text
        ln = min(1.0, log1p(len(text)) / log1p(5000))
        # density: count sentences/paragraphs ratio (simple)
        sents = text.count(".") + text.count("!") + text.count("?")
        density = min(1.0, (sents / max(1, (len(text)/200))))
        return round(0.5 * ln + 0.5 * density, 3)

    def _kg_centrality_score(self, kg_data: Dict[str, Any]) -> float:
        if not _has_nx or not kg_data:
            return 0.5
        try:
            # build graph
            G = nx.Graph()
            for n in kg_data.get("nodes", []):
                nid = n.get("id") or n.get("label") or n.get("text")
                G.add_node(nid)
            for e in kg_data.get("links", []):
                s = e.get("source")
                t = e.get("target")
                if s and t:
                    G.add_edge(s, t)
            if G.number_of_nodes() < 2:
                return 0.45
            central = nx.degree_centrality(G)
            # average centrality normalized
            avg = sum(central.values()) / len(central)
            return round(min(0.95, avg * 1.5), 3)
        except Exception:
            return 0.5

    def _bias_penalty(self, bias_note: str) -> float:
        if not bias_note:
            return 0.0
        low = bias_note.lower()
        if "sensational" in low or "opinionated" in low or "highly biased" in low:
            return 0.18
        if "slightly biased" in low:
            return 0.06
        return 0.0
