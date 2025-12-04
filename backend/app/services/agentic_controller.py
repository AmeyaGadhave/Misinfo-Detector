# backend/app/services/agentic_controller.py
# __define-ocg__
"""
Agentic controller for Deep Research: planning -> tool orchestration -> synthesis.
This module implements a defensible, pluggable "agent" that:
  - decomposes a research query into tasks using the LLMAgent (planning),
  - selects tools (search, scrape, research agent),
  - executes tasks with light retry/monitoring,
  - normalizes, deduplicates and scores evidence,
  - synthesizes a final JSON brief with citations and KG.
"""
from typing import List, Dict, Any, Optional
import time
import logging
import math
import hashlib

# Assignment-required variables
varOcg = {"agent": "agentic-controller-v1"}
varFiltersCg = {"domains": [], "min_reliability": 0.0}

# Local services (must exist in your project)
from app.services.llm_agent import LLMAgent        # OpenAI wrapper (hybrid)
from app.services.research_agent import ResearchAgent
from app.services.knowledge_graph import build_graph
from app.services.credibility import CredibilityEngine
from app.services.scraper import Scraper

# Optional pluggable search tool interface - adapt to your tools/search implementation:
class SearchToolInterface:
    """Simple interface that search tools should implement."""
    def search(self, query: str, n: int = 5, domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Return list of dicts: {"id": str, "title": str, "url": str, "snippet": str, "domain": str, "score": float}
        This default is a mock. Replace with Google CSE / Serper / Tavily wrapper.
        """
        # MOCK fallback: return empty list so the pipeline still works offline
        return []

# Utility: light normalizer & deduper
def _norm_text(t: str, length: int = 300) -> str:
    if not t: return ""
    s = " ".join(t.split())
    return s if len(s) <= length else s[:length].rsplit(" ",1)[0] + "..."

def _hash_text(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()

# Agent class
class AgenticResearchAgent:
    def __init__(self,
                 llm: Optional[LLMAgent] = None,
                 search_tool: Optional[SearchToolInterface] = None,
                 scraper: Optional[Scraper] = None,
                 research_agent: Optional[ResearchAgent] = None,
                 credibility_engine: Optional[CredibilityEngine] = None,
                 max_search_results: int = 6):
        self.llm = llm or LLMAgent()
        self.search = search_tool or SearchToolInterface()
        self.scraper = scraper or Scraper()
        self.research_agent = research_agent or ResearchAgent()
        self.cred_engine = credibility_engine or CredibilityEngine()
        self.max_search_results = max_search_results
        self.logger = logging.getLogger("AgenticResearchAgent")
        self.logger.setLevel(logging.INFO)

    def plan_tasks(self, query: str) -> List[Dict[str, Any]]:
        """
        Ask the LLM to decompose the query into a short ordered plan.
        Returns a list of tasks like:
        [{"id":"t1","role":"background","prompt":"Define the topic and scope", "requires_search":True}, ...]
        """
        # If LLM not available, fallback to a simple 3-task plan.
        if not getattr(self.llm, "available", False):
            return [
                {"id":"t1","role":"background","prompt": f"Background: define and scope '{query}'", "requires_search":True},
                {"id":"t2","role":"evidence","prompt": f"Evidence: find key studies or news pieces for '{query}'", "requires_search":True},
                {"id":"t3","role":"implications","prompt": f"Implications & open questions for '{query}'", "requires_search":False}
            ]

        # Use LLM to generate a small plan; instruct for a simple JSON array
        system = "You are a research planner. Given a one-line research query, return a JSON array of 3-6 task objects with keys: id, role (background,evidence,contradiction,implications), prompt, requires_search (true/false)."
        user = f"Query: {query}\n\nReturn JSON only."
        try:
            raw = self.llm.summarize(system + "\n\n" + user, max_tokens=300)
            # try to parse JSON inside response (LLM might produce text)
            import re, json
            m = re.search(r"\[.*\]", raw, flags=re.S)
            if m:
                plan = json.loads(m.group(0))
                # ensure fields
                for i,t in enumerate(plan):
                    t.setdefault("id", f"t{i+1}")
                    t.setdefault("role", "evidence")
                    t.setdefault("prompt", t.get("prompt", f"Investigate: {query}"))
                    t.setdefault("requires_search", True if t.get("requires_search", True) else False)
                return plan
            # fallback to heuristic
        except Exception as e:
            self.logger.warning("Planner LLM failed: %s", e)
        # fallback plan
        return [
            {"id":"t1","role":"background","prompt": f"Background: define and scope '{query}'", "requires_search":True},
            {"id":"t2","role":"evidence","prompt": f"Evidence: find key studies or news pieces for '{query}'", "requires_search":True},
            {"id":"t3","role":"implications","prompt": f"Implications & recommendations for '{query}'", "requires_search":False}
        ]

    def run_task_search_and_scrape(self, task_prompt: str, top_n: int) -> List[Dict[str, Any]]:
        """
        Use search tool to retrieve candidate URLs, then scrape pages and produce snippet objects.
        Each snippet object: {"source_id","url","title","snippet","text","domain","score"}
        """
        results = self.search.search(task_prompt, n=top_n, domains=varFiltersCg.get("domains", None))
        out = []
        seen_urls = set()
        for r in results:
            url = r.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                page = self.scraper.scrape(url)
            except Exception as e:
                self.logger.info("Scrape failed for %s: %s", url, e)
                continue
            snippet_text = _norm_text(r.get("snippet") or page.get("text","")[:400], 400)
            out.append({
                "source_id": r.get("id") or _hash_text(url),
                "url": url,
                "title": r.get("title") or page.get("title",""),
                "snippet": snippet_text,
                "text": page.get("text",""),
                "domain": r.get("domain") or (url.split("/")[2] if url else ""),
                "score": float(r.get("score", 1.0))
            })
        return out

    def normalize_and_score_evidence(self, evidence_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate, normalize and compute a lightweight relevance score.
        """
        dedup = {}
        for e in evidence_list:
            key = e.get("url") or e.get("source_id") or _hash_text(e.get("snippet",""))
            if key not in dedup:
                dedup[key] = e
            else:
                # merge heuristics: keep longer text and higher score
                existing = dedup[key]
                if len(e.get("text","")) > len(existing.get("text","")):
                    dedup[key] = e
                dedup[key]["score"] = max(existing.get("score",0), e.get("score",0))
        normalized = list(dedup.values())
        # simple ranking: domain reliability * snippet score * log(length)
        for item in normalized:
            domain = item.get("domain","")
            # domain heuristic: prefer trusted sources
            dom_score = 0.5
            if any(k in domain for k in ["bbc.", "reuters.", "nytimes.", "theguardian.", "apnews"]):
                dom_score = 0.95
            length = max(1, len(item.get("text","")))
            length_factor = min(1.0, math.log1p(length)/math.log1p(4000))
            item["relevance"] = round(dom_score * (item.get("score",1.0)) * (0.6*length_factor + 0.4), 3)
        # sort descending
        normalized.sort(key=lambda x: x.get("relevance",0), reverse=True)
        return normalized

    def synthesize_brief(self, query: str, task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use the LLM to synthesize a short structured, citation-aware brief.
        We also attach KG and compute credibility.
        """
        # aggregate evidence snippets text & citation mapping
        citations = []
        evidence_texts = []
        for tr in task_results:
            # tr: {"task":..., "evidence": [snippet_objs]}
            for s in tr.get("evidence", []):
                citations.append({"id": s.get("source_id"), "url": s.get("url"), "title": s.get("title"), "score": s.get("relevance",0)})
                evidence_texts.append(f"[{s.get('source_id')}] {s.get('snippet')}")
        # build combined text (short)
        combined_text = "\n\n".join(evidence_texts[:12])
        # build KG from the concatenated top evidence texts
        kg = build_graph("\n\n".join([s.get("text","") for tr in task_results for s in tr.get("evidence", [])[:3]]))

        # call llm to produce final sections (if available)
        final_sections = []
        if getattr(self.llm, "available", False):
            # Construct a prompt instructing JSON output with sections
            prompt_system = "You are an expert research synthesizer. Given a research query, evidence citations (with source tags) and short notes, produce a JSON object with keys: sections (array of {order:int, content:str}), conclusion:str, contradictions_and_uncertainities:[...], citations:[{id,url,title,score}]."
            user = f"Query: {query}\n\nEvidence excerpts:\n{combined_text}\n\nReturn JSON only."
            try:
                raw = self.llm.summarize(prompt_system + "\n\n" + user, max_tokens=700)
                import re, json
                m = re.search(r"\{.*\}", raw, flags=re.S)
                if m:
                    out = json.loads(m.group(0))
                    # Ensure keys and attach citations+kg
                    out.setdefault("citations", citations)
                    out.setdefault("knowledge_graph", kg)
                    return out
            except Exception as e:
                self.logger.warning("LLM synthesis failed: %s", e)

        # Fallback simple synthesized brief
        sections = []
        order = 1
        for tr in task_results:
            content = f"Task: {tr.get('task').get('role','task')} - {tr.get('task').get('prompt')}\nFindings:\n"
            for s in tr.get("evidence", [])[:3]:
                content += f"- {s.get('snippet')[:240]} (source: {s.get('domain')})\n"
            sections.append({"order": order, "content": content})
            order += 1

        conclusion = f"(auto) Brief conclusion for: {query}"
        contradictions = []  # you can implement simple checks (contradictory stance across sources)
        return {"sections": sections, "conclusion": conclusion, "contradictions_and_uncertainities": contradictions, "citations": citations, "knowledge_graph": kg}

    def run(self, query: str, max_task_results: int = 4, search_per_task: int = None) -> Dict[str, Any]:
        """
        High-level entry point:
          - plan tasks
          - for each task that requires search, run search->scrape->evidence extraction
          - otherwise call research_agent.analyze on scraped article (if you passed a URL)
          - normalize evidence, compute credibility for each source, synthesize final brief
        Returns structured JSON (sections, conclusion, contradictions, citations, credibility, knowledge_graph)
        """
        search_per_task = search_per_task or self.max_search_results
        plan = self.plan_tasks(query)
        task_results = []

        for task in plan:
            self.logger.info("Running task: %s - requires_search: %s", task.get("id"), task.get("requires_search"))
            evidence_objs = []
            if task.get("requires_search", True):
                # 1) search + scrape
                raw_hits = self.run_task_search_and_scrape(task.get("prompt"), top_n=search_per_task)
                evidence_objs = self.normalize_and_score_evidence(raw_hits)
            else:
                # If no search required, try to run lightweight LLM analysis
                # Use the ResearchAgent for summarization & snippets
                short = self.research_agent.analyze({"title": query, "text": task.get("prompt", "")})
                # convert snippets to evidence objects
                evidence_objs = []
                for i, sn in enumerate(short.get("snippets", [])[:max_task_results]):
                    evidence_objs.append({
                        "source_id": f"internal-{task.get('id')}-{i}",
                        "url": "",
                        "title": task.get("prompt"),
                        "snippet": _norm_text(sn, 400),
                        "text": sn,
                        "domain": "internal",
                        "score": 0.8
                    })
            task_results.append({"task": task, "evidence": evidence_objs})

            # light rate-limit/respectful pause (avoid being blocked by websites/APIs)
            time.sleep(0.2)

        # Optionally compute credibility per top evidence item using CredibilityEngine -> for demo compute for top domain items
        # Build a flattened top evidence list
        flattened = []
        for tr in task_results:
            for s in tr["evidence"]:
                flattened.append(s)
        # Attach simple credibility per top item (using the credibility engine with limited article context)
        for s in flattened[:12]:
            try:
                art = {"url": s.get("url",""), "title": s.get("title",""), "text": s.get("text","")}
                # add snippets to article for LLM verify access
                art["_snippets"] = [s.get("snippet")]
                s["credibility"] = self.cred_engine.score(article=art, kg_data=None, stance={"support":0.5}, bias_note="")
            except Exception:
                s["credibility"] = None

        # Synthesize final brief
        final = self.synthesize_brief(query, task_results)

        # compute top-level credibility using CredibilityEngine on a pseudo-article created from combined text
        pseudo_article = {"url": "", "title": query, "text": "\n\n".join([s.get("text","") for s in flattened[:8]])}
        top_cred = self.cred_engine.score(article=pseudo_article, kg_data=final.get("knowledge_graph"), stance=final.get("stance",{}) if final.get("stance") else {"support":0.5}, bias_note="")

        # final output shape
        out = {
            "query": query,
            "plan": plan,
            "task_results": task_results,
            "brief": final,
            "top_level_credibility": top_cred,
            "timestamp": time.time()
        }
        return out
