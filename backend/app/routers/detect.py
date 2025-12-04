# backend/app/routers/detect.py
# __define-ocg__

"""
Agentic + LLM-enhanced detection router.
This integrates:
 - Real agentic AI controller
 - Web scraping
 - LLM summarization (OpenAI GPT-4.1 / GPT-4o)
 - Hybrid stance + bias detection (your HF models)
 - Knowledge graph extraction
 - Credibility scoring
 - Professional dashboard response JSON
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

# assignment-required variable
varOcg = {"router": "detect", "mode": "agentic-llm"}

# import your services
from app.services.scraper import Scraper
from app.services.agentic_controller import AgenticResearchAgent   # NEW
from app.services.research_agent import ResearchAgent
from app.services.knowledge_graph import build_graph
from app.services.credibility import CredibilityEngine


router = APIRouter()


# -----------------------------
# REQUEST MODELS
# -----------------------------
class DetectRequest(BaseModel):
    url: str


class AgenticRequest(BaseModel):
    query: str | None = None
    url: str | None = None


# ======================================================================
# 1) CLASSIC /detect  (kept for compatibility with your current frontend)
# ======================================================================
@router.post("/detect", response_model=Dict[str, Any])
def detect(req: DetectRequest):
    """
    Traditional pipeline:
    scrape → research agent → KG → credibility → structured JSON
    """

    try:
        # Scrape
        article = Scraper.scrape(req.url)
        if not isinstance(article, dict):
            article = {"title": "", "text": ""}

        article["url"] = req.url

        # Research agent (LLM summary + evidence)
        agent = ResearchAgent()
        analysis = agent.analyze(article)

        # Fallback safe structure
        if not isinstance(analysis, dict):
            analysis = {
                "summary": "(no summary)",
                "evidence": [],
                "contradictions": [],
                "stance": {},
                "bias_note": "(no bias info)",
                "knowledge_graph": None,
            }

        # Knowledge graph
        kg = analysis.get("knowledge_graph") or build_graph(article.get("text", ""))

        # Credibility score
        cred = CredibilityEngine()
        score = cred.score(
            article=article,
            kg_data=kg,
            stance=analysis.get("stance", {}),
            bias_note=analysis.get("bias_note", "")
        )

        # Response for your frontend UI
        return {
            "url": req.url,
            "title": article.get("title", ""),
            "text": article.get("text", ""),
            "summary": analysis.get("summary"),
            "evidence": analysis.get("evidence", []),
            "contradictions": analysis.get("contradictions", []),
            "credibility_score": score,
            "knowledge_graph": kg,
            "stance": analysis.get("stance", {}),
            "bias_note": analysis.get("bias_note", "")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classic detect failed: {str(e)}")



# ======================================================================
# 2) NEW: /agentic_detect — complete agentic AI orchestrated pipeline
# ======================================================================
@router.post("/agentic_detect", response_model=Dict[str, Any])
def agentic_detect(req: AgenticRequest):
    """
    FULL agentic AI pipeline:
      - if URL is given → scrape → research pipeline
      - if query is given → agentic deep research
    """

    try:
        # Initialize agentic controller
        agent = AgenticResearchAgent()

        # CASE A: USER PASSED A URL (article analysis mode)
        if req.url:
            article = Scraper.scrape(req.url)
            if not isinstance(article, dict):
                article = {"title": "", "text": ""}

            article["url"] = req.url

            # Let ResearchAgent do LLM summary, stance, snippets
            research = ResearchAgent().analyze(article)

            # Build KG
            kg = research.get("knowledge_graph") or build_graph(article.get("text", ""))

            # Credibility scoring
            cred = CredibilityEngine()
            score = cred.score(
                article=article,
                kg_data=kg,
                stance=research.get("stance", {}),
                bias_note=research.get("bias_note", "")
            )

            return {
                "mode": "url-article-analysis",
                "url": req.url,
                "title": article.get("title", ""),
                "summary": research.get("summary"),
                "evidence": research.get("evidence"),
                "stance": research.get("stance"),
                "bias_note": research.get("bias_note"),
                "knowledge_graph": kg,
                "credibility_score": score,
            }

        # CASE B: USER PASSED A QUERY (deep research mode)
        if req.query:
            result = agent.run(req.query)
            return {
                "mode": "deep-research",
                "query": req.query,
                "plan": result["plan"],
                "task_results": result["task_results"],
                "brief": result["brief"],                 # structured professional research brief
                "credibility_score": result["top_level_credibility"],
                "knowledge_graph": result["brief"]["knowledge_graph"],
                "timestamp": result["timestamp"]
            }

        raise HTTPException(status_code=400, detail="Provide either 'url' or 'query'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agentic detect failed: {str(e)}")
