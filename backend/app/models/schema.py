from pydantic import BaseModel
from typing import List, Dict, Any

class DetectRequest(BaseModel):
    url: str

class DetectionResult(BaseModel):
    url: str
    title: str
    text: str
    summary: str
    evidence: List[str]
    contradictions: List[str]
    credibility_score: float
    knowledge_graph: Dict[str, Any]
